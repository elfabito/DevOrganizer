"""
Centralized session management utilities
Handles all session-related operations consistently across the application
"""
import os
from datetime import timedelta
from flask import current_app, session, g, make_response
import logging

def init_session_config(app):
    """Initialize session configuration with proper directory setup and permissions"""
    import stat
    import tempfile
    
    # Configuración básica de la sesión
    session_dir = os.path.abspath('./.flask_session')
    
    # Determinar si estamos en producción (puedes personalizar esta lógica según tu entorno)
    is_production = os.getenv('FLASK_ENV', 'development').lower() == 'production'
    
    # Determinar si estamos usando HTTPS (por defecto True en producción, False en desarrollo)
    is_https = is_production or os.getenv('HTTPS', '').lower() in ('true', '1', 'on')
    
    try:
        # Crear el directorio si no existe
        os.makedirs(session_dir, exist_ok=True, mode=0o700)
        
        # Verificar permisos de escritura
        test_file = os.path.join(session_dir, '.permission_test')
        try:
            # Probar escritura
            with open(test_file, 'w') as f:
                f.write('test')
            # Probar lectura
            with open(test_file, 'r') as f:
                f.read()
            # Limpiar
            os.unlink(test_file)
            app.logger.info(f"[SESSION] Directory {session_dir} is writable")
        except Exception as e:
            app.logger.error(f"[SESSION] Cannot write to session directory {session_dir}: {str(e)}")
            # Si no podemos escribir, usar un directorio temporal
            temp_dir = os.path.join(tempfile.gettempdir(), 'devorganizer_sessions')
            os.makedirs(temp_dir, exist_ok=True, mode=0o700)
            session_dir = temp_dir
            app.logger.warning(f"[SESSION] Using temporary directory: {session_dir}")
        
        # Configuración de la aplicación
        app.config.update(
            # Session settings
            SESSION_TYPE='filesystem',
            SESSION_FILE_DIR=session_dir,
            SESSION_PERMANENT=True,
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
            
            # Cookie settings
            SESSION_COOKIE_NAME='devorg_session',
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SECURE=is_https,  # True en producción con HTTPS
            SESSION_COOKIE_SAMESITE='Lax',
            SESSION_USE_SIGNER=True,
            
            # Required for session to work
            SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production'),
            
            # Session protection
            SESSION_PROTECTION='basic',
            
            # Ensure session is saved on each request
            SESSION_REFRESH_EACH_REQUEST=True,
            
            # Session file system settings
            SESSION_FILE_THRESHOLD=500,
            SESSION_FILE_MODE=0o600,
            
            # Session serialization
            SESSION_JSON_SORT_KEYS=True,
            
            # Additional security settings
            PREFERRED_URL_SCHEME='https' if is_https else 'http',
            
            # Trust X-Forwarded-* headers from proxies
            # IMPORTANTE: Solo habilitar si estás detrás de un proxy de confianza
            PROXYFIX_X_FOR=1 if is_production else 0,
            PROXYFIX_X_PROTO=1 if is_production else 0,
            PROXYFIX_X_HOST=1 if is_production else 0,
            PROXYFIX_X_PORT=1 if is_production else 0,
            PROXYFIX_X_PREFIX=1 if is_production else 0
        )
        
        # Configuración específica para producción
        if is_production:
            app.config.update(
                # Forzar HTTPS en producción
                SESSION_COOKIE_SECURE=True,
                # Usar SameSite=Lax o Strict en producción
                SESSION_COOKIE_SAMESITE='Lax',
                # Deshabilitar el modo debug
                DEBUG=False,
                # Configuración adicional de seguridad
                TRAP_HTTP_EXCEPTIONS=True,
                TRAP_BAD_REQUEST_ERRORS=True
            )
            
            # Configurar el proxy fix si es necesario
            if is_https:
                from werkzeug.middleware.proxy_fix import ProxyFix
                app.wsgi_app = ProxyFix(
                    app.wsgi_app,
                    x_for=1,  # Número de proxies confiables
                    x_proto=1,
                    x_host=1,
                    x_port=1,
                    x_prefix=1
                )
                app.logger.info("[CONFIG] ProxyFix enabled for HTTPS")
        
        app.logger.info(f"[CONFIG] Session cookie secure: {app.config['SESSION_COOKIE_SECURE']}")
        app.logger.info(f"[CONFIG] Running in {'production' if is_production else 'development'} mode")
        app.logger.info(f"[CONFIG] Using HTTPS: {is_https}")
        
        app.logger.info(f"[SESSION] Session directory: {session_dir}")
        
    except Exception as e:
        app.logger.error(f"[SESSION] Failed to initialize session directory: {str(e)}")
        raise

