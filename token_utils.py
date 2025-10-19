"""
Token management utilities for JWT token handling and blacklisting
"""
import jwt
from datetime import datetime, timedelta
from flask import current_app
from storage_sqlite import get_db_connection

class TokenBlacklist:
    """Handles JWT token blacklisting and validation"""
    
    @classmethod
    def add_to_blacklist(cls, token):
        """Add a token to the blacklist"""
        try:
            # Decode the token to get expiration time
            payload = jwt.decode(
                token, 
                current_app.config.get('JWT_SECRET_KEY', current_app.secret_key),
                algorithms=['HS256'],
                options={"verify_exp": False}  # Don't verify expiration yet
            )
            
            # Calculate token expiration time
            expires_at = datetime.utcfromtimestamp(payload['exp'])
            
            # Add to blacklist
            conn = get_db_connection()
            try:
                conn.execute(
                    'INSERT INTO token_blacklist (token, expires_at) VALUES (?, ?)',
                    (token, expires_at)
                )
                conn.commit()
                current_app.logger.debug(f"Token added to blacklist, expires at {expires_at}")
                return True
            finally:
                conn.close()
                
        except Exception as e:
            current_app.logger.error(f"Error adding token to blacklist: {str(e)}")
            return False
    
    @classmethod
    def is_blacklisted(cls, token):
        """Check if a token is in the blacklist"""
        if not token:
            return False
            
        conn = get_db_connection()
        try:
            # Check if token is in blacklist
            result = conn.execute(
                'SELECT id FROM token_blacklist WHERE token = ?',
                (token,)
            ).fetchone()
            
            # Clean up expired tokens while we're here
            if not result:
                cls._cleanup_expired_tokens(conn)
                
            return result is not None
        except Exception as e:
            current_app.logger.error(f"Error checking token blacklist: {str(e)}")
            return True  # Fail closed - if we can't check, assume token is blacklisted
        finally:
            conn.close()
    
    @classmethod
    def _cleanup_expired_tokens(cls, conn):
        """Remove expired tokens from the blacklist"""
        try:
            conn.execute(
                'DELETE FROM token_blacklist WHERE expires_at < ?',
                (datetime.utcnow(),)
            )
            conn.commit()
        except Exception as e:
            current_app.logger.error(f"Error cleaning up expired tokens: {str(e)}")
            conn.rollback()

def decode_jwt_token(token):
    """Decode and verify a JWT token, checking blacklist"""
    from auth import AuthError
    
    try:
        # First check if token is blacklisted
        if TokenBlacklist.is_blacklisted(token):
            raise AuthError('Token has been invalidated', 401)
            
        # Then verify the token
        payload = jwt.decode(
            token, 
            current_app.config.get('JWT_SECRET_KEY', current_app.secret_key),
            algorithms=['HS256']
        )
        
        return {
            'user_id': payload['sub'],
            'exp': payload['exp']
        }
    except jwt.ExpiredSignatureError:
        raise AuthError('Token has expired', 401)
    except jwt.InvalidTokenError as e:
        raise AuthError(f'Invalid token: {str(e)}', 401)
    except Exception as e:
        raise AuthError('Failed to authenticate token', 401)
