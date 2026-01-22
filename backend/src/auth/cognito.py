"""
Authentication utilities for AWS Cognito JWT validation.
Handles token validation and user ID extraction.
"""

import os
import logging
import json
from typing import Optional, Dict, Any
import boto3
from jose import jwt, JWTError
from jose.backends import RSAKey
import requests
from functools import lru_cache

logger = logging.getLogger()

# Cognito configuration
COGNITO_REGION = os.environ.get('COGNITO_REGION', 'us-east-1')
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')
COGNITO_CLIENT_SECRET = os.environ.get('COGNITO_CLIENT_SECRET')

# Cognito URLs
COGNITO_ISSUER = f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}'
COGNITO_JWKS_URL = f'{COGNITO_ISSUER}/.well-known/jwks.json'


@lru_cache(maxsize=1)
def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Fetch Cognito public keys for JWT validation (cached).
    
    Returns:
        Dictionary of public keys indexed by 'kid'
    """
    try:
        response = requests.get(COGNITO_JWKS_URL, timeout=5)
        response.raise_for_status()
        jwks = response.json()
        
        # Index keys by 'kid' for easy lookup
        keys = {}
        for key in jwks.get('keys', []):
            keys[key['kid']] = key
        
        logger.info(f"Loaded {len(keys)} Cognito public keys")
        return keys
        
    except Exception as e:
        logger.error(f"Error fetching Cognito public keys: {str(e)}", exc_info=True)
        return {}


def validate_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate Cognito JWT token and return claims.
    
    Args:
        token: JWT token string (ID token from Cognito)
        
    Returns:
        Token claims dict if valid, None if invalid
        
    Example:
        >>> claims = validate_token(id_token)
        >>> print(claims['email'])
        'demo@cgassistant.com'
    """
    try:
        # Get token header to find the key ID
        headers = jwt.get_unverified_headers(token)
        kid = headers.get('kid')
        
        if not kid:
            logger.error("Token missing 'kid' in header")
            return None
        
        # Get public key
        public_keys = get_cognito_public_keys()
        public_key = public_keys.get(kid)
        
        if not public_key:
            logger.error(f"Public key not found for kid: {kid}")
            return None
        
        # Verify and decode token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER
        )
        
        logger.info(f"Token validated for user: {claims.get('cognito:username', 'unknown')}")
        return claims
        
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error validating token: {str(e)}", exc_info=True)
        return None


