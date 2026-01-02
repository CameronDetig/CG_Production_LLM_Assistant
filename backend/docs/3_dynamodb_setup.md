# DynamoDB Conversations Table Setup Guide

This guide walks through creating the DynamoDB table for storing conversation history.

## Overview

DynamoDB will store:
- Conversation metadata (ID, user, title, timestamps)
- Message history (user queries, assistant responses, tool calls)
- Conversation state for multi-turn interactions

---

## Table Schema

### Primary Key Structure

- **Partition Key**: `conversation_id` (String) - UUID for each conversation
- **Sort Key**: `user_id` (String) - User identifier from Cognito

### Global Secondary Index (GSI)

- **Index Name**: `user_id-created_at-index`
- **Partition Key**: `user_id` (String)
- **Sort Key**: `created_at` (String) - ISO8601 timestamp
- **Purpose**: Efficiently list all conversations for a user, sorted by creation date

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `conversation_id` | String (PK) | UUID v4 |
| `user_id` | String (SK) | Cognito user ID or "demo" |
| `title` | String | Auto-generated from first query |
| `messages` | List | Array of message objects |
| `created_at` | String | ISO8601 timestamp |
| `updated_at` | String | ISO8601 timestamp |
| `message_count` | Number | Total messages in conversation |

### Message Object Structure

```json
{
  "role": "user" | "assistant" | "system",
  "content": "string",
  "timestamp": "2025-12-30T14:00:00Z",
  "tool_calls": [  // Optional, only for assistant messages
    {
      "tool": "search_by_metadata_embedding",
      "args": {"query": "...", "limit": 10},
      "result": [...]
    }
  ]
}
```

---

## Step 1: Create DynamoDB Table

### Using AWS Console

1. **Navigate to DynamoDB**:
   - Go to [DynamoDB Console](https://console.aws.amazon.com/dynamodb/)
   - Click **"Create table"**

2. **Configure Table**:
   - **Table name**: `cg-chatbot-conversations`
   - **Partition key**: `conversation_id` (String)
   - **Sort key**: `user_id` (String)
   - **Table settings**: Use default settings (On-demand capacity)
   - Click **"Create table"**

3. **Create GSI**:
   - Wait for table to be created
   - Click on the table → **"Indexes"** tab → **"Create index"**
   - **Index name**: `user_id-created_at-index`
   - **Partition key**: `user_id` (String)
   - **Sort key**: `created_at` (String)
   - **Projected attributes**: All
   - Click **"Create index"**

### Using AWS CLI

Create a table definition file:

```bash
cat > dynamodb-table.json << 'EOF'
{
  "TableName": "cg-chatbot-conversations",
  "KeySchema": [
    {
      "AttributeName": "conversation_id",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "user_id",
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "conversation_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "user_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "created_at",
      "AttributeType": "S"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "user_id-created_at-index",
      "KeySchema": [
        {
          "AttributeName": "user_id",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "created_at",
          "KeyType": "RANGE"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST",
  "Tags": [
    {
      "Key": "Project",
      "Value": "CG-Production-Assistant"
    }
  ]
}
EOF
```

Create the table:

```bash
aws dynamodb create-table --cli-input-json file://dynamodb-table.json --region us-east-1
```

Wait for table to be active:

```bash
aws dynamodb wait table-exists --table-name cg-chatbot-conversations --region us-east-1
```

---

## Step 2: Update Lambda IAM Role

Add DynamoDB permissions to Lambda execution role.

### Using AWS Console

1. **Navigate to IAM**:
   - Go to [IAM Console](https://console.aws.amazon.com/iam/)
   - Click **"Roles"** → Find `cg-chatbot-lambda-role`

2. **Add Inline Policy**:
   - Click **"Add permissions"** → **"Create inline policy"**
   - Click **"JSON"** tab
   - Paste the policy below
   - Name it `DynamoDBConversationsAccess`
   - Click **"Create policy"**

**Policy JSON**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations",
        "arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations/index/*"
      ]
    }
  ]
}
```

### Using AWS CLI

```bash
cat > dynamodb-lambda-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations",
        "arn:aws:dynamodb:us-east-1:*:table/cg-chatbot-conversations/index/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name cg-chatbot-lambda-role \
  --policy-name DynamoDBConversationsAccess \
  --policy-document file://dynamodb-lambda-policy.json
```

---

## Step 3: Update Lambda Environment Variables

Add DynamoDB table name to Lambda configuration.

### Using AWS Console

1. Go to Lambda function `cg-production-chatbot`
2. Click **"Configuration"** → **"Environment variables"** → **"Edit"**
3. Add:
   - **Key**: `DYNAMODB_TABLE_NAME`
   - **Value**: `cg-chatbot-conversations`
4. Click **"Save"**

### Using AWS CLI

```bash
# Update Lambda environment (merge with existing vars)
aws lambda update-function-configuration \
  --function-name cg-production-chatbot \
  --environment "Variables={DYNAMODB_TABLE_NAME=cg-chatbot-conversations,...}" \
  --region us-east-1
