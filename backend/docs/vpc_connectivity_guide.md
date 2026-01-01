# Lambda Connectivity Guide

This guide explains the network architecture options for your Lambda function.

## Current Architecture: Lambda Outside VPC (Recommended)

**Status**: ✅ **Currently Deployed**

Your Lambda function is deployed **outside of a VPC**, which provides:

### Advantages
- ✅ **Full Internet Access**: Can connect to AWS services (Bedrock, Cognito, DynamoDB, S3) and external APIs
- ✅ **No Additional Costs**: No VPC endpoints or NAT Gateway fees
- ✅ **Simpler Setup**: No VPC configuration needed
- ✅ **Faster Cold Starts**: No ENI (Elastic Network Interface) creation delay

### Database Access
- RDS database is configured as **publicly accessible**
- Security Group restricts access to specific IPs/ranges
- Database credentials stored in Lambda environment variables
- SSL/TLS encryption for database connections

### Security Considerations
- Lambda uses IAM roles for AWS service access
- Database password is strong and rotated regularly
- Security Group limits database access
- Consider using AWS Secrets Manager for credentials in production

---

## Alternative: Lambda in VPC (Not Recommended for This Use Case)

If you need Lambda inside a VPC (e.g., for private database access), you have two options:

### Option 1: VPC with NAT Gateway
**Cost**: ~$32/month + data transfer fees

**Provides**:
- Access to private RDS database
- Internet access for AWS services and external APIs

**Setup**:
1. Create NAT Gateway in public subnet
2. Update private subnet route table to route `0.0.0.0/0` through NAT Gateway
3. Configure Lambda to use private subnets

### Option 2: VPC with VPC Endpoints
**Cost**: ~$7-10/month per endpoint

**Provides**:
- Access to private RDS database
- Access to specific AWS services (Bedrock, DynamoDB, S3, Cognito)
- **No** access to external internet

**Required Endpoints**:
- `com.amazonaws.us-east-1.bedrock-runtime` - For Bedrock LLM calls
- `com.amazonaws.us-east-1.dynamodb` - For DynamoDB conversations
- `com.amazonaws.us-east-1.s3` - For S3 thumbnail storage
- `com.amazonaws.us-east-1.cognito-idp` - For Cognito authentication

**Setup**:
1. Create VPC endpoints for each service
2. Configure Security Groups to allow HTTPS (port 443)
3. Update Lambda to use VPC subnets

---

## Cost Comparison

| Architecture | Monthly Cost | Internet Access | AWS Services | Private DB |
|-------------|--------------|-----------------|--------------|------------|
| **No VPC (Current)** | **$0** | ✅ Yes | ✅ Yes | ❌ No (DB must be public) |
| VPC + NAT Gateway | ~$32 | ✅ Yes | ✅ Yes | ✅ Yes |
| VPC + Endpoints | ~$28-40 | ❌ No | ✅ Yes (specific) | ✅ Yes |

---

## When to Use Each Option

### Use No VPC (Current) When:
- Database can be publicly accessible with proper security
- Cost is a primary concern
- Simplicity is preferred
- You need both AWS services AND external API access

### Use VPC + NAT Gateway When:
- Database must be private
- You need external internet access (e.g., calling Groq, OpenAI)
- Budget allows ~$32/month

### Use VPC + Endpoints When:
- Database must be private
- You only need AWS services (no external APIs)
- You want to minimize costs compared to NAT Gateway

---

## Switching Architectures

### To Move Lambda INTO VPC:
```bash
aws lambda update-function-configuration \
    --function-name cg-production-chatbot \
    --vpc-config SubnetIds=subnet-xxx,subnet-yyy,SecurityGroupIds=sg-zzz \
    --region us-east-1
```

### To Remove Lambda FROM VPC:
```bash
aws lambda update-function-configuration \
    --function-name cg-production-chatbot \
    --vpc-config SubnetIds=[],SecurityGroupIds=[] \
    --region us-east-1
```

---

## Security Best Practices

Regardless of architecture:

1. **Use IAM Roles**: Lambda should use IAM roles, not access keys
2. **Rotate Credentials**: Regularly rotate database passwords
3. **Use Secrets Manager**: Store sensitive credentials in AWS Secrets Manager
4. **Enable CloudWatch Logs**: Monitor Lambda execution and errors
5. **Restrict Security Groups**: Only allow necessary inbound/outbound traffic
6. **Use HTTPS**: Always use SSL/TLS for database and API connections
7. **Enable VPC Flow Logs**: If using VPC, enable flow logs for monitoring
