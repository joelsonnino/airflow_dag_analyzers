To deploy your **Airflow DAG Intelligence Dashboard** to a production environment on AWS, we will design an architecture that prioritizes scalability, security, and operational efficiency. This guide assumes you have basic familiarity with AWS services and the AWS CLI.

---

# 🚀 Production Deployment Guide: Airflow DAG Intelligence Dashboard on AWS

This document provides a comprehensive, step-by-step guide for deploying the Airflow DAG Intelligence Dashboard to a production environment on Amazon Web Services (AWS). It covers infrastructure setup, security considerations, and operational best practices, designed for a senior data scientist or MLOps engineer.

## Table of Contents
1.  [Introduction](#1-introduction)
2.  [Production Architecture Overview](#2-production-architecture-overview)
    *   [AWS Services Utilized](#aws-services-utilized)
3.  [Prerequisites](#3-prerequisites)
4.  [Step-by-Step Deployment Guide](#4-step-by-step-deployment-guide)
    *   [Step 4.1: IAM Roles and Permissions](#step-41-iam-roles-and-permissions)
    *   [Step 4.2: Network Configuration (VPC & Security Groups)](#step-42-network-configuration-vpc--security-groups)
    *   [Step 4.3: Securely Store DAGs (Amazon S3)](#step-43-securely-store-dags-amazon-s3)
    *   [Step 4.4: Deploy Ollama & LLM (EC2 Instance)](#step-44-deploy-ollama--llm-ec2-instance)
    *   [Step 4.5: Containerize Application (Dockerfile)](#step-45-containerize-application-dockerfile)
    *   [Step 4.6: Push to Amazon Elastic Container Registry (ECR)](#step-46-push-to-amazon-elastic-container-registry-ecr)
    *   [Step 4.7: Deploy Analyzers (ECS Fargate Task)](#step-47-deploy-analyzers-ecs-fargate-task)
    *   [Step 4.8: Schedule Analyzers (Amazon EventBridge)](#step-48-schedule-analyzers-amazon-eventbridge)
    *   [Step 4.9: Deploy Streamlit Dashboard (ECS Fargate Service)](#step-49-deploy-streamlit-dashboard-ecs-fargate-service)
    *   [Step 4.10: Data Persistence for Reports (Amazon S3)](#step-410-data-persistence-for-reports-amazon-s3)
5.  [Security Best Practices](#5-security-best-practices)
6.  [Cost Optimization](#6-cost-optimization)
7.  [Maintenance and Updates](#7-maintenance-and-updates)
8.  [Conclusion](#9-conclusion)

---

## 1. Introduction

This guide outlines a production-grade deployment strategy for your Airflow DAG Intelligence Dashboard on AWS. The solution leverages various AWS services to ensure the analysis pipeline is robust, scalable, and secure. Key components like the Ollama LLM, Python analyzers, and the Streamlit dashboard will be deployed using containerization and managed services.

## 2. Production Architecture Overview

The proposed architecture separates concerns and uses managed services where possible to minimize operational overhead.

*   **LLM (Ollama)**: Deployed on a dedicated **Amazon EC2** instance, ideally with GPU capabilities for optimal Llama 3.2 inference performance. This instance will serve the LLM API internally within your VPC.
*   **Python Analyzers**: Packaged as Docker images and run as scheduled **AWS Fargate** tasks within **Amazon ECS**. These tasks will fetch DAG code from S3, logs from CloudWatch, and interact with the Ollama instance for AI analysis.
*   **Streamlit Dashboard**: Also packaged as a Docker image and deployed as an **Amazon ECS Fargate** service. It will expose a web interface via an **Application Load Balancer (ALB)** and securely load pre-generated analysis data from S3.
*   **Report Storage**: All generated JSON and HTML reports, especially the final dashboard data, will be stored in a dedicated **Amazon S3** bucket.
*   **Scheduling**: **Amazon EventBridge** (CloudWatch Events) will trigger the analyzer ECS Fargate tasks on a regular schedule.
*   **Networking**: All components will reside within a secure **Amazon VPC**, utilizing private subnets for backend services and a public subnet for the ALB, with appropriate **Security Groups** for granular access control.
*   **Identity & Access Management**: **AWS IAM Roles** will provide least-privilege permissions for all components.

```
+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|                                                                                           AWS VPC                                                                                                           |
| +---------------------------------------------------------------------------------------------------------------------+   +-----------------------------------------------------------------------------+ |
| | Public Subnets                                                                      | | Private Subnets (No direct Internet access)                                     | |
| |                                                                                     | |                                                                                 | |
| | +---------------------+   +-----------------------------------------------------+ | | +---------------------+   +-------------------------------------------------+ | |
| | | Internet Gateway    |   | Application Load Balancer (ALB)                   | | | | NAT Gateway         |   | EC2 (Ollama / LLM)                            | | |
| | |                     |   |   (HTTPS Listener)                                | | | |                     |   |   (GPU Instance, Port 11434, Private IP)      | | |
| | +----------+----------+   +---------------------+-------------------------------+ | | +----------+----------+   +--------+--------------------------+------------+ | |
| |            |                                     |                               | | |            |                               |                           |            | |
| +------------+-------------------------------------+-------------------------------+ | +------------+--------------------------------+                           |            | |
|              | (Internet Traffic)                  | (HTTP/S to Streamlit)         | |              | (Outbound Internet for Ollama Pulls)                 |           |            |
|              v                                     v                               | |              v                               |                           |            |
| +-----------------------------------------------------------------------------------+ | | +-------------------------------------------+---------------------------+------------+ |
| |                                                                                   | | |                                           | (Ollama API Calls)        | (Internal Access)   |
| |                                                                                   | | | +-----------------------------------------+---------------------------+------------+ |
| |                                                                                   | | | | AWS ECS Cluster                                                               | |
| | +-------------------------------------------------------------------------------+ | | | |                                                                               | |
| | | Streamlit Dashboard (ECS Fargate Service)                                     | | | | +---------------------------------------------------------------------------+ | |
| | |   (Running `streamlit run streamlit_dashboard.py`)                            | | | | | Analyzer Tasks (ECS Fargate Tasks)                                      | | |
| | |   - Security Group (Ingress 80/443 from ALB)                                  | | | | |   (Scheduled by EventBridge, run `python -m analyzers.*`)               | | |
| | +-------------------------------------------------------------------------------+ | | | | |   - Reads DAGs from S3                                                  | | |
| |                                                                                   | | | | |   - Reads Logs from CloudWatch                                          | | |
| +-----------------------------------------------------------------------------------+ | | | | |   - Writes Reports (JSON/HTML) to S3                                    | | |
|                                                                                     | | | | |   - Interacts with Ollama (Internal VPC IP)                             | | |
|                                                                                     | | | | +---------------------------------------------------------------------------+ | |
| +-----------------------------------------------------------------------------------+ | | |                                                                               | |
| | AWS CloudWatch (Logs from Airflow, Analyzers, Ollama)                           | | | +-------------------------------------------------------------------------------+ |
| +-----------------------------------------------------------------------------------+ | +---------------------------------------------------------------------------------+ |
|                                                                                     | |                                                                                   | |
| +-----------------------------------------------------------------------------------+ | +---------------------------------------------------------------------------------+ |
| | AWS S3 (DAGs source, Analyzer Reports output - `final_dashboard_data.json`)     | | | AWS EventBridge (Scheduled rule to trigger Analyzer Tasks)                      | |
| +-----------------------------------------------------------------------------------+ | +---------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
```

### AWS Services Utilized
*   **Amazon EC2**: Hosting the Ollama LLM endpoint.
*   **Amazon ECS (Fargate Launch Type)**: Running the containerized Python analyzers and Streamlit dashboard without managing servers.
*   **Amazon ECR**: Storing Docker images for the application.
*   **Amazon S3**: Centralized storage for DAG code and all generated analysis reports.
*   **Amazon CloudWatch Logs**: Collecting logs from Airflow, Ollama, and the deployed application.
*   **Amazon EventBridge**: Scheduling the periodic execution of the analysis tasks.
*   **Application Load Balancer (ALB)**: Distributing traffic to the Streamlit dashboard and enabling HTTPS.
*   **AWS VPC**: Providing a secure, isolated network environment.
*   **AWS IAM**: Managing access permissions for all AWS resources.

## 3. Prerequisites
*   An active AWS Account.
*   AWS CLI installed and configured with administrative or sufficient permissions.
*   Docker installed locally for building and pushing images.
*   Familiarity with VPC, EC2, ECS, S3 concepts.
*   Your Airflow DAGs are already stored in an S3 bucket and CloudWatch Logs are configured for your Airflow environment.

## 4. Step-by-Step Deployment Guide

### Step 4.1: IAM Roles and Permissions

Create the necessary IAM roles with least-privilege permissions.

1.  **ECS Task Execution Role**: Allows ECS tasks to pull images from ECR and send logs to CloudWatch.
    *   Managed Policy: `arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy`
2.  **ECS Task Role (for Analyzers)**: Allows analyzer tasks to interact with S3 and CloudWatch.
    *   Custom Policy (attach inline or create separate):
        ```json
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutObject"
                    ],
                    "Resource": [
                        "arn:aws:s3:::your-dags-bucket/*",
                        "arn:aws:s3:::your-reports-bucket/*",
                        "arn:aws:s3:::your-dags-bucket",
                        "arn:aws:s3:::your-reports-bucket"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:FilterLogEvents",
                        "logs:DescribeLogGroups"
                    ],
                    "Resource": "arn:aws:logs:*:*:log-group:your-airflow-log-group-prefix*:*"
                }
            ]
        }
        ```
    *   **Note**: Replace `your-dags-bucket`, `your-reports-bucket`, and `your-airflow-log-group-prefix` with your actual resource names.

### Step 4.2: Network Configuration (VPC & Security Groups)

Leverage your existing VPC or create a new one.

1.  **VPC**: Ensure you have a VPC with at least two private subnets and two public subnets across different Availability Zones (AZs).
2.  **NAT Gateway**: Deploy a NAT Gateway in one of your public subnets and associate it with route tables of your private subnets. This allows private instances/tasks to access the internet (e.g., pulling Ollama models, connecting to AWS APIs) without being publicly accessible.
3.  **Security Groups**:
    *   **`ollama-sg`**: For your EC2 Ollama instance.
        *   Inbound: Allow TCP `11434` from the security group(s) of your ECS tasks (both Analyzer and Streamlit). This keeps Ollama's API private.
        *   Outbound: Allow All Traffic (or specific ports for model pulls/updates).
    *   **`ecs-task-sg`**: For your ECS Fargate tasks.
        *   Inbound: No direct inbound needed from internet. For Analyzer tasks, allow outbound to Ollama (port 11434) and standard AWS service endpoints.
        *   Outbound: Allow All Traffic (or restrict to S3, CloudWatch, Ollama private IP, etc.).
    *   **`alb-sg`**: For your Application Load Balancer.
        *   Inbound: Allow TCP `80` (or `443` for HTTPS) from `0.0.0.0/0` (or specific IP ranges if restricted access).
        *   Outbound: Allow TCP `80` (or `443` if Streamlit runs on HTTPS) to `ecs-task-sg`.

### Step 4.3: Securely Store DAGs (Amazon S3)

Ensure your Airflow DAGs are stored in an S3 bucket. This is the source for `code_analyzer.py`.

*   **Bucket Policy**: Verify that the IAM role for your analyzer ECS tasks (from Step 4.1) has `s3:GetObject` and `s3:ListBucket` permissions on this bucket.
*   **Encryption**: Enable Server-Side Encryption (SSE-S3 or KMS) on your DAGs S3 bucket.

### Step 4.4: Deploy Ollama & LLM (EC2 Instance)

1.  **Launch EC2 Instance**:
    *   **Instance Type**: Choose a GPU-enabled instance type (e.g., `g4dn.xlarge`, `g5.xlarge`) for production use of Llama 3.2. For evaluation, a CPU-only instance (e.g., `c6i.large`) might suffice, but performance will be limited.
    *   **AMI**: Select a suitable Deep Learning AMI or Ubuntu Server AMI.
    *   **VPC/Subnet**: Deploy in a **private subnet** of your VPC.
    *   **Security Group**: Attach the `ollama-sg` created in Step 4.2.
    *   **Storage**: Allocate sufficient EBS volume (e.g., 100-200GB) for the Ollama installation and downloaded models.
    *   **Key Pair**: For SSH access.
2.  **Install Docker and Ollama**:
    *   SSH into your EC2 instance.
    *   Install Docker: `sudo apt-get update && sudo apt-get install -y docker.io`
    *   Start Docker service: `sudo systemctl start docker && sudo systemctl enable docker`
    *   Download and install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
    *   Set Ollama to listen on all interfaces if necessary (`OLLAMA_HOST=0.0.0.0` in `/etc/systemd/system/ollama.service`).
    *   Pull the Llama 3.2 model: `ollama pull llama3.2` (or your preferred version).
3.  **Verify Ollama**: From a bastion host or another instance in the same VPC, try `curl <EC2_PRIVATE_IP>:11434/api/tags` to confirm it's reachable.

### Step 4.5: Containerize Application (Dockerfile)

Create a `Dockerfile` in your project root to containerize your Python application (analyzers and Streamlit dashboard).

```dockerfile
# Use a slim Python base image for smaller size
FROM python:3.9-slim-buster

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Create reports directory if it doesn't exist (for local runs/artifacts before S3 upload)
RUN mkdir -p reports reports/daily_dashboards

# Expose the port for Streamlit
EXPOSE 8501

# No CMD here; entrypoint will be defined in ECS Task Definition
```

### Step 4.6: Push to Amazon Elastic Container Registry (ECR)

1.  **Create ECR Repository**:
    ```bash
    aws ecr create-repository --repository-name airflow-dag-intelligence-dashboard --image-tag-mutability IMMUTABLE
    ```
2.  **Authenticate Docker to ECR**:
    ```bash
    aws ecr get-login-password --region your-aws-region | docker login --username AWS --password-stdin your-aws-account-id.dkr.ecr.your-aws-region.amazonaws.com
    ```
3.  **Build and Tag Docker Image**:
    ```bash
    docker build -t airflow-dag-intelligence-dashboard .
    docker tag airflow-dag-intelligence-dashboard:latest your-aws-account-id.dkr.ecr.your-aws-region.amazonaws.com/airflow-dag-intelligence-dashboard:latest
    ```
4.  **Push Image to ECR**:
    ```bash
    docker push your-aws-account-id.dkr.ecr.your-aws-region.amazonaws.com/airflow-dag-intelligence-dashboard:latest
    ```

### Step 4.7: Deploy Analyzers (ECS Fargate Task)

Analyzers (`code_analyzer.py`, `stat_reporter.py`, `log_analyzer.py`, `report_merger_agent.py`) will run as *scheduled tasks*.

1.  **Create ECS Cluster**: If you don't have one, create an ECS cluster with Fargate capacity providers.
    ```bash
    aws ecs create-cluster --cluster-name dag-intelligence-cluster
    ```
2.  **Create Task Definition for Analyzers**: This defines the Docker image, resources, and command to run.
    *   Create a file (e.g., `analyzer-task-definition.json`):
        ```json
        {
            "family": "dag-analyzer-task",
            "networkMode": "awsvpc",
            "cpu": "1024",
            "memory": "2048",
            "requiresCompatibilities": ["FARGATE"],
            "executionRoleArn": "arn:aws:iam::your-aws-account-id:role/ecsTaskExecutionRole",
            "taskRoleArn": "arn:aws:iam::your-aws-account-id:role/ecsAnalyzerTaskRole",
            "containerDefinitions": [
                {
                    "name": "dag-analyzer",
                    "image": "your-aws-account-id.dkr.ecr.your-aws-region.amazonaws.com/airflow-dag-intelligence-dashboard:latest",
                    "command": ["python", "-m", "run_all"],
                    "environment": [
                        { "name": "OLLAMA_HOST", "value": "http://<OLLAMA_EC2_PRIVATE_IP>:11434" },
                        { "name": "S3_DAGS_DIR", "value": "s3://your-dags-bucket/dags/" },
                        { "name": "LOG_GROUP_PREFIX", "value": "your-airflow-environment-" },
                        { "name": "LOG_GROUP_NAME", "value": "your-airflow-environment-Task" },
                        { "name": "DASHBOARD_DATA_PATH", "value": "s3://your-reports-bucket/final_dashboard_data.json" }
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/ecs/dag-intelligence-analyzers",
                            "awslogs-region": "your-aws-region",
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                }
            ]
        }
        ```
    *   **Note**:
        *   Replace placeholders: `your-aws-account-id`, `your-aws-region`, `ecsTaskExecutionRole` (from Step 4.1, Execution Role), `ecsAnalyzerTaskRole` (from Step 4.1, Task Role), `OLLAMA_EC2_PRIVATE_IP`, `your-dags-bucket`, `your-reports-bucket`, `your-airflow-environment-`, `your-airflow-environment-Task`.
        *   The `command` runs `run_all.py`, which orchestrates all analyzers.
        *   `DASHBOARD_DATA_PATH` environment variable tells `report_merger_agent.py` to save the final data to S3, and `streamlit_dashboard.py` to load from S3.
    *   Register the task definition:
        ```bash
        aws ecs register-task-definition --cli-input-json file://analyzer-task-definition.json
        ```

### Step 4.8: Schedule Analyzers (Amazon EventBridge)

Set up a scheduled rule to trigger the analyzer Fargate task periodically.

1.  **Create an EventBridge Rule**:
    *   Go to EventBridge console -> Rules -> Create Rule.
    *   Choose a schedule (e.g., `cron(0 2 * * ? *)` for daily at 2 AM UTC).
    *   **Target**: Select `ECS task`.
    *   **Cluster**: `dag-intelligence-cluster`.
    *   **Task Definition**: Select `dag-analyzer-task`.
    *   **Launch Type**: `FARGATE`.
    *   **Platform Version**: `LATEST`.
    *   **VPC, Subnets, Security Groups**: Select your private subnets and `ecs-task-sg`.
    *   **IAM Role**: Choose `ecsEventsRole` (EventBridge service role for ECS).

### Step 4.9: Deploy Streamlit Dashboard (ECS Fargate Service)

This will be a long-running service for your dashboard.

1.  **Create Task Definition for Dashboard**:
    *   Create a file (e.g., `dashboard-task-definition.json`):
        ```json
        {
            "family": "dag-dashboard-task",
            "networkMode": "awsvpc",
            "cpu": "512",
            "memory": "1024",
            "requiresCompatibilities": ["FARGATE"],
            "executionRoleArn": "arn:aws:iam::your-aws-account-id:role/ecsTaskExecutionRole",
            "taskRoleArn": "arn:aws:iam::your-aws-account-id:role/ecsAnalyzerTaskRole", # Re-use analyzer role if it has S3 read for reports
            "containerDefinitions": [
                {
                    "name": "streamlit-dashboard",
                    "image": "your-aws-account-id.dkr.ecr.your-aws-region.amazonaws.com/airflow-dag-intelligence-dashboard:latest",
                    "portMappings": [
                        { "containerPort": 8501, "hostPort": 8501, "protocol": "tcp" }
                    ],
                    "environment": [
                        { "name": "OLLAMA_HOST", "value": "http://<OLLAMA_EC2_PRIVATE_IP>:11434" },
                        { "name": "DASHBOARD_DATA_PATH", "value": "s3://your-reports-bucket/final_dashboard_data.json" }
                    ],
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": "/ecs/dag-intelligence-dashboard",
                            "awslogs-region": "your-aws-region",
                            "awslogs-stream-prefix": "ecs"
                        }
                    }
                }
            ]
        }
        ```
    *   **Note**:
        *   Adjust CPU/Memory as needed for your user load.
        *   The `command` will default to `streamlit run streamlit_dashboard.py` based on the `Dockerfile` entrypoint, or you can specify it here.
        *   `DASHBOARD_DATA_PATH` must point to the S3 location where the analyzer tasks store the data.
    *   Register the task definition:
        ```bash
        aws ecs register-task-definition --cli-input-json file://dashboard-task-definition.json
        ```
2.  **Create an Application Load Balancer (ALB)**:
    *   Create an ALB in your public subnets.
    *   Configure an HTTPS listener (port 443) and attach an ACM SSL certificate.
    *   Create a target group pointing to port 8501 (Streamlit's default port).
3.  **Create ECS Service**:
    *   Go to ECS console -> Clusters -> `dag-intelligence-cluster` -> Services -> Create.
    *   **Launch Type**: `FARGATE`.
    *   **Task Definition**: `dag-dashboard-task`.
    *   **Service Name**: `dag-intelligence-dashboard-service`.
    *   **Desired Tasks**: `1` (or more for High Availability).
    *   **VPC, Subnets, Security Groups**: Select your public subnets and `ecs-task-sg`.
    *   **Load Balancing**: Choose your ALB and the target group created above.
    *   **Service Auto Scaling**: Configure scaling policies based on CPU utilization or request count if needed.

### Step 4.10: Data Persistence for Reports (Amazon S3)

The generated analysis reports (`dag_ai_audit.json`, `dag_stats.json`, `log_analysis.json`, and crucially `final_dashboard_data.json`) should be stored in a dedicated S3 bucket.

1.  **Create S3 Bucket for Reports**:
    ```bash
    aws s3 mb s3://your-reports-bucket --region your-aws-region
    ```
2.  **Update Analyzer Scripts**:
    *   Modify `report_merger_agent.py` and `streamlit_dashboard.py` (and potentially others if you want intermediate reports persisted) to use S3 paths for saving/loading data. This will involve using `boto3` for S3 `put_object` and `get_object` operations. The `data_reader.py` module already has `read_file_s3` for reading. You'll need to add S3 write capability if not already present.
    *   **Crucial:** Ensure the `DASHBOARD_DATA_PATH` environment variable set in your ECS Task Definitions (Steps 4.7 and 4.9) correctly points to the S3 path, e.g., `s3://your-reports-bucket/final_dashboard_data.json`.

## 5. Security Best Practices

*   **Least Privilege IAM**: Always grant only the necessary permissions to IAM roles.
*   **VPC Isolation**: Deploy core components (Ollama, analyzers) in private subnets.
*   **Security Groups**: Use strict inbound/outbound rules. Never expose Ollama's port directly to the internet.
*   **HTTPS**: Enable HTTPS on the ALB for the Streamlit dashboard using ACM.
*   **Secrets Management**: For any sensitive credentials (e.g., if you introduce external APIs), use AWS Secrets Manager instead of hardcoding or environment variables directly.
*   **Logging**: Ensure all services (EC2, ECS, ALB) are logging to CloudWatch Logs for auditing and debugging.
*   **Regular Security Audits**: Periodically review your AWS configuration and IAM policies.

## 6. Cost Optimization

*   **EC2 Instance Type**: Select the smallest GPU instance type that meets your performance requirements for Ollama. Consider `g4dn` or `g5` instances. If Llama 3.2 is performing adequately on CPU for your use case, a `c6i` or `m6i` instance can be significantly cheaper.
*   **Fargate CPU/Memory**: Start with minimal CPU/Memory for ECS tasks and scale up as needed. Monitor resource utilization in CloudWatch.
*   **S3 Lifecycle Policies**: Implement lifecycle policies on your S3 reports bucket to transition older data to cheaper storage classes (e.g., S3 Glacier) or expire it.
*   **Scheduled Tasks**: Ensure analyzer tasks are only run when necessary (e.g., once daily) to avoid unnecessary Fargate charges.
*   **ALB**: Costs accrue based on LCU (Load Balancer Capacity Units) and hours. Ensure your health checks are efficient.

## 7. Maintenance and Updates

*   **Code Updates**: Update your local code, rebuild the Docker image, push to ECR, and then update the ECS Task Definition to deploy new analyzer and dashboard versions.
*   **Ollama Model Updates**: SSH into your EC2 instance and run `ollama pull <model_name>` to update the LLM model.
*   **CloudWatch Alarms**: Set up alarms on ECS service health, task failures, or Streamlit dashboard response times to be notified of operational issues.
*   **Monitoring**: Use CloudWatch Dashboards to monitor the health and performance of your EC2 instance, ECS tasks, and S3 usage.

## 8. Troubleshooting Common Issues

*   **Analyzer tasks failing**:
    *   Check ECS task logs in CloudWatch. Look for Python errors, permission denied messages from S3/CloudWatch, or connection errors to Ollama.
    *   Verify `OLLAMA_HOST` environment variable points to the correct private IP of the EC2 instance.
    *   Ensure the `ecsAnalyzerTaskRole` has all necessary S3 and CloudWatch permissions.
*   **Streamlit dashboard not loading**:
    *   Check ALB health checks and target group status. Is the target group healthy?
    *   Inspect Streamlit container logs in CloudWatch for startup errors or issues loading data from S3.
    *   Verify `alb-sg` and `ecs-task-sg` allow traffic flow between the ALB and the Streamlit container.
    *   Ensure the `DASHBOARD_DATA_PATH` environment variable is correctly set and the S3 object exists and is readable by the `ecsAnalyzerTaskRole` (or a dedicated dashboard role).
*   **Ollama not reachable**:
    *   Verify the EC2 instance is running and has sufficient resources.
    *   Check `ollama-sg` rules and confirm the Ollama service is active on the EC2 instance.
    *   Ensure the private IP for `OLLAMA_HOST` is correct and resolvable within the VPC.

## 9. Conclusion

By following this guide, you will establish a robust and intelligent Airflow DAG monitoring system on AWS. This architecture provides a solid foundation for proactive pipeline management, accelerated debugging, and continuous improvement of your data orchestration workflows. Remember to regularly review and optimize your AWS resources and security configurations.