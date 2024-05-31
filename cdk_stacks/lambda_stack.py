import aws_cdk as core

from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_iam as iam,
    Duration
)
from constructs import Construct
from dotenv import load_dotenv
import os 



class LambdaStack(core.Stack):

    def __init__(self, scope: Construct, id: str,cluster,vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create a Lambda function
        lambda_function = lambda_.Function(self, 'StartSubredditDownload',
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='lambda_function.lambda_handler',
            code=lambda_.Code.from_asset("lambda"),
            timeout=Duration.minutes(5),
            environment={
                'CLUSTER_ARN': cluster.cluster.cluster_arn,
                'TASK_DEFINITION_ARN': cluster.task_definition.task_definition_arn,
            }
        )
        lambda_function.add_environment('SUBNETS', ','.join([subnet.subnet_id for subnet in vpc.vpc.private_subnets]))
        lambda_function.add_environment('SECURITY_GROUP', vpc.task_security_group.security_group_id)

        user_role = "arn:aws:iam::791346673593:role/*"
        lambda_function.role.add_to_policy(iam.PolicyStatement(
            actions=['ecs:RunTask','iam:PassRole'],
            resources=[cluster.task_definition.task_definition_arn,user_role]
        ))

        api = apigateway.RestApi(self, 'SherlockApi',
                                  rest_api_name='DownloadSubreddit')

        entity = api.root.add_resource(
            'entity',
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_methods=['POST','GET', 'OPTIONS'],
                allow_origins=apigateway.Cors.ALL_ORIGINS)
        )
        entity_lambda_integration = apigateway.LambdaIntegration(
            lambda_function,
            proxy=False,
            integration_responses=[
                apigateway.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': "'*'"
                    }
                )
            ]
        )
        entity.add_method(
            'POST', entity_lambda_integration,
            api_key_required=True,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True
                    }
                )
            ]
        )

        api_key = api.add_api_key(
            'SHERLOCK_BACKEND_API_KEY',
            description='API Key for lambda backend call',
            value=os.environ['SHERLOCK_BACKEND_API_KEY'],
        )

        # Create a usage plan
        usage_plan = api.add_usage_plan(
            'UsagePlan',
            name='Easy',
            throttle=apigateway.ThrottleSettings(
                rate_limit=10,
                burst_limit=2
            )
        )

        # Associate the API key with the usage plan
        usage_plan.add_api_key(api_key)
        usage_plan.add_api_stage(stage=api.deployment_stage)