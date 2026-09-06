# Multi-stage Dockerfile for AWS Lambda Container
# 
# This uses a two-stage build on the Lambda Python base image so compiled wheels
# are compatible with Lambda's operating-system ABI.
# - Stage 1: Install dependencies and preload models
# - Stage 2: Copy the prepared application into the runtime image
#
# IMPORTANT: Build with these flags to ensure Lambda compatibility:
#   docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t cg-chatbot .
#
# Stage 1: Build dependencies in a Lambda-compatible environment.
# All dependencies below are required as wheels, so a compiler toolchain is not needed.
FROM public.ecr.aws/lambda/python:3.11 AS builder

# Create a directory for dependencies
WORKDIR /install

# Install huggingface_hub explicitly first to enable model downloading
# This allows us to cache the model download layer even if requirements.txt changes
RUN pip install --upgrade pip && \
    pip install huggingface_hub --target /install --no-cache-dir

# Pre-download HuggingFace models
# This layer will now only invalidate if download_models.py changes
COPY src/core/download_models.py .
RUN PYTHONPATH=/install python download_models.py

# Copy requirements and install the rest of the dependencies
COPY requirements.txt .
RUN pip install \
    --only-binary=:all: \
    --target /install \
    --no-cache-dir \
    -r requirements.txt

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
