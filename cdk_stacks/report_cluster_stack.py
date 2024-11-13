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

load_dotenv(override=True)

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
wcs_url = os.getenv('WCS_URL')
wcs_api_key = os.getenv('WCS_API_KEY')
aws_rerank_url = 'http://ec2-35-90-19-128.us-west-2.compute.amazonaws.com:7997/rerank'

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

        # Get latest image tags
        latest_report_image_tag = 'f6942f0'  # Hardcoded for now

        # Create security groups
        report_sg = ec2.SecurityGroup(self, "ReportSecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)
        redis_sg = ec2.SecurityGroup(self, "RedisSecurityGroup", vpc=vpc.vpc, allow_all_outbound=True)

        # Allow inbound traffic from report to redis
        redis_sg.add_ingress_rule(report_sg, ec2.Port.tcp(6379), "Allow report service to access Redis")
        
        # Allow inbound traffic from celery to redis
        print("AWS_RERANK_URL: ", aws_rerank_url)

        # Create Fargate Service and ALB for Report Service
        report_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ReportService",
            cluster=self.cluster,
            memory_limit_mib=2048,
            cpu=256,
            min_healthy_percent=0,
            desired_count=1,
            health_check_grace_period=core.Duration.seconds(360),
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
                    'AWS_RERANK_URL': aws_rerank_url,
                    'WCS_URL': wcs_url,
                    'WCS_API_KEY': wcs_api_key,
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
            min_healthy_percent=0,
            security_groups=[redis_sg],
            service_name="redis",
            cloud_map_options=ecs.CloudMapOptions(
                cloud_map_namespace=namespace,
                name="redis"
            )
        )
                