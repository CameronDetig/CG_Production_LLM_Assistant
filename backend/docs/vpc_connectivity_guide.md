# VPC Connectivity Guide: Bedrock & External APIs

This guide explains how to connect your private Lambda function to AWS Bedrock and external APIs (like Groq) using VPC Endpoints and NAT Gateways.

## 1. Connecting to AWS Bedrock (VPC Endpoint)

Since your Lambda is in a private VPC without internet access, you must use a **VPC Endpoint** to reach AWS Bedrock securely.

### Quick Facts
- **Service Name**: `com.amazonaws.us-east-1.bedrock-runtime`
- **Cost**: ~$7/month per Availability Zone.
- **Type**: Interface Endpoint (requires Security Group).

### Step-by-Step Setup (AWS Console)
1. Go to **[VPC Console > Endpoints](https://console.aws.amazon.com/vpc/home?region=us-east-1#Endpoints:)**.
2. Click **Create endpoint**.
3. **Name**: `bedrock-runtime-endpoint`.
4. **Service category**: Select **AWS services**.
5. **Services**: Search for and select `com.amazonaws.us-east-1.bedrock-runtime`.
   > ⚠️ **Important**: Select `bedrock-runtime`, NOT just `bedrock`. The runtime service is used for invoking models.
6. **VPC**: Select your Lambda function's VPC.
7. **Subnets**: Select the subnets where your Lambda is running.
8. **Security Groups**:
   - Select the **same Security Group** that your Lambda uses.
   - **Crucial Configuration**: You must ensure this Security Group allows **Inbound traffic on Port 443** from itself.
   - **How to configure Inbound Rules**:
     - Type: **HTTPS**
     - Port: **443**
     - Source: **Custom** -> Start typing the name of the Security Group itself (e.g., `sg-0123...`) and select it from the dropdown. This creates a "self-referencing" rule.
9. Click **Create endpoint**.
10. Wait ~60 seconds for status to change to **Available**.

---

## 2. Connecting to External APIs (Groq, OpenAI, HuggingFace)

If you need to connect to services *outside* of AWS (like Groq, OpenAI API, or downloading models dynamically from HuggingFace), a VPC Endpoint is not enough. You need internet access.

### The Solution: NAT Gateway
Verified solution for enabling outbound internet access for private subnets.

- **Cost**: ~$32/month + data processing fees.
- **Function**: Routes traffic from your private subnet to the public internet securely.

### Setup Overview
1. **Create a Public Subnet** (if you don't have one).
2. **Create a NAT Gateway** in the public subnet.
3. **Allocate an Elastic IP** for the NAT Gateway.
4. **Update Route Table**:
   - Go to the Route Table associated with your **Lambda's Private Subnet**.
   - Add a route: `0.0.0.0/0` -> Target: `nat-gw-xxxx`.

### Comparison: VPC Endpoint vs. NAT Gateway

| Feature | VPC Endpoint (Current Setup) | NAT Gateway |
| :--- | :--- | :--- |
| **Connectivity** | AWS Services (Bedrock, S3, DynamoDB) | **Any Internet Address** (Groq, OpenAI, Google) |
| **Cost** | ~$7/month per endpoint | ~$32/month |
| **Security** | Private (Internal AWS Network) | Private Outbound (Traffic leaves AWS) |
| **Use Case** | Calling Bedrock LLMs | Calling Groq/OpenAI APIs |