def clear_session(force_new_session=False):
    """Clear all session data and optionally force a new session
    
    Args:
        force_new_session: If True, generates a new session ID after clearing
    """
    if not session:
        return
        
    current_app.logger.debug("[SESSION] Clearing session data")
    
    # Get the current session ID for logging
    old_sid = getattr(session, 'sid', None)
    
    try:
        # Clear the session data
        session.clear()
        
        # Force a new session ID if requested
        if force_new_session:
            if hasattr(session, 'regenerate'):
                session.regenerate()
                current_app.logger.debug(f"[SESSION] Regenerated session ID: {getattr(session, 'sid', 'unknown')}")
            
        # Mark as modified to ensure save
        session.modified = True
        
        # Create a response object to save the session
        response = make_response()
        session_interface = current_app.session_interface
        
        # Save the empty session
        session_interface.save_session(current_app, session, response)
        
        # If we have a response with Set-Cookie header, log it
        set_cookie = response.headers.get('Set-Cookie', '')
        current_app.logger.debug(
            f"[SESSION] Cleared session (old_sid: {old_sid}), "
            f"new_sid: {getattr(session, 'sid', 'none')}, "
            f"set_cookie: {'yes' if set_cookie else 'no'}"
        )
        
        # Clean up any user-related globals
        if hasattr(g, 'user_id'):
            delattr(g, 'user_id')
            
    except Exception as e:
        current_app.logger.error(f"[SESSION] Error clearing session: {str(e)}", exc_info=True)
        # En este punto no podemos restaurar old_session ya que no la guardamos
        # pero podemos forzar una nueva sesión en el próximo request
        if hasattr(session, 'regenerate'):
            session.regenerate()
            current_app.logger.debug("[SESSION] Regenerated session after error")
 
def set_session_cookie(response, session_id):
    """
    Set session cookie with consistent settings from app config.
    
    Args:
        response: Flask response object
        session_id: Session ID to set in the cookie
        
    Returns:
        Updated response object with cookie set
    """
    if not current_app:
        raise RuntimeError("Cannot set session cookie: current_app is not available")
    
    # Get cookie configuration from app config
    cookie_config = {
        'key': current_app.config['SESSION_COOKIE_NAME'],
        'value': session_id,
        'max_age': int(current_app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()),
        'path': current_app.config.get('SESSION_COOKIE_PATH', '/'),
        'domain': current_app.config.get('SESSION_COOKIE_DOMAIN'),
        'secure': current_app.config['SESSION_COOKIE_SECURE'],
        'httponly': current_app.config['SESSION_COOKIE_HTTPONLY'],
        'samesite': current_app.config['SESSION_COOKIE_SAMESITE']
    }
    
    # Remove None values to avoid errors
    cookie_config = {k: v for k, v in cookie_config.items() if v is not None}
    
    # Log cookie settings for debugging
    current_app.logger.debug(f"[SESSION] Setting session cookie with config: {cookie_config}")
    
    # Set the cookie
    response.set_cookie(**cookie_config)
    
    # Verify cookie was set
    set_cookie = response.headers.get('Set-Cookie')
    if not set_cookie or current_app.config['SESSION_COOKIE_NAME'] not in set_cookie:
        current_app.logger.error(
            f"[SESSION] Failed to set session cookie. "
            f"Set-Cookie header: {set_cookie}"
        )
    
    return response