def extract_user_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from Cognito JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID (email or sub), or None if invalid
        
    Example:
        >>> user_id = extract_user_from_token(id_token)
        >>> print(user_id)
        'demo@cgassistant.com'
    """
    claims = validate_token(token)
    
    if not claims:
        return None
    
    # Use email as user_id (or could use 'sub' for UUID)
    user_id = claims.get('email') or claims.get('cognito:username') or claims.get('sub')
    
    return user_id


def is_demo_user(user_id: str) -> bool:
    """
    Check if user is the demo account.
    
    Args:
        user_id: User identifier
        
    Returns:
        True if demo user, False otherwise
    """
    return user_id == 'demo@cgassistant.com'


def compute_secret_hash(username: str) -> str:
    """
    Compute SECRET_HASH for Cognito authentication.
    Required when the app client has a client secret.
    
    Args:
        username: Username (email) for authentication
        
    Returns:
        Base64-encoded HMAC-SHA256 hash
    """
    import hmac
    import hashlib
    import base64
    
    if not COGNITO_CLIENT_SECRET:
        raise ValueError("COGNITO_CLIENT_SECRET not configured")
    
    message = username + COGNITO_CLIENT_ID
    dig = hmac.new(
        COGNITO_CLIENT_SECRET.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    
    return base64.b64encode(dig).decode()


def authenticate_user(email: str, password: str) -> Optional[Dict[str, str]]:
    """
    Authenticate user with Cognito and return tokens.
    This is for frontend use, not Lambda validation.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        Dict with 'id_token', 'access_token', 'refresh_token', or None if auth fails
        
    Example:
        >>> tokens = authenticate_user('demo@cgassistant.com', 'DemoPass10!')
        >>> print(tokens['id_token'][:50])
        'eyJraWQiOiJ...'
    """
    try:
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        
        # Prepare auth parameters
        auth_params = {
            'USERNAME': email,
            'PASSWORD': password
        }
        
        # Add SECRET_HASH if client secret is configured
        if COGNITO_CLIENT_SECRET:
            auth_params['SECRET_HASH'] = compute_secret_hash(email)
        
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters=auth_params
        )
        
        auth_result = response.get('AuthenticationResult')
        
        if not auth_result:
            logger.error("Authentication failed: No AuthenticationResult in response")
            return None
        
        return {
            'id_token': auth_result['IdToken'],
            'access_token': auth_result['AccessToken'],
            'refresh_token': auth_result['RefreshToken']
        }
        
    except cognito_client.exceptions.NotAuthorizedException:
        logger.error(f"Authentication failed for user {email}: Invalid credentials")
        return None
    except Exception as e:
        logger.error(f"Error authenticating user {email}: {str(e)}", exc_info=True)
        return None


def signup_user(email: str, password: str) -> Dict[str, Any]:
    """
    Create a new user in Cognito.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        Dict with 'success', 'message', 'user_confirmed', and optionally 'tokens'
        
    Example:
        >>> result = signup_user('newuser@example.com', 'SecurePass123!')
        >>> if result['success']:
        ...     print("Account created!")
    """
    try:
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        
        # Prepare signup parameters
        signup_params = {
            'ClientId': COGNITO_CLIENT_ID,
            'Username': email,
            'Password': password,
            'UserAttributes': [
                {'Name': 'email', 'Value': email}
            ]
        }
        
        # Add SECRET_HASH if client secret is configured
        if COGNITO_CLIENT_SECRET:
            signup_params['SecretHash'] = compute_secret_hash(email)
        
        response = cognito_client.sign_up(**signup_params)
        
        user_confirmed = response.get('UserConfirmed', False)
        
        # Auto-confirm user if not already confirmed
        if not user_confirmed:
            try:
                cognito_client.admin_confirm_sign_up(
                    UserPoolId=COGNITO_USER_POOL_ID,
                    Username=email
                )
                user_confirmed = True
                logger.info(f"Auto-confirmed user {email}")
            except Exception as confirm_error:
                logger.error(f"Failed to auto-confirm user {email}: {confirm_error}")
                # Continue anyway - user can still verify via email
        
        if user_confirmed:
            # User is confirmed, try to authenticate and return tokens
            tokens = authenticate_user(email, password)
            if tokens:
                return {
                    'success': True,
                    'message': 'Account created and logged in!',
                    'user_confirmed': True,
                    'tokens': tokens
                }
            else:
                return {
                    'success': True,
                    'message': 'Account created! Please log in.',
                    'user_confirmed': True
                }
        else:
            return {
                'success': True,
                'message': 'Account created! Please check your email to verify your account.',
                'user_confirmed': False
            }
        
    except cognito_client.exceptions.UsernameExistsException:
        return {
            'success': False,
            'message': 'An account with this email already exists.'
        }
    except cognito_client.exceptions.InvalidPasswordException as e:
        return {
            'success': False,
            'message': f'Password does not meet requirements: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Error signing up user {email}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'Signup error: {str(e)}'
        }


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, str]]:
    """
    Refresh access token using refresh token.
    
    Args:
        refresh_token: Refresh token from previous authentication
        
    Returns:
        Dict with new 'id_token' and 'access_token', or None if refresh fails
    """
    try:
        cognito_client = boto3.client('cognito-idp', region_name=COGNITO_REGION)
        
        response = cognito_client.initiate_auth(
            ClientId=COGNITO_CLIENT_ID,
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token
            }
        )
        
        auth_result = response.get('AuthenticationResult')
        
        if not auth_result:
            return None
        
        return {
            'id_token': auth_result['IdToken'],
            'access_token': auth_result['AccessToken']
        }
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
        return None


def extract_user_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract user ID from Lambda event (API Gateway request).
    Checks Authorization header for Bearer token.
    
    Args:
        event: Lambda event dict from API Gateway
        
    Returns:
        User ID if valid token, None otherwise
        
    Example:
        >>> user_id = extract_user_from_event(event)
        >>> print(user_id)
        'demo@cgassistant.com'
    """
    # Get Authorization header
    headers = event.get('headers', {})
    auth_header = headers.get('Authorization') or headers.get('authorization')
    
    if not auth_header:
        logger.warning("No Authorization header found")
        return None
    
    # Extract token from "Bearer <token>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        logger.warning("Invalid Authorization header format")
        return None
    
    token = parts[1]
    return extract_user_from_token(token)
