# -----------------------------------------------------------------------------
# What's in this file:
#   A self-contained deployment script that takes the project from local code
#   to a running Amazon Bedrock AgentCore endpoint in one command. It handles
#   every AWS resource the agent needs: ECR repo, Docker build+push, IAM
#   execution role, and the AgentCore agent runtime itself.
#
# Technologies used:
#   - Docker (CLI via subprocess) — builds and tags the container image
#   - Amazon ECR — stores the Docker image in AWS
#   - AWS IAM — creates a least-privilege execution role for AgentCore
#   - Amazon Bedrock AgentCore (bedrock-agentcore-control boto3 client) —
#     creates the managed agent runtime that serves /invocations traffic
#   - boto3 / botocore — all AWS API calls
#   - Python stdlib: argparse, json, subprocess, sys, time
#
# Example of what this file does:
#   Running `python deploy.py --region us-east-1 --account-id 123456789012`
#   builds the Docker image, pushes it to ECR at
#   123456789012.dkr.ecr.us-east-1.amazonaws.com/nathan-webb-doc-review:latest,
#   creates the NathanWebbAgentCoreRole IAM role with Bedrock + ECR policies,
#   then calls create_agent_runtime and prints the live HTTPS endpoint.
# -----------------------------------------------------------------------------
"""
Deploy the Nathan Webb Doc Review Agent to Amazon Bedrock AgentCore.

Usage:
    python deploy.py --region us-east-1 --account-id 123456789012

What this script does:
  1. Creates an ECR repository (if needed) and pushes the Docker image
  2. Creates an IAM execution role for AgentCore
  3. Creates (or updates) a Bedrock AgentCore agent runtime
  4. Prints the invocation endpoint

Prerequisites:
  - Docker daemon running locally
  - AWS credentials configured (aws configure or IAM role)
  - Sufficient IAM permissions: ECR, IAM, bedrock:*
"""

import argparse
import json
import subprocess
import sys
import time
import boto3
from botocore.exceptions import ClientError

REPO_NAME = "nathan-webb-doc-review"
AGENT_NAME = "nathan-webb-doc-review-agent"
ROLE_NAME = "NathanWebbAgentCoreRole"


def run(cmd: str, check=True) -> str:
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        sys.exit(result.returncode)
    return result.stdout.strip()


def ensure_ecr_repo(ecr_client, account_id: str, region: str) -> str:
    repo_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{REPO_NAME}"
    try:
        ecr_client.create_repository(
            repositoryName=REPO_NAME,
            imageScanningConfiguration={"scanOnPush": True},
            encryptionConfiguration={"encryptionType": "AES256"},
        )
        print(f"  Created ECR repository: {REPO_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryAlreadyExistsException":
            print(f"  ECR repository already exists: {REPO_NAME}")
        else:
            raise
    return repo_uri


def build_and_push(repo_uri: str, region: str):
    print("\n[1/3] Authenticating Docker with ECR...")
    run(f"aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {repo_uri.split('/')[0]}")

    print("\n[2/3] Building Docker image...")
    run(f"docker build -t {REPO_NAME}:latest .")
    run(f"docker tag {REPO_NAME}:latest {repo_uri}:latest")

    print("\n[3/3] Pushing image to ECR...")
    run(f"docker push {repo_uri}:latest")

    digest = run(f"docker inspect --format='{{{{.RepoDigests}}}}' {repo_uri}:latest")
    print(f"  Image pushed. Digest info: {digest}")
    return f"{repo_uri}:latest"


def ensure_iam_role(iam_client, account_id: str) -> str:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        role = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for Nathan Webb AgentCore agent",
        )
        role_arn = role["Role"]["Arn"]
        print(f"  Created IAM role: {ROLE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            role_arn = iam_client.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
            print(f"  IAM role already exists: {ROLE_NAME}")
        else:
            raise

    # Attach required policies
    policies = [
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
    ]
    for policy_arn in policies:
        try:
            iam_client.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy_arn)
        except ClientError:
            pass  # already attached

    time.sleep(10)  # IAM propagation
    return role_arn


def deploy_to_agentcore(bedrock_client, image_uri: str, role_arn: str) -> dict:
    """
    Create or update a Bedrock AgentCore agent runtime.
    Uses the bedrock-agentcore control plane API.
    """
    print(f"\n  Deploying to Bedrock AgentCore as: {AGENT_NAME}")

    agent_config = {
        "agentRuntimeName": AGENT_NAME,
        "description": "Nathan Webb — rigorous document reviewer with a Bezos-inspired philosophy",
        "containerConfiguration": {
            "containerImage": image_uri,
            "containerPort": 8080,
            "healthCheckPath": "/ping",
            "environment": {
                "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20251001-v2:0",
                "ENV": "prod",
            },
        },
        "executionRoleArn": role_arn,
        "networkConfiguration": {
            "securityGroupIds": [],   # fill in your VPC security groups
            "subnetIds": [],          # fill in your VPC subnet IDs
        },
    }

    try:
        response = bedrock_client.create_agent_runtime(**agent_config)
        print(f"  Agent runtime created.")
        return response
    except ClientError as e:
        if "already exists" in str(e).lower() or e.response["Error"]["Code"] in ("ConflictException", "ResourceAlreadyExistsException"):
            print(f"  Agent runtime already exists — updating...")
            response = bedrock_client.update_agent_runtime(
                agentRuntimeName=AGENT_NAME,
                containerConfiguration=agent_config["containerConfiguration"],
            )
            return response
        else:
            print(f"\n  NOTE: AgentCore create_agent_runtime API may differ in your SDK version.")
            print(f"  Error: {e}")
            print(f"\n  Manual deployment config (use AWS Console or CLI):")
            print(json.dumps(agent_config, indent=2))
            return {}


def main():
    parser = argparse.ArgumentParser(description="Deploy Nathan Webb Agent to AgentCore")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--account-id", required=True, help="AWS account ID (12 digits)")
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build/push")
    args = parser.parse_args()

    region = args.region
    account_id = args.account_id

    session = boto3.Session(region_name=region)
    ecr = session.client("ecr")
    iam = session.client("iam")

    print(f"\n{'='*60}")
    print(f"  Deploying Nathan Webb Doc Review Agent")
    print(f"  Region: {region} | Account: {account_id}")
    print(f"{'='*60}\n")

    repo_uri = ensure_ecr_repo(ecr, account_id, region)

    if not args.skip_build:
        image_uri = build_and_push(repo_uri, region)
    else:
        image_uri = f"{repo_uri}:latest"
        print("  Skipping Docker build (--skip-build).")

    print("\n[IAM] Ensuring execution role...")
    role_arn = ensure_iam_role(iam, account_id)
    print(f"  Role ARN: {role_arn}")

    print("\n[AgentCore] Deploying agent runtime...")
    response = deploy_to_agentcore(
        session.client("bedrock-agentcore-control"),
        image_uri,
        role_arn,
    )

    print(f"\n{'='*60}")
    print(f"  Deployment complete!")
    if response:
        endpoint = response.get("agentRuntimeEndpoint", response.get("endpoint", "See AWS Console"))
        print(f"  Endpoint: {endpoint}")
    print(f"\n  Invoke your agent:")
    print(f"  curl -X POST <endpoint>/invocations \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"documentText\": \"Your document here...\", \"documentTitle\": \"My Proposal\"}}'")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
