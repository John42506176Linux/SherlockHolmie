#!/bin/bash

# Get the latest git commit hash
IMAGE_VERSION=$(git rev-parse --short HEAD)

# Define variables
IMAGE_NAME="report-task"
ACCOUNT_ID="791346673593"
REGION="us-west-2"
REPOSITORY_NAME="sherlockholmie-report"
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}:${IMAGE_VERSION}"

# Build the image using docker-compose
docker-compose build

# Tag the image
docker tag ${IMAGE_NAME} ${ECR_URL}

# Authenticate to ECR
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Push the image to ECR
docker push ${ECR_URL}

echo "Image pushed to ${ECR_URL}"
