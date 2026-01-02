# Multi-stage Dockerfile for AWS Lambda Container
# 
# This uses a two-stage build to avoid compilation errors in the Lambda base image:
# - Stage 1: Build dependencies in python:3.11-slim (has modern build tools)
# - Stage 2: Copy built packages to Lambda base image
#
# IMPORTANT: Build with these flags to ensure Lambda compatibility:
#   docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t cg-chatbot .
#
# Stage 1: Build dependencies in a full Python environment
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for dependencies
WORKDIR /install

# Copy requirements and install to a target directory
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt --target /install --no-cache-dir

# Pre-download HuggingFace models so they're bundled in the image
# This is critical for Lambda in VPC which has no internet access
COPY src/core/download_models.py .
RUN PYTHONPATH=/install python download_models.py

# Stage 2: Copy to Lambda base image
FROM public.ecr.aws/lambda/python:3.11

# Copy the built dependencies from builder stage
COPY --from=builder /install ${LAMBDA_TASK_ROOT}

# Copy pre-downloaded explicit model directory
COPY --from=builder /install/model_cache ${LAMBDA_TASK_ROOT}/model_cache

# Copy all Python function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Force offline mode - prevent any network requests
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HUB_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]
