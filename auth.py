"""
Authentication service for DevOrganizer
Handles user registration, login, and session management
"""
import bcrypt
from functools import wraps
from flask import g, session, current_app

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

# JWT token functions removed - using Flask-Session only

def login_required(f=None):
    """
    Decorator to require authentication for a route using Flask-Session only.
    Works for both web pages and API endpoints.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import redirect, url_for, request, session, current_app, g, jsonify

            # Public paths that don't require authentication
            if request.endpoint in ('web_login', 'web_signup', 'static'):
                return f(*args, **kwargs)

            # Check if user is logged in via session
            user_id = session.get('user_id') or session.get('_user_id')

            if not user_id:
                current_app.logger.warning(f"[AUTH] No user_id in session for {request.path}")

                # For API endpoints and AJAX requests, return JSON error
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if request.path.startswith('/api/') or is_ajax or request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401

                # For web pages, redirect to login
                # Only save 'next' if it's not already set OR if it's different from current URL
                # This prevents loops where 'next' gets stuck with the same URL
                current_next = session.get('next')
                if not current_next or current_next != request.url:
                    # Don't save '/web_login' as next URL - this would cause a loop
                    if request.path != '/web_login':
                        session['next'] = request.url
                        session.modified = True
                        current_app.logger.debug(f"[AUTH] Saved next URL: {request.url}")

                return redirect(url_for('web_login'))

            # Set user_id in g for the request context
            g.user_id = str(user_id)
            current_app.logger.debug(f"[AUTH] User {g.user_id} authenticated")

            return f(*args, **kwargs)

        return decorated_function

    # Handle both @login_required and @login_required() syntax
    if f is None:
        return decorator
    return decorator(f)

def get_current_user_id():
    """
    Get the current user ID from the session.

    Returns:
        str: The current user ID if authenticated, None otherwise
    """
    # Check if already cached in g
    if hasattr(g, 'user_id'):
        return g.user_id

    # Get from session
    user_id = session.get('user_id') or session.get('_user_id')
    if user_id:
        g.user_id = str(user_id)
        return g.user_id

    return None