from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as sm,
)
import aws_cdk as core
from constructs import Construct


class AuroraServerlessStack(core.Stack):
    """

    """
    def __init__(self, scope: Construct, id: str,vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        db_master_user_name="admin_user"

        secret = rds.DatabaseSecret(
            self,
            id="MasterUserSecret",
            username=db_master_user_name
        )
        # cluster = rds.DatabaseCluster(
        #     self,
        #     "SherlockServerlessv2",
        #     serverless_v2_max_capacity=128,
        #     serverless_v2_min_capacity= 0.5,
        #     engine=rds.DatabaseClusterEngine.aurora_postgres(
        #         version=rds.AuroraPostgresEngineVersion.VER_16_2
        #     ),
        #     credentials=rds.Credentials.from_secret(secret),
        #     writer=rds.ClusterInstance.serverless_v2(
        #         "writer", publicly_accessible=False
        #     ),
        #     readers=[
        #         rds.ClusterInstance.serverless_v2("reader1",scale_with_writer=True),
        #         rds.ClusterInstance.serverless_v2("reader2"),
        #     ],
        #     vpc=vpc.vpc,
        #     default_database_name="RedditDataBase",
        #     security_groups=[vpc.task_security_group],
        #     deletion_protection=True,
        #     enable_data_api=True
        # )
        
        core.CfnOutput(self, "RDSSecret", value=secret.secret_arn)
        