def setup_user_session(user):
    """Set up user session with standard fields and ensure it's saved"""
    if not user or 'id' not in user or 'email' not in user:
        current_app.logger.error("[SESSION] Invalid user data provided to setup_user_session")
        raise ValueError("Invalid user data")
    
    try:
        # Clear existing session data
        session.clear()
        
        # Ensure we have a clean session
        if hasattr(session, 'regenerate'):
            session.regenerate()
        
        # Store user ID as a string in user_id
        user_id = str(user['id'])
        
        # Set session data - only store the user ID in session['user_id']
        session.permanent = True
        session['_fresh'] = True
        session['_permanent'] = True
        session['_user_id'] = user_id  # Used by Flask-Login
        session['user_id'] = user_id   # Our own field for consistency
        
        # Store user data in a separate key
        session['user'] = {
            'id': user_id,
            'email': user['email'],
            'name': user.get('name', ''),
            'created_at': user.get('created_at', ''),
            'updated_at': user.get('updated_at', ''),
            'is_active': bool(user.get('is_active', True))
        }
        
        # Mark session as modified
        session.modified = True
        
        # Log the session data for debugging
        current_app.logger.debug(f"[SESSION] Setting up session for user_id: {user['id']}")
        current_app.logger.debug(f"[SESSION] Session data: {dict(session)}")
        
        # Save the session
        try:
            # Create a response object to save the session
            from flask import make_response
            response = make_response()
            
            # Get the session interface
            session_interface = current_app.session_interface
            
            # Save the session
            session_interface.save_session(current_app, session, response)
            
            # Verify the session was saved
            if not session_interface.is_null_session(session):
                current_app.logger.debug("[SESSION] Session saved successfully")
                
                # Log the Set-Cookie header for debugging
                set_cookie = response.headers.get('Set-Cookie', '')
                current_app.logger.debug(f"[SESSION] Set-Cookie header: {set_cookie}")
                
                # If we're in development, log additional debug info
                if current_app.config.get('DEBUG'):
                    current_app.logger.debug(f"[SESSION DEBUG] Session ID: {getattr(session, 'sid', 'unknown')}")
                    current_app.logger.debug(f"[SESSION DEBUG] Session directory: {current_app.config.get('SESSION_FILE_DIR')}")
            else:
                current_app.logger.error("[SESSION] Failed to save session - null session returned")
                
            return session
                
        except Exception as e:
            current_app.logger.error(f"[SESSION] Error saving session: {str(e)}", exc_info=True)
            raise
            
    except Exception as e:
        current_app.logger.error(f"[SESSION] Error in setup_user_session: {str(e)}", exc_info=True)
        # Re-raise the exception to be handled by the caller
        raise

def get_security_headers():
    """Return a dictionary of security headers with appropriate CSP settings"""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': 
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
    }

def get_current_user_id():
    """Get current user ID from session with validation"""
    # If we've already set g.user_id in this request, return it
    if hasattr(g, 'user_id'):
        current_app.logger.debug(f"[AUTH] Returning user_id from g: {g.user_id}")
        return g.user_id
        
    # Log session contents for debugging
    if not session:
        current_app.logger.warning("[AUTH] Session is empty")
    else:
        current_app.logger.debug(f"[AUTH] Session contents: {dict(session)}")
    
    # Try to get user_id from session (check both _user_id and user_id for compatibility)
    user_id = session.get('user_id') or session.get('_user_id')
    current_app.logger.debug(f"[AUTH] Retrieved user_id from session: {user_id}")
    
    if user_id:
        try:
            user_id = str(user_id).strip()
            if not user_id:
                current_app.logger.warning("[AUTH] Empty user_id in session")
                return None
                
            current_app.logger.debug(f"[AUTH] Processed user_id: {user_id}")

            # Verify the user exists in the database.
            # Use the application's user_storage instance (defined in app.py)
            # Import here to avoid circular imports at module import time.
            try:
                from app import user_storage
            except Exception:
                # Fallback: try module-level helper (older code paths)
                try:
                    from user_storage import UserStorage
                    # create a temp storage only if needed (rare)
                    user_storage = UserStorage()
                except Exception:
                    current_app.logger.exception("[AUTH] Could not access user storage to validate session user_id")
                    clear_session()
                    return None

            user = None
            try:
                user = user_storage.get_user_by_id(user_id)
            except Exception as e:
                current_app.logger.error(f"[AUTH] Error querying user storage: {str(e)}", exc_info=True)

            if user:
                # Store in g for subsequent calls in the same request
                g.user_id = user_id
                current_app.logger.debug(f"[AUTH] Found valid user_id in session: {user_id}")
                return user_id
            else:
                current_app.logger.warning(f"[AUTH] User ID {user_id} not found in database")
                clear_session()

        except Exception as e:
            current_app.logger.error(f"[AUTH] Error getting user ID from session: {str(e)}", exc_info=True)
            clear_session()

    return None
