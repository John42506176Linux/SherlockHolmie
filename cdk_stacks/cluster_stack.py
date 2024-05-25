import aws_cdk as core

from aws_cdk import (
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr_assets as assets,
)
from constructs import Construct
from dotenv import load_dotenv
import os
load_dotenv()

db_username = os.getenv('DB_USERNAME')
db_password=os.getenv('DB_PASSWORD')
db_host=os.getenv('DB_HOST')
db_port=os.getenv('DB_PORT')
db_database=os.getenv('DB_DATABASE')
openai_api_key=os.getenv('OPENAI_API_KEY')

class ClusterStack(core.Stack):

    def __init__(self, scope: Construct, id: str,vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        # Create a ECS cluster
        self.cluster = ecs.Cluster(self, 'RedditDownloadCluster', vpc=vpc.vpc)

        # Create a task definition with the local Docker image asset
        self.task_definition = ecs.FargateTaskDefinition(self, 'RedditETLEmbeddingTask',
            memory_limit_mib=30720,
            cpu=4096,
            ephemeral_storage_gib=40
        )
        log_group = logs.LogGroup(self, 'RedditETLLogGroup',
            retention=logs.RetentionDays.ONE_WEEK
        )
        self.task_definition.add_container('RedditContainer',
            image=ecs.RepositoryImage.from_registry('sherlockholmie/reddit-etl-task:latest'),
            logging=ecs.LogDriver.aws_logs(stream_prefix='RedditETL', log_group=log_group),
            environment={
                'DB_HOST': db_host,
                'DB_PORT' : db_port,
                'DB_DATABASE': db_database,
                'DB_USERNAME' : db_username,
                'DB_PASSWORD' : db_password,
                'OPENAI_API_KEY': openai_api_key
            }
        )

        # Create an IAM role for the Fargate task to allow it to execute
        task_role = iam.Role(self, 'SubredditDownloaderRole',
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com')
        )
        task_role.add_to_policy(iam.PolicyStatement(
            actions=['ecs:RunTask','iam:PassRole'],
            resources=[self.task_definition.task_definition_arn]
        ))