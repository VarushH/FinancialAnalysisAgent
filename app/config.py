import os

# Gemini
GEMINI_MODEL = "gemini-1.5-pro"

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = "financial_documents"

# DynamoDB
DYNAMODB_TABLE = "financial-agent-sessions"

# AWS
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
