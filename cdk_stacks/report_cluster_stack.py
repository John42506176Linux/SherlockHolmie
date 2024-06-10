import aws_cdk as core

from aws_cdk import (
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as assets,
)
import boto3

from constructs import Construct
import aws_cdk.aws_ecs_patterns as ecs_patterns
from dotenv import load_dotenv
import os
load_dotenv()

db_username = os.getenv('DB_USERNAME')
db_password=os.getenv('DB_PASSWORD')
db_host=os.getenv('DB_HOST')
db_port=os.getenv('DB_PORT')
db_database=os.getenv('DB_DATABASE')
openai_api_key=os.getenv('OPENAI_API_KEY')
google_api_key=os.getenv('GOOGLE_API_KEY')
aws_region=os.getenv('AWS_REGION')
aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')

def get_latest_image_tag(repository_name):
            client = boto3.client('ecr', region_name='us-west-2')
            response = client.describe_images(
                repositoryName=repository_name,
                filter={'tagStatus': 'TAGGED'},
                maxResults=1,
            )
            print("Tag: ",response['imageDetails'][0]['imageTags'][0])
            return response['imageDetails'][0]['imageTags'][0]

class ReportClusterStack(core.Stack):

    def __init__(self, scope: Construct, id: str,vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create a ECS cluster
        self.cluster = ecs.Cluster(self, 'ReportGeneratorCluster', vpc=vpc.vpc)

        # Create an IAM role for the Fargate task to allow it to execute
        task_role = iam.Role(
            self,
            "ReportGeneratorRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryFullAccess"),
                # Add any additional policies as needed
            ],
        )

        latest_image_tag = get_latest_image_tag('sherlockholmie-report')

        image = ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            image=ecs.RepositoryImage.from_registry(f'791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie-report:{latest_image_tag}'),
            environment={
                'DB_HOST': db_host,
                'DB_PORT' : db_port,
                'DB_DATABASE': db_database,
                'DB_USERNAME' : db_username,
                'DB_PASSWORD' : db_password,
                'OPENAI_API_KEY': openai_api_key,
                'ENV': 'PROD',
                'AWS_REGION': 'us-west-2',
                'AWS_ACCESS_KEY_ID': aws_access_key_id,
                'AWS_SECRET_ACCESS_KEY': aws_secret_access_key,
                'GOOGLE_API_KEY': google_api_key
            },
            execution_role=task_role,
        )

        # (iv) Create Fargate Service and ALB
        self.ecs_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ReportService",
            cluster=self.cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=2,
            task_image_options=image,
        )