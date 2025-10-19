"""
Authentication service for DevOrganizer
Handles user registration, login, and JWT token management
"""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, Tuple
from functools import wraps
from flask import request, jsonify, g, session, current_app, make_response

# Import token utilities
from token_utils import TokenBlacklist, decode_jwt_token

# Configuration
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24  # Token expires in 24 hours

class AuthError(Exception):
    """Base authentication error"""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

def hash_password(password: str) -> str:
    """Hash a password for storing in the database"""
    if not password:
        raise ValueError("Password cannot be empty")
    
    if not isinstance(password, (str, bytes)):
        raise TypeError("Password must be a string or bytes")
    
    try:
        # Ensure password is bytes
        if isinstance(password, str):
            password = password.encode('utf-8')
            
        # Generate salt and hash
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password, salt)
        
        # Return as string for storage
        return hashed.decode('utf-8')
    except Exception as e:
        current_app.logger.error(f"Error hashing password: {str(e)}")
        raise

def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify a stored password against one provided by user"""
    if not stored_hash or not provided_password:
        return False
    
    try:
        # Ensure the stored hash is properly encoded
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        
        # Ensure the provided password is properly encoded
        if isinstance(provided_password, str):
            provided_password = provided_password.encode('utf-8')
        
        # Verify the password
        return bcrypt.checkpw(provided_password, stored_hash)
    except (ValueError, Exception) as e:
        current_app.logger.error(f"Password verification error: {str(e)}")
        return False

def create_jwt_token(user_id: str) -> str:
    """Create a JWT token for a user"""
    payload = {
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow(),
        'sub': user_id
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token
    
    Args:
        token: The JWT token to decode
        
    Returns:
        Dict containing user_id (as 'sub') and expiration time
        
    Raises:
        AuthError: If token is invalid, expired, or blacklisted
    """
    try:
        if not token:
            raise AuthError('No token provided', 401)
            
        # Decode the token
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]}
        )
        
        # Check if token is blacklisted
        if is_token_blacklisted(token):
            raise AuthError('Token has been revoked', 401)
            
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuthError('Token has expired', 401)
    except (jwt.InvalidTokenError, jwt.PyJWTError) as e:
        raise AuthError(f'Invalid token: {str(e)}', 401)
    except Exception as e:
        current_app.logger.error(f'Error decoding token: {str(e)}')
        raise AuthError('Could not validate credentials', 500)

def is_token_blacklisted(token: str) -> bool:
    """
    Check if a token is in the blacklist
    
    Args:
        token: The JWT token to check
        
    Returns:
        bool: True if token is blacklisted, False otherwise
    """
    # In a production environment, you would check this against a database
    # For this implementation, we'll return False (no tokens blacklisted)
    return False


def get_token_from_header() -> Optional[str]:
    """
    Get and validate JWT token from request headers or cookies
    
    Returns:
        str: The token if valid, None otherwise
    """
    # First check for token in Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            # Expecting: 'Bearer <token>'
            parts = auth_header.split()
            if parts[0].lower() != 'bearer' or len(parts) != 2:
                current_app.logger.warning("[AUTH] Invalid Authorization header format")
                return None
                
            token = parts[1]
            try:
                # This will raise AuthError if token is invalid
                payload = decode_jwt_token(token)
                current_app.logger.debug(f"[AUTH] Valid token for user {payload['user_id']}")
                return token
            except AuthError as e:
                current_app.logger.warning(f"[AUTH] Token validation failed: {e.message}")
                return None
                
        except Exception as e:
            current_app.logger.error(f"[AUTH] Error processing Authorization header: {str(e)}")
            return None
    
    # Fall back to session-based auth for web requests
    if 'user_id' in session:
        current_app.logger.debug("[AUTH] User authenticated via session")
        return session.get('user_id')
        
    return None

