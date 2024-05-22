import json
import boto3
import os
import time

def run_task_with_retries(ecs_client, params, retries=3, delay=1):
    for attempt in range(retries):
        try:
            response = ecs_client.run_task(**params)
            return response
        except ecs_client.exceptions.ClientException as e:
            print(f"Error:{e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise e

def lambda_handler(event, context):
    # Get parameters from the API Gateway event
    subreddits = event.get('subreddits')
    years = event.get('years', 2)
    update = event.get('update',True)

    if not subreddits or not isinstance(subreddits, list):
        return {
            'statusCode': 400,
            'body': json.dumps('Missing or invalid subreddits')
        }

    # Initialize the ECS client
    ecs_client = boto3.client('ecs')

    # Retrieve environment variables
    cluster_arn = os.environ['CLUSTER_ARN']
    task_definition_arn = os.environ['TASK_DEFINITION_ARN']
    subnets = os.environ['SUBNETS'].split(',')
    security_group = os.environ['SECURITY_GROUP']

    # List to hold task ARNs
    task_arns = []

    # Start a Fargate task for each subreddit
    for subreddit in subreddits:
        params = {
            'cluster': cluster_arn,
            'taskDefinition': task_definition_arn,
            'launchType': 'FARGATE',
            'networkConfiguration': {
                'awsvpcConfiguration': {
                    'subnets': subnets,
                    'securityGroups': [security_group],
                    'assignPublicIp': 'ENABLED'
                }
            },
            'overrides': {
                'containerOverrides': [
                    {
                        'name': 'RedditContainer',
                        'environment': [
                            {'name': 'SUBREDDIT', 'value': subreddit},
                            {'name': 'ENV', 'value': 'PROD'},
                            {'name': 'YEARS', 'value': str(years)},
                            {'name': 'UPDATE','value':str(update)}
                        ]
                    }
                ],
            }
        }

        try:
            response = run_task_with_retries(ecs_client, params)
            task_arn = response['tasks'][0]['taskArn'] if response['tasks'] else f'Failed to start task for {subreddit} Error:{response}\n'
            task_arns.append(task_arn)
        except ecs_client.exceptions.ClientException as e:
            task_arns.append(f'Failed to start task for {subreddit}: {str(e)}')

    # Return the task IDs or other relevant information
    return {
        'statusCode': 200,
        'body': json.dumps(f'Tasks started: {task_arns}')
    }