```

---

## Step 4: Test Table Access

Once `conversations.py` is implemented, test CRUD operations:

```python
from conversations import create_conversation, add_message, get_conversation

# Create new conversation
conv_id = create_conversation(user_id="test_user", title="Test Conversation")

# Add messages
add_message(conv_id, role="user", content="Hello!")
add_message(conv_id, role="assistant", content="Hi there!")

# Retrieve conversation
conv = get_conversation(conv_id, user_id="test_user")
print(conv)
```

---

## Example Data

### Sample Conversation Item

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "demo",
  "title": "4K Renders Search",
  "created_at": "2025-12-30T14:00:00Z",
  "updated_at": "2025-12-30T14:05:30Z",
  "message_count": 4,
  "messages": [
    {
      "role": "user",
      "content": "Show me 4K renders",
      "timestamp": "2025-12-30T14:00:00Z"
    },
    {
      "role": "assistant",
      "content": "I found 5 4K renders...",
      "timestamp": "2025-12-30T14:00:05Z",
      "tool_calls": [
        {
          "tool": "filter_by_metadata",
          "args": {"resolution": "3840x2160", "limit": 10},
          "result": [...]
        }
      ]
    },
    {
      "role": "user",
      "content": "Show me the first one",
      "timestamp": "2025-12-30T14:05:00Z"
    },
    {
      "role": "assistant",
      "content": "Here are the details...",
      "timestamp": "2025-12-30T14:05:30Z",
      "tool_calls": [
        {
          "tool": "get_file_details",
          "args": {"file_id": 123},
          "result": {...}
        }
      ]
    }
  ]
}
```

---

## Capacity Planning

### On-Demand Pricing (Recommended)

- **Writes**: $1.25 per million write request units
- **Reads**: $0.25 per million read request units
- **Storage**: $0.25 per GB/month

### Estimated Costs (1,000 conversations/month)

- **Writes**: ~2,000 writes/month (2 per conversation) = $0.0025
- **Reads**: ~5,000 reads/month (5 per user session) = $0.00125
- **Storage**: ~0.1 GB = $0.025

**Total**: ~$0.03/month for 1,000 conversations

For portfolio demo with ~100 conversations/month: **~$0.01/month**

### Provisioned Capacity (Alternative)

If you have predictable traffic, provisioned capacity can be cheaper:

- **1 RCU + 1 WCU**: $0.47/month
- Use for production with consistent load

---

## Monitoring

### View Table Metrics

```bash
# Get table description
aws dynamodb describe-table \
  --table-name cg-chatbot-conversations \
  --region us-east-1

# Get item count
aws dynamodb scan \
  --table-name cg-chatbot-conversations \
  --select COUNT \
  --region us-east-1
```

### CloudWatch Metrics

Monitor in CloudWatch:
- `ConsumedReadCapacityUnits`
- `ConsumedWriteCapacityUnits`
- `UserErrors` (throttling)

---

## Troubleshooting

### "ResourceNotFoundException"

**Solution**: Verify table exists and region is correct:

```bash
aws dynamodb list-tables --region us-east-1
```

### "AccessDeniedException"

**Solution**: Check Lambda IAM role has DynamoDB permissions:

```bash
aws iam get-role-policy \
  --role-name cg-chatbot-lambda-role \
  --policy-name DynamoDBConversationsAccess
```

### GSI Not Ready

**Solution**: Wait for GSI to be active:

```bash
aws dynamodb describe-table \
  --table-name cg-chatbot-conversations \
  --query 'Table.GlobalSecondaryIndexes[0].IndexStatus' \
  --output text
```

---

## Data Management

### Backup Strategy

Enable point-in-time recovery:

```bash
aws dynamodb update-continuous-backups \
  --table-name cg-chatbot-conversations \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

### Export Conversations (for analysis)

```bash
# Export to S3 (requires S3 bucket)
aws dynamodb export-table-to-point-in-time \
  --table-arn arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/cg-chatbot-conversations \
  --s3-bucket my-export-bucket \
  --export-format DYNAMODB_JSON
```

---

## Next Steps

After DynamoDB setup is complete:
1. ✅ DynamoDB table created with GSI
2. ✅ Lambda IAM permissions configured
3. ➡️ Implement `conversations.py` for CRUD operations
4. ➡️ Test conversation persistence
5. ➡️ Integrate with LangGraph agent
