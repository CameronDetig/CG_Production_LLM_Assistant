# Dockerfile for Lambda Container (Alternative Deployment)
# Use this if you prefer containerized deployment or need custom dependencies

FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt --no-cache-dir

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}
COPY bedrock_client.py ${LAMBDA_TASK_ROOT}
COPY database.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD [ "lambda_function.lambda_handler" ]
