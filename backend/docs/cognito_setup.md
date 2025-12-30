# AWS Cognito User Pool Setup Guide

This guide walks through setting up AWS Cognito for user authentication with a demo account for portfolio access.

## Overview

AWS Cognito will handle:
- User registration and authentication
- JWT token generation and validation
- Demo account for public portfolio access
- Password policies and security

---

## Step 1: Create Cognito User Pool

### Using AWS Console

1. **Navigate to Cognito**:
   - Go to [Cognito Console](https://console.aws.amazon.com/cognito/)
   - Click **"Create user pool"**

2. **Configure Sign-in Experience**:
   - **Provider types**: Cognito user pool
   - **Cognito user pool sign-in options**: ✅ Email
   - Click **"Next"**

3. **Configure Security Requirements**:
   - **Password policy**: Cognito defaults (min 8 chars, uppercase, lowercase, numbers, special chars)
   - **Multi-factor authentication**: No MFA (for demo simplicity)
   - **User account recovery**: Email only
   - Click **"Next"**

4. **Configure Sign-up Experience**:
   - **Self-registration**: Enable (allow users to sign up)
   - **Required attributes**: Email
   - **Custom attributes**: None needed
   - Click **"Next"**

5. **Configure Message Delivery**:
   - **Email provider**: Send email with Cognito (free tier: 50 emails/day)
   - **FROM email address**: no-reply@verificationemail.com (default)
   - Click **"Next"**

6. **Integrate Your App**:
   - **User pool name**: `cg-production-assistant-users`
   - **Hosted authentication pages**: No (we'll use custom Gradio UI)
   - **Initial app client**:
     - **App client name**: `cg-assistant-client`
     - **Client secret**: Don't generate (public client)
     - **Authentication flows**: ✅ ALLOW_USER_PASSWORD_AUTH
   - Click **"Next"**

7. **Review and Create**:
   - Review settings
   - Click **"Create user pool"**

### Using AWS CLI

Create user pool:

```bash
aws cognito-idp create-user-pool \
  --pool-name cg-production-assistant-users \
  --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=true}" \
  --auto-verified-attributes email \
  --username-attributes email \
  --region us-east-1
```

Save the `UserPoolId` from the output.

Create app client:

```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id YOUR_USER_POOL_ID \
  --client-name cg-assistant-client \
  --no-generate-secret \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --region us-east-1
```

Save the `ClientId` from the output.

---

## Step 2: Create Demo Account

Create a demo user that can be shared publicly for portfolio access.

### Using AWS Console

1. **Navigate to User Pool**:
   - Go to Cognito → User pools → `cg-production-assistant-users`
   - Click **"Users"** tab → **"Create user"**

2. **Configure Demo User**:
   - **Email**: `demo@cgassistant.com`
   - **Temporary password**: Generate a temporary password
   - **Mark email as verified**: ✅ Yes
   - Click **"Create user"**

3. **Set Permanent Password**:
   - After creation, click on the user
   - Click **"Actions"** → **"Reset password"**
   - Set password to: `DemoPass10!`
   - **Mark as permanent**: ✅ Yes

### Using AWS CLI

```bash
# Create demo user
aws cognito-idp admin-create-user \
  --user-pool-id YOUR_USER_POOL_ID \
  --username demo@cgassistant.com \
  --user-attributes Name=email,Value=demo@cgassistant.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region us-east-1

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id YOUR_USER_POOL_ID \
  --username demo@cgassistant.com \
  --password "DemoPass10!" \
  --permanent \
  --region us-east-1
```

---

## Step 3: Get Cognito Configuration Details

You'll need these values for Lambda and frontend configuration.

### Using AWS Console

1. **User Pool ID**:
   - Cognito → User pools → `cg-production-assistant-users`
   - Copy the **User pool ID** (e.g., `us-east-1_abc123xyz`)

2. **App Client ID**:
   - Click **"App integration"** tab
   - Under **App clients**, copy the **Client ID**

3. **Region**:
   - `us-east-1` (or your chosen region)

### Using AWS CLI

```bash
# List user pools
aws cognito-idp list-user-pools --max-results 10 --region us-east-1

# Get user pool details
aws cognito-idp describe-user-pool \
  --user-pool-id YOUR_USER_POOL_ID \
  --region us-east-1

# List app clients
aws cognito-idp list-user-pool-clients \
  --user-pool-id YOUR_USER_POOL_ID \
  --region us-east-1
```

---

## Step 4: Update Lambda Environment Variables

Add Cognito configuration to Lambda.

### Using AWS Console

1. Go to Lambda function `cg-production-chatbot`
2. Click **"Configuration"** → **"Environment variables"** → **"Edit"**
3. Add:
   - **Key**: `COGNITO_USER_POOL_ID`
   - **Value**: `us-east-1_abc123xyz` (your pool ID)
   - **Key**: `COGNITO_CLIENT_ID`
   - **Value**: `your-client-id`
   - **Key**: `COGNITO_REGION`
   - **Value**: `us-east-1`
4. Click **"Save"**

### Using AWS CLI

```bash
aws lambda update-function-configuration \
  --function-name cg-production-chatbot \
  --environment "Variables={COGNITO_USER_POOL_ID=us-east-1_abc123xyz,COGNITO_CLIENT_ID=your-client-id,COGNITO_REGION=us-east-1,...}" \
  --region us-east-1
```

---

## Step 5: Test Authentication

### Test Demo Login

Once `auth.py` is implemented, test authentication:

```python
import boto3

client = boto3.client('cognito-idp', region_name='us-east-1')

# Authenticate demo user
response = client.initiate_auth(
    ClientId='YOUR_CLIENT_ID',
    AuthFlow='USER_PASSWORD_AUTH',
    AuthParameters={
        'USERNAME': 'demo@cgassistant.com',
        'PASSWORD': 'DemoPass10!'
    }
)

# Get tokens
id_token = response['AuthenticationResult']['IdToken']
access_token = response['AuthenticationResult']['AccessToken']
refresh_token = response['AuthenticationResult']['RefreshToken']

print(f"ID Token: {id_token[:50]}...")
```

### Test JWT Validation

```python
from auth import extract_user_from_token

# Extract user ID from token
user_id = extract_user_from_token(id_token)
print(f"User ID: {user_id}")  # Should be: demo@cgassistant.com
```

---

## Frontend Integration

### Gradio Authentication Flow

```python
import boto3
import gradio as gr

cognito_client = boto3.client('cognito-idp', region_name='us-east-1')
CLIENT_ID = 'your-client-id'

def login(email, password):
    """Authenticate user and return JWT token."""
    try:
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password
            }
        )
        return response['AuthenticationResult']['IdToken']
    except Exception as e:
        return f"Login failed: {str(e)}"

def demo_login():
    """Quick login with demo account."""
    return login('demo@cgassistant.com', 'DemoPass10!')

# Gradio UI
with gr.Blocks() as demo:
    with gr.Row():
        email = gr.Textbox(label="Email")
        password = gr.Textbox(label="Password", type="password")
        login_btn = gr.Button("Login")
    
    demo_btn = gr.Button("🎭 Demo Login")
    token_output = gr.Textbox(label="Auth Token", visible=False)
    
    login_btn.click(login, inputs=[email, password], outputs=token_output)
    demo_btn.click(demo_login, outputs=token_output)
```

---

## JWT Token Structure

Cognito ID tokens contain user information:

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "email_verified": true,
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc123xyz",
  "cognito:username": "demo@cgassistant.com",
  "aud": "your-client-id",
  "email": "demo@cgassistant.com",
  "exp": 1735578000,
  "iat": 1735574400
}
```

Extract `sub` (subject) or `cognito:username` as the `user_id`.

---

## Security Considerations

### Password Policy

Current policy requires:
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character

Demo password `DemoPass10!` meets all requirements.

### Token Expiration

- **ID Token**: 1 hour (default)
- **Access Token**: 1 hour (default)
- **Refresh Token**: 30 days (default)

Frontend should handle token refresh:

```python
def refresh_token(refresh_token):
    response = cognito_client.initiate_auth(
        ClientId=CLIENT_ID,
        AuthFlow='REFRESH_TOKEN_AUTH',
        AuthParameters={
            'REFRESH_TOKEN': refresh_token
        }
    )
    return response['AuthenticationResult']['IdToken']
```

### Demo Account Limitations

For portfolio security:
- Demo account has same permissions as regular users
- Consider adding rate limiting in Lambda for demo user
- Monitor demo account usage in CloudWatch

---

## Cost Estimation

### Cognito Pricing

- **Free tier**: 50,000 MAUs (Monthly Active Users)
- **Beyond free tier**: $0.0055 per MAU

For portfolio demo: **$0.00/month** (well within free tier)

---

## Troubleshooting

### "NotAuthorizedException: Incorrect username or password"

**Check**:
1. Email is correct: `demo@cgassistant.com`
2. Password is correct: `DemoPass10!`
3. User exists: `aws cognito-idp admin-get-user --user-pool-id YOUR_POOL_ID --username demo@cgassistant.com`

### "InvalidParameterException: USER_PASSWORD_AUTH flow not enabled"

**Solution**: Enable auth flow in app client:

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id YOUR_USER_POOL_ID \
  --client-id YOUR_CLIENT_ID \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH
```

### "User is not confirmed"

**Solution**: Confirm user manually:

```bash
aws cognito-idp admin-confirm-sign-up \
  --user-pool-id YOUR_USER_POOL_ID \
  --username demo@cgassistant.com
```

---

## Next Steps

After Cognito setup is complete:
1. ✅ User pool created with demo account
2. ✅ App client configured
3. ➡️ Implement `auth.py` for JWT validation
4. ➡️ Update Lambda to extract user_id from tokens
5. ➡️ Add authentication UI to Gradio frontend
