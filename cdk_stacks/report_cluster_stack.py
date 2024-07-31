import aws_cdk as core
from aws_cdk import (
    aws_ecs as ecs,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_servicediscovery as servicediscovery,
    aws_efs as efs,
)
import boto3
from constructs import Construct
import aws_cdk.aws_ecs_patterns as ecs_patterns
from dotenv import load_dotenv
import os

load_dotenv()

# Load environment variables
db_username = os.getenv('DB_USERNAME')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_database = os.getenv('DB_DATABASE')
openai_api_key = os.getenv('OPENAI_API_KEY')
google_api_key = os.getenv('GOOGLE_API_KEY')
aws_region = os.getenv('AWS_REGION')
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_rerank_model = os.getenv('AWS_RERANK_MODEL')
aws_small_rerank_model = os.getenv('AWS_SMALL_RERANK_MODEL')
nextjs_api_url = os.getenv('NEXTJS_API_URL')

def get_latest_image_tag(repository_name):
    client = boto3.client('ecr', region_name='us-west-2')
    response = client.describe_images(
        repositoryName=repository_name,
        filter={'tagStatus': 'TAGGED'},
        maxResults=3,
    )
    print("Repository Name: ", repository_name)
    print("Tag: ", response['imageDetails'][0]['imageTags'][0])
    print("Response: ", response)
    return response['imageDetails'][0]['imageTags'][0]

