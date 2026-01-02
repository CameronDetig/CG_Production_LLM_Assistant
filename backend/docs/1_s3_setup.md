# S3 Thumbnail Bucket Setup Guide

This guide walks through setting up the S3 bucket for storing and serving thumbnail images.

## Overview

The S3 bucket will store 512x512 JPEG thumbnails for:
- Blender files (`.blend`)
- Images (`.png`, `.jpg`, etc.)
- Videos (`.mp4`, `.mov`, etc.)

Lambda will generate presigned URLs for secure, temporary access to these thumbnails.

---

## Step 1: Create S3 Bucket

### Using AWS Console

1. **Navigate to S3**:
   - Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
   - Click **"Create bucket"**

2. **Configure Bucket**:
   - **Bucket name**: `cg-production-data-thumbnails`
   - **Region**: `us-east-1` (same as Lambda)
   - **Block Public Access**: Keep all enabled (we'll use presigned URLs)
   - Click **"Create bucket"**

### Using AWS CLI

```bash
aws s3 mb s3://cg-production-data-thumbnails --region us-east-1
```

---

## Step 2: Create Folder Structure

The bucket should have three folders matching your file types:

```
cg-production-data-thumbnails/
├── blend/
│   └── {file_id}_thumb.jpg
├── image/
│   └── {file_id}_thumb.jpg
└── video/
    └── {file_id}_thumb.jpg
```

### Create Folders (AWS Console)

1. Open the `cg-production-data-thumbnails` bucket
2. Click **"Create folder"**
3. Create three folders: `blend`, `image`, `video`

### Create Folders (AWS CLI)

```bash
# Create placeholder files to establish folder structure
touch .placeholder
aws s3 cp .placeholder s3://cg-production-data-thumbnails/blend/.placeholder
aws s3 cp .placeholder s3://cg-production-data-thumbnails/image/.placeholder
aws s3 cp .placeholder s3://cg-production-data-thumbnails/video/.placeholder
rm .placeholder
```

---

## Step 3: Configure Bucket Policy

Create a bucket policy that allows Lambda to read objects.

### Create Policy File

Create `s3-bucket-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaReadAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:role/cg-chatbot-lambda-role"
      },
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::cg-production-data-thumbnails/*"
    }
  ]
}
```

**Replace `YOUR_ACCOUNT_ID`** with your AWS account ID:

```bash
# Get your account ID
aws sts get-caller-identity --query Account --output text
```

### Apply Bucket Policy

```bash
aws s3api put-bucket-policy \
  --bucket cg-production-data-thumbnails \
  --policy file://s3-bucket-policy.json
```

---

## Step 4: Update Lambda IAM Role

Add S3 permissions to your Lambda execution role.

### Using AWS Console

1. **Navigate to IAM**:
   - Go to [IAM Console](https://console.aws.amazon.com/iam/)
   - Click **"Roles"** → Find `cg-chatbot-lambda-role`

2. **Add Inline Policy**:
   - Click **"Add permissions"** → **"Create inline policy"**
   - Click **"JSON"** tab
   - Paste the policy below
   - Name it `S3ThumbnailAccess`
   - Click **"Create policy"**

**Policy JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::cg-production-data-thumbnails/*"
    }
  ]
}
```

### Using AWS CLI

```bash
# Create policy file
cat > s3-lambda-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::cg-production-data-thumbnails/*"
    }
  ]
}
EOF

# Attach to Lambda role
aws iam put-role-policy \
  --role-name cg-chatbot-lambda-role \
  --policy-name S3ThumbnailAccess \
  --policy-document file://s3-lambda-policy.json
```



---

## Step 5: Update Lambda Environment Variables

Add the S3 bucket name to Lambda configuration.

### Using AWS Console

1. Go to Lambda function `cg-production-chatbot`
2. Click **"Configuration"** → **"Environment variables"** → **"Edit"**
3. Add:
   - **Key**: `THUMBNAIL_BUCKET`
   - **Value**: `cg-production-data-thumbnails`
4. Click **"Save"**

### Using AWS CLI

```bash
# Get current environment variables
CURRENT_ENV=$(aws lambda get-function-configuration \
  --function-name cg-production-chatbot \
  --query 'Environment.Variables' \
  --output json)

# Add THUMBNAIL_BUCKET (you'll need to merge with existing vars)
aws lambda update-function-configuration \
  --function-name cg-production-chatbot \
  --environment "Variables={THUMBNAIL_BUCKET=cg-production-thumbnails,...}" # Add other existing vars
```

---

## Step 6: Test Presigned URL Generation

Once `s3_utils.py` is implemented, test presigned URL generation:

```python
from s3_utils import get_thumbnail_url

# Test with a real file
url = get_thumbnail_url("images/123_thumb.jpg")
print(url)
# Should output: https://cg-production-thumbnails.s3.amazonaws.com/images/123_thumb.jpg?X-Amz-Algorithm=...
```

---

## Troubleshooting

### "Access Denied" Errors

**Check**:
1. Lambda IAM role has `s3:GetObject` permission
2. Bucket policy allows Lambda role
3. Object exists in S3: `aws s3 ls s3://cg-production-thumbnails/images/123_thumb.jpg`

### Presigned URLs Expire Too Quickly

Default expiration is 3600 seconds (1 hour). Adjust in `s3_utils.py`:

```python
url = s3_client.generate_presigned_url(
    'get_object',
    Params={'Bucket': BUCKET_NAME, 'Key': key},
    ExpiresIn=7200  # 2 hours
)
```

### Large Upload Times

For bulk uploads, use S3 Transfer Acceleration:

```bash
# Enable transfer acceleration
aws s3api put-bucket-accelerate-configuration \
  --bucket cg-production-thumbnails \
  --accelerate-configuration Status=Enabled

# Upload with acceleration
aws s3 sync ./thumbnails/ s3://cg-production-thumbnails/ \
  --endpoint-url https://cg-production-thumbnails.s3-accelerate.amazonaws.com
```

---

## Cost Estimation

**Storage**: ~$0.023/GB/month
- 20GB of thumbnails = ~$0.46/month

**Requests**: $0.0004 per 1,000 GET requests
- 10,000 requests/month = ~$0.004/month

**Data Transfer**: First 100GB/month free

**Total**: ~$0.50/month for typical usage

---

## Next Steps

After S3 setup is complete:
1. ✅ S3 bucket created and configured
2. ➡️ Implement `s3_utils.py` for presigned URL generation
3. ➡️ Update database functions to include thumbnail URLs
4. ➡️ Test thumbnail display in frontend
