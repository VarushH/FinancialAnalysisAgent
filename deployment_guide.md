# Deployment Guide: Financial Analysis Agent on AWS Lambda

This guide outlines the steps to deploy your LangGraph-based Financial Analysis Agent to AWS Lambda using a Docker container image.

## Architecture Overview

Based on your current code (`app/main.py` and `app/workflow/financial_graph.py`), your application uses a **Monolithic Lambda Architecture**.

*   **How many Lambdas?** **1 Lambda Function**.
    *   Your `financial_graph` coordinates all agents (Supervisor, Extractor, Analyzer, etc.) within a single process.
    *   The `handler` in `main.py` invokes the graph and waits for the result.
    *   **Pros**: Simpler to deploy and debug; shared state in memory is fast.
    *   **Cons**: Subject to Lambda's **15-minute timeout**. If your agents (esp. PDF extraction) take longer than 15 mins total, you will need to refactor this into an AWS Step Functions workflow.

## Prerequisites

1.  **AWS CLI** installed and configured (`aws configure`).
2.  **Docker Desktop** running (for building the image).
3.  **Python** installed.

---

## Step 1: Create DynamoDB Table

Your application relies on DynamoDB to save state (Session History).

1.  Go to the [DynamoDB Console](https://console.aws.amazon.com/dynamodbv2/).
2.  Click **Create table**.
3.  **Table name**: `financial-agent-sessions` (This matches `app/state/dynamodb.py`).
4.  **Partition key**: `session_id` (String).
5.  **Settings**: Default settings (On-demand capacity is recommended for keeping costs low during development).
6.  Click **Create table**.

## Step 2: Create ECR Repository

We need a place to store your Docker image.

1.  Go to the [Amazon ECR Console](https://console.aws.amazon.com/ecr/).
2.  Click **Create repository**.
3.  **Visibility settings**: Private.
4.  **Repository name**: `financial-analysis-agent`.
5.  Click **Create repository**.
6.  **Note the URI** of your repository (e.g., `123456789012.dkr.ecr.us-east-1.amazonaws.com/financial-analysis-agent`).

## Step 3: Build and Push Docker Image

Run these commands in your project root (where the `Dockerfile` is).

**(Windows PowerShell)**

```powershell
# 1. Login to ECR
# Replace <REGION> with your region (e.g., us-east-1) and <ACCOUNT_ID> with your AWS Account ID
aws ecr get-login-password --region <REGION> --profile <YOUR_PROFILE_IF_ANY> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

# 2. Build the image
docker build -t financial-analysis-agent .

# 3. Tag the image
# Replace <REPO_URI> with the URI you noted in Step 2
docker tag financial-analysis-agent:latest <REPO_URI>:latest

# 4. Push the image
docker push <REPO_URI>:latest
```

## Step 4: Create Lambda Function

1.  Go to the [Lambda Console](https://console.aws.amazon.com/lambda/).
2.  Click **Create function**.
3.  Select **Container image**.
4.  **Function name**: `FinancialAnalysisAgent`.
5.  **Container image URI**: Click "Browse images" and select the image you just pushed to ECR.
6.  Click **Create function**.

### Configuration

Once created, go to the **Configuration** tab:

1.  **General configuration** -> **Edit**:
    *   **Memory**: Set to at least **2048 MB** (PDF processing and LLMs are memory intensive).
    *   **Timeout**: Set to **15 min 0 sec** (Max allowed).
    *   Click **Save**.
2.  **Permissions** -> Click the **Role name**:
    *   This opens IAM. Click **Add permissions** -> **Attach policies**.
    *   Search for `AmazonDynamoDBFullAccess` (or create a custom policy strictly for the `financial-agent-sessions` table) and attach it.
    *   (If you use S3 for PDFs) Attach `AmazonS3ReadOnlyAccess`.
3.  **Environment variables** -> **Edit**:
    *   Add your API keys required by the agents (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.).

## Step 5: Setup API Gateway

To trigger this via HTTP (REST API or Webhook):

1.  Go to the [API Gateway Console](https://console.aws.amazon.com/apigateway/).
2.  Click **Create API**.
3.  Choose **HTTP API** (Simpler, cheaper) or **REST API** (More features). Let's use **HTTP API**.
4.  **Integration**: Select **Lambda**.
5.  **Lambda function**: Select `FinancialAnalysisAgent`.
6.  **API Name**: `FinancialAgentAPI`.
7.  Click **Next** through routes (Default `$default` route is fine for testing) and stages.
8.  Click **Create**.
9.  **Note the Invoke URL**.

## Critical Note: Handling PDF Files

Your `extract_agent` expects a `pdf_path`.
*   **Local paths (C:\...) will NOT work in Lambda.**
*   **Solution**:
    1.  The input event should contain an **S3 URL** (e.g., `s3://my-bucket/doc.pdf`) or a public URL.
    2.  You must update `app/agents/extractor.py` to download this file from S3 to `/tmp/doc.pdf` inside the Lambda before processing. Lambda only allows writing to `/tmp`.

## Summary
*   **Lambda Count**: 1
*   **Architecture**: Container-based (Docker) due to heavy dependencies (`unstructured`, `poppler`).
*   **Timeout**: Hard limit of 15 minutes.