def login_required(f=None, api_auth=False):
    """
    Decorator to require authentication for a route.
    
    Args:
        f: The view function to decorate
        api_auth: If True, requires JWT token authentication (for API endpoints).
                 If False, uses session-based authentication (for web endpoints).
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import redirect, url_for, request, session, current_app, g, flash, jsonify
            
            # Debug logging
            current_app.logger.debug(
                f"[AUTH] {'API' if api_auth else 'Web'} auth check for: "
                f"{request.method} {request.path}"
            )
            
            # Public paths that don't require authentication
            public_paths = ['/web_login', '/web_signup', '/static/', '/favicon.ico', '/.well-known/']
            
            # Check if current path is public
            is_public = any(
                request.path == path.rstrip('/') or 
                request.path.startswith(path) 
                for path in public_paths
            )
            
            # Allow access to public routes and static files
            if is_public or request.endpoint in ('web_login', 'web_signup', 'static'):
                return f(*args, **kwargs)
            
            # Handle API authentication
            if api_auth:
                token = get_token_from_header()
                if not token:
                    return jsonify({'error': 'Authentication required'}), 401
                
                try:
                    # This validates the token and checks blacklist
                    payload = decode_jwt_token(token)
                    g.user_id = payload['sub']  # JWT uses 'sub' for subject/user ID
                    current_app.logger.debug(f"[AUTH] API request authenticated for user {g.user_id}")
                    return f(*args, **kwargs)
                except KeyError as e:
                    current_app.logger.error(f"JWT payload missing required field: {str(e)}")
                    return jsonify({'error': 'Invalid token format'}), 401
                except AuthError as e:
                    return jsonify({'error': e.message}), e.status_code
            
            # Handle web session authentication
            else:
                # Check if user is logged in via session
                if 'user_id' not in session and '_user_id' not in session:
                    current_app.logger.warning(
                        f"[AUTH] No user_id in session. "
                        f"Endpoint: {request.endpoint}, "
                        f"Path: {request.path}, "
                        f"Session keys: {list(session.keys())}, "
                        f"Cookies: {request.cookies}"
                    )
                    # Store the intended URL before redirecting to login
                    session['next'] = request.url
                    return redirect(url_for('web_login'))
                
                # Get user_id from either 'user_id' or '_user_id' for backward compatibility
                user_id = session.get('user_id') or session.get('_user_id')
                if not user_id:
                    current_app.logger.warning("[AUTH] Session exists but no user_id found")
                    session.clear()
                    return redirect(url_for('web_login'))
                    
                # Set user_id in g for the request context
                g.user_id = user_id
                
                # Store user info in g for access in routes
                g.user_id = session['user_id']
                current_app.logger.debug(f"[AUTH] Web user {g.user_id} authenticated")
                
                # Handle redirect after login if needed
                if 'next' in session and request.endpoint == 'index':
                    next_url = session.pop('next', None)
                    if next_url and not next_url.endswith(('web_login', 'web_signup')):
                        current_app.logger.debug(f"[AUTH] Redirecting to original URL: {next_url}")
                        return redirect(next_url)
                
                return f(*args, **kwargs)
        
        return decorated_function
    
    # Handle both @login_required and @login_required(api_auth=True) syntax
    if f is None:
        return decorator
    return decorator(f)

def get_current_user_id():
    """
    Get the current user ID from the session.
    
    Returns:
        str: The current user ID if authenticated, None otherwise
    """
    # First check if we have a JWT token (for API requests)
    token = get_token_from_header()
    if token:
        try:
            payload = decode_jwt_token(token)
            user_id = payload.get('user_id')
            if user_id:
                g.user_id = str(user_id)
                return g.user_id
        except AuthError:
            pass  # Fall through to session check
    
    # For web requests, check the session
    if not session:
        current_app.logger.debug("[AUTH] No active session")
        return None
    
    # Check both possible session keys for user_id
    user_id = session.get('user_id') or session.get('_user_id')
    if not user_id:
        current_app.logger.debug("[AUTH] No user_id in session")
        return None
    
    # Cache in g for subsequent calls in the same request
    g.user_id = str(user_id)
    return g.user_id