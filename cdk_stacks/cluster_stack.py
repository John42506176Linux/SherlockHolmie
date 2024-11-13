import aws_cdk as core

from aws_cdk import (
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as assets,
)
import boto3

from constructs import Construct
from dotenv import load_dotenv
import os
load_dotenv(override=True)

openai_api_key=os.getenv('OPENAI_API_KEY')
wcs_api_key = os.getenv('WCS_API_KEY')
wcs_url =  os.getenv('WCS_URL')
print("WCS URL: ", wcs_url)
embedding_url =  'http://ec2-35-90-19-128.us-west-2.compute.amazonaws.com:7997'
embedding_model = os.getenv('AWS_EMBEDDING_MODEL')

def get_latest_image_tag(repository_name):
            client = boto3.client('ecr', region_name='us-west-2')
            response = client.describe_images(
                repositoryName=repository_name,
                filter={'tagStatus': 'TAGGED'},
                maxResults=1,
            )
            print("Repository Name: ", repository_name)
            print("Tag: ", response['imageDetails'][0]['imageTags'][0])
            print("Response: ", response)
            return response['imageDetails'][0]['imageTags'][0]

class ClusterStack(core.Stack):

    def __init__(self, scope: Construct, id: str,vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create a ECS cluster
        self.cluster = ecs.Cluster(self, 'RedditDownloadCluster', vpc=vpc.vpc)
        latest_image_tag = '2a24cd9'
        # Create an IAM role for the Fargate task to allow it to execute
        task_role = iam.Role(
            self,
            "SubredditDownloaderRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryPowerUser"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryFullAccess"),
                # Add any additional policies as needed
            ],
        )

        # Create a task definition with the local Docker image asset
        self.task_definition = ecs.FargateTaskDefinition(self, 'RedditETLEmbeddingTask',
            memory_limit_mib=30720,
            cpu=4096,
            ephemeral_storage_gib=40,
            execution_role=task_role,
        )

        task_role.add_to_policy(iam.PolicyStatement(
            actions=['ecs:RunTask','iam:PassRole'],
            resources=[self.task_definition.task_definition_arn]
        ))

        log_group = logs.LogGroup(self, 'RedditETLLogGroup',
            retention=logs.RetentionDays.ONE_WEEK
        )
       
        self.task_definition.add_container('RedditContainer',
            image=ecs.RepositoryImage.from_registry(f'791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie:{latest_image_tag}'),
            logging=ecs.LogDriver.aws_logs(stream_prefix='RedditETL', log_group=log_group),
            environment={
                'OPENAI_API_KEY': openai_api_key,
                'WCS_API_KEY' : wcs_api_key,
                'WCS_URL': wcs_url,
                'AWS_EMBEDDING_URL': embedding_url,
                'AWS_EMBEDDING_MODEL': embedding_model,
            },
        )