class ReportClusterStack(core.Stack):
    def __init__(self, scope: Construct, id: str, vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create an ECS cluster
        self.cluster = ecs.Cluster(self, 'ReportGeneratorCluster', vpc=vpc.vpc)
        namespace = servicediscovery.PrivateDnsNamespace(
            self, "ReportNamespace",
            name="report.local",
            vpc=vpc.vpc,
            description="Private namespace for report services"
        )

        # Create an IAM role for the Fargate task
        task_role = iam.Role(
            self,
            "ReportGeneratorRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonElasticFileSystemClientFullAccess")
            ],
        )

        task_role.add_to_policy(
            statement=iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
                effect=iam.Effect.ALLOW
            )
        )
        file_system = efs.FileSystem(self, "MyEfsFileSystem",
            vpc=vpc.vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            security_group=ec2.SecurityGroup(self, "EfsSecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)
        )

        # Create EFS Access Point
        access_point = file_system.add_access_point("AccessPoint",
            path="/app",  # Changed back to "/app" to match Docker Compose
            create_acl=efs.Acl(
                owner_uid="1000",
                owner_gid="1000",
                permissions="755"
            ),
            posix_user=efs.PosixUser(
                uid="1000",
                gid="1000"
            ),
        )

        # Get latest image tags
        latest_report_image_tag = '3d87d19'  # Hardcoded for now
        latest_celery_report_image_tag = '8a37941'

        # Create security groups
        report_sg = ec2.SecurityGroup(self, "ReportSecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)
        redis_sg = ec2.SecurityGroup(self, "RedisSecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)
        celery_sg = ec2.SecurityGroup(self, "CelerySecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)

        # Allow inbound traffic from report to redis
        redis_sg.add_ingress_rule(report_sg, ec2.Port.tcp(6379), "Allow report service to access Redis")
        
        # Allow inbound traffic from celery to redis
        redis_sg.add_ingress_rule(celery_sg, ec2.Port.tcp(6379), "Allow celery worker to access Redis")


        # Create Fargate Service and ALB for Report Service
        report_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ReportService",
            cluster=self.cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=2,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry(f'791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie-report:{latest_report_image_tag}'),
                environment={
                    'DB_HOST': db_host,
                    'DB_PORT': db_port,
                    'DB_DATABASE': db_database,
                    'DB_USERNAME': db_username,
                    'DB_PASSWORD': db_password,
                    'OPENAI_API_KEY': openai_api_key,
                    'ENV': 'PROD',
                    'AWS_REGION': 'us-west-2',
                    'AWS_ACCESS_KEY_ID': aws_access_key_id,
                    'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
                    'GOOGLE_API_KEY': google_api_key,
                    'AWS_RERANK_MODEL': aws_rerank_model,
                    'AWS_SMALL_RERANK_MODEL': aws_small_rerank_model,
                    'NEXTJS_API_URL': nextjs_api_url,
                    'REDIS_URL': 'redis://redis.report.local:6379/0',
                },
                execution_role=task_role,
            ),
            security_groups=[report_sg],
        )


        # Create a Fargate service for Redis
        redis_task_definition = ecs.FargateTaskDefinition(
            self, "RedisTaskDefinition",
            memory_limit_mib=512,
            cpu=256,
            execution_role=task_role,
        )

        redis_container = redis_task_definition.add_container(
            "RedisContainer",
            image=ecs.ContainerImage.from_registry("redis:alpine"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="redis")
        )
        redis_container.add_port_mappings(ecs.PortMapping(container_port=6379))

        redis_service = ecs.FargateService(
            self, "RedisService",
            cluster=self.cluster,
            task_definition=redis_task_definition,
            desired_count=1,
            security_groups=[redis_sg],
            service_name="redis",
            cloud_map_options=ecs.CloudMapOptions(
                cloud_map_namespace=namespace,
                name="redis"
            )
        )

        # Create a Fargate service for Celery Worker
        celery_task_definition = ecs.FargateTaskDefinition(
            self, "CeleryTaskDefinition",
            memory_limit_mib=16384,
            cpu=2048,
            execution_role=task_role,
        )

        celery_container = celery_task_definition.add_container(
            "CeleryContainer",
            image=ecs.ContainerImage.from_registry(f'791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie-celery:{latest_celery_report_image_tag}'),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="celery"),
            environment={
                'DB_HOST': db_host,
                'DB_PORT': db_port,
                'DB_DATABASE': db_database,
                'DB_USERNAME': db_username,
                'DB_PASSWORD': db_password,
                'OPENAI_API_KEY': openai_api_key,
                'ENV': 'PROD',
                'AWS_REGION': 'us-west-2',
                'AWS_ACCESS_KEY_ID': aws_access_key_id,
                'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
                'GOOGLE_API_KEY': google_api_key,
                'AWS_RERANK_MODEL': aws_rerank_model,
                'AWS_SMALL_RERANK_MODEL': aws_small_rerank_model,
                'NEXTJS_API_URL': nextjs_api_url,
                'REDIS_URL': 'redis://redis.report.local:6379/0',
            },
        )

        celery_worker_service = ecs.FargateService(
            self, "CeleryWorkerService",
            cluster=self.cluster,
            task_definition=celery_task_definition,
            desired_count=1,
            security_groups=[celery_sg],
        )

        # Add dependencies
        celery_worker_service.node.add_dependency(redis_service)
        report_service.service.node.add_dependency(redis_service)
        report_task_definition = report_service.task_definition
        report_task_definition.add_volume(
            name="app-volume",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=access_point.access_point_id,
                    iam="ENABLED"
                ),
                root_directory="/"
            )
        )

        report_container = report_task_definition.find_container("web")
        report_container.add_mount_points(
            ecs.MountPoint(
                container_path="/app",  # Changed back to "/app" to match Docker Compose
                source_volume="app-volume",
                read_only=False
            )
        )
        celery_task_definition.add_volume(
            name="app-volume",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=file_system.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=access_point.access_point_id,
                    iam="ENABLED"
                ),
                root_directory="/"
            )
        )

        celery_container.add_mount_points(
            ecs.MountPoint(
                container_path="/app",  # Changed back to "/app" to match Docker Compose
                source_volume="app-volume",
                read_only=False
            )
        )

        # Update IAM permissions
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticfilesystem:ClientMount",
                    "elasticfilesystem:ClientWrite",
                    "elasticfilesystem:DescribeMountTargets"
                ],
                resources=[file_system.file_system_arn]
            )
        )

        # Allow connections to EFS from the services
        file_system.connections.allow_default_port_from(celery_worker_service.connections)
        file_system.connections.allow_default_port_from(report_service.service.connections)

        # Grant access point permissions
        efs.FileSystem.from_file_system_attributes(
            self, "ImportedFileSystem",
            file_system_id=file_system.file_system_id,
            security_group=file_system.connections.security_groups[0]
        ).grant_root_access(celery_worker_service.task_definition.task_role)
        
        efs.FileSystem.from_file_system_attributes(
            self, "ImportedFileSystem2",
            file_system_id=file_system.file_system_id,
            security_group=file_system.connections.security_groups[0]
        ).grant_root_access(report_service.task_definition.task_role)

        efs_sg = ec2.SecurityGroup(self, "EFSSecurityGroup", vpc=vpc.vpc)
        efs_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(2049), "Allow NFS traffic")

        file_system.connections.allow_default_port_from(report_sg)
        file_system.connections.allow_default_port_from(celery_sg)

                