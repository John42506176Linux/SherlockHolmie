#!/bin/bash

# Get the latest git commit hash
IMAGE_VERSION=$(git rev-parse --short HEAD)

# Define variables
IMAGE_NAME="reddit-etl-task"
ACCOUNT_ID="791346673593"
REGION="us-west-2"
REPOSITORY_NAME="sherlockholmie"
ECR_URL="791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie:71d7b32"

# Build the image using docker-compose

# Tag the image
docker tag reddit-etl-task 791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie:71d7b32

# Authenticate to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 791346673593.dkr.ecr.us-west-2.amazonaws.com

# Push the image to ECR
docker push 791346673593.dkr.ecr.us-west-2.amazonaws.com/sherlockholmie:aacba10

echo "Image pushed to ${ECR_URL}"
