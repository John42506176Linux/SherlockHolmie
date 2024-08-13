#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_ecr_assets as assets,
    aws_rds as rds
)
from cdk_stacks.database_stack import AuroraServerlessStack
from cdk_stacks.vpc_stack import VpcStack
from cdk_stacks.cluster_stack import ClusterStack
from cdk_stacks.lambda_stack import LambdaStack
from cdk_stacks.small_db_stack import ReportDBStack
from cdk_stacks.report_cluster_stack import ReportClusterStack
from cdk_stacks.messy_ec2_stack import ReportEC2Stack
from dotenv import load_dotenv
import os

load_dotenv()

app = cdk.App()
vpc = VpcStack(app,"SherlockVPC")
cluster = ClusterStack(app,"ClusterStack",vpc=vpc)
LambdaStack(app,"LambdaStack",cluster=cluster,vpc=vpc)
AuroraServerlessStack(app,"DatabaseStack",vpc=vpc)
ReportDBStack(app,"ReportDBStack",vpc=vpc)
ReportClusterStack(app,"ReportClusterStack",vpc=vpc)
ReportEC2Stack(app,"ReportEC2Stack",vpc=vpc)

app.synth()
