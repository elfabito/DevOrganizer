"""
Dev Project Organizer - Main Flask Application
A tool to help developers organize and plan new projects with AI assistance
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g, flash, make_response, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from flask_session import Session
from datetime import datetime, timedelta
import os
import json
import logging
from storage import ProjectStorage
from weekly_summary_storage import WeeklySummaryStorage
from user_storage import UserStorage
from clickup_service import get_clickup_service
from auth import AuthError, create_jwt_token, verify_password, login_required, get_current_user_id, get_token_from_header, decode_jwt_token
from ai_service import generate_plan, generate_weekly_summary, generate_feature_suggestions, generate_estimation
from functools import wraps
import uuid

# Add CSRF token verification function
def verify_csrf_token(token):
    """Verify the CSRF token"""
    if not token:
        return False
    
    # Get the current session's CSRF token
    session_csrf = session.get('_csrf_token')
    if not session_csrf:
        return False
        
    # For development, you can add a check to bypass CSRF for testing
    if current_app.debug and token == 'dev-bypass-csrf':
        return True
        
    # Compare the tokens
    return token == session_csrf

STORAGE_TYPE = 'sqlite'  # Options: 'json' or 'sqlite'
STORAGE_FILE = 'projects.db'

# Import storage based on configuration
if STORAGE_TYPE == 'sqlite':
    from storage_sqlite import ProjectStorageSQLite as StorageClass
else:
    from storage import ProjectStorage as StorageClass

# Initialize Flask app
app = Flask(__name__)

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath(STORAGE_FILE)}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize storage and user storage
storage = StorageClass(STORAGE_FILE)
user_storage = UserStorage(STORAGE_FILE)
weekly_storage = WeeklySummaryStorage(STORAGE_FILE)

# Load configuration from file if it exists
app.config.from_pyfile('config.py', silent=True)

# Environment configuration
app.config['ENV'] = os.getenv('FLASK_ENV', 'development')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', '1' if app.config['ENV'] == 'development' else '0').lower() in ('1', 'true', 'on')

# Session configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_FILE_DIR'] = os.path.abspath('./.flask_session')
app.config['SESSION_COOKIE_NAME'] = 'devorg_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to False for development
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # More permissive than 'Strict'
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_PROTECTION'] = 'basic'  # Less strict for development

# For development, ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True, mode=0o700)

# Clear any existing sessions that might be corrupted
if app.config.get('ENV') == 'development':
    import glob
    for f in glob.glob(os.path.join(app.config['SESSION_FILE_DIR'], 'sess_*')):
        try:
            os.remove(f)
        except Exception as e:
            app.logger.warning(f"Could not remove session file {f}: {e}")

# Security configuration
app.config['PREFERRED_URL_SCHEME'] = 'https' if os.getenv('HTTPS', '').lower() in ('true', '1', 'on') else 'http'

# Generate a secure secret key if not set
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    import secrets
    secret_key = secrets.token_hex(32)
    os.environ['FLASK_SECRET_KEY'] = secret_key
    with open('.env', 'a') as f:
        f.write(f'\nFLASK_SECRET_KEY={secret_key}\n')

app.secret_key = secret_key

# Ensure session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True, mode=0o700)

# Initialize Flask-Session
from flask_session import Session
Session(app)

# Import and initialize session utilities after app is created
from session_utils import init_session_config
init_session_config(app)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

@app.after_request
def after_request(response):
    from flask import session, request, current_app, g, url_for, redirect
    from session_utils import set_session_cookie, get_security_headers
    
    # Skip for static files, OPTIONS requests, and Chrome devtools
    if (request.endpoint == 'static' or 
        request.method == 'OPTIONS' or 
        request.path.startswith('/.well-known/') or
        request.path.startswith('/favicon.ico')):
        return response
    
    # Debug logging
    current_app.logger.debug(f"[AFTER_REQUEST] {request.method} {request.path}")
    current_app.logger.debug(f"[AFTER_REQUEST] Session: {dict(session)}")
    
    # Ensure session is properly initialized
    if 'user_id' in session:
        # Ensure g.user_id is set for the request context
        g.user_id = session['user_id']
        
        # Ensure the session is marked as modified to force saving
        session.modified = True
        
        # Set a persistent session
        session.permanent = True
        
    # Always generate a new CSRF token for each request
    csrf_token = generate_csrf()
    session['_csrf_token'] = csrf_token
    
    # Add CSRF token to response headers for all responses
    response.headers.set('X-CSRF-Token', csrf_token)
    
    # Set the session cookie with appropriate settings
    response.set_cookie(
        app.config['SESSION_COOKIE_NAME'],
        value=request.cookies.get(app.config['SESSION_COOKIE_NAME'], ''),
        httponly=app.config['SESSION_COOKIE_HTTPONLY'],
        secure=app.config['SESSION_COOKIE_SECURE'],
        samesite=app.config['SESSION_COOKIE_SAMESITE'],
        max_age=app.config['PERMANENT_SESSION_LIFETIME']
    )
    
    # Also set a cookie with the CSRF token
    response.set_cookie(
        'csrf_token',
        value=csrf_token,
        httponly=True,
        secure=app.config['SESSION_COOKIE_SECURE'],
        samesite=app.config['SESSION_COOKIE_SAMESITE']
    )
    
    current_app.logger.debug(f"[AFTER_REQUEST] Set CSRF token: {csrf_token[:8]}...")
    
    # If this is an AJAX request, make sure to include the token in the response
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax and response.is_json:
        try:
            data = response.get_json()
            if isinstance(data, dict):
                data['csrf_token'] = csrf_token
                response.set_data(json.dumps(data))
        except:
            pass
    
    # Check for active user session
    has_user_session = bool(session.get('_user_id') or session.get('user_id'))
    
    # For authenticated requests, ensure the session is saved
    if has_user_session and not getattr(session, 'modified', False):
        current_app.logger.debug("[AFTER_REQUEST] Ensuring session is saved for authenticated user")
        session.modified = True
    
    # Only save the session if it's modified or new, and we have a user session
    should_save = (
        getattr(session, 'modified', False) or  # Session was modified
        (has_user_session and not session.get('_fresh', False)) or  # Has user but not a fresh session
        (hasattr(session, '_new') and session._new)  # It's a new session
    )
    
    if should_save and has_user_session:  # Only save if we have a user session
        try:
            session.permanent = True
            session_interface = current_app.session_interface
            
            # Only save if it's not a null session
            if not session_interface.is_null_session(session):
                # Save the session
                session_interface.save_session(current_app, session, response)
                
                # Get the Set-Cookie header after saving
                set_cookie = response.headers.get('Set-Cookie', '')
                
                # If we have a user but no cookie, force set it
                if has_user_session and current_app.config['SESSION_COOKIE_NAME'] not in set_cookie:
                    current_app.logger.warning(
                        "[AFTER_REQUEST] Session cookie not set in response. "
                        f"Session modified: {getattr(session, 'modified', False)}, "
                        f"Has user: {has_user_session}"
                    )
                    
                    # Force set the session cookie with explicit settings
                    if hasattr(session, 'sid'):
                        cookie_name = current_app.config['SESSION_COOKIE_NAME']
                        cookie_domain = current_app.config.get('SESSION_COOKIE_DOMAIN')
                        cookie_secure = current_app.config.get('SESSION_COOKIE_SECURE', False)
                        cookie_httponly = current_app.config.get('SESSION_COOKIE_HTTPONLY', True)
                        cookie_samesite = current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
                        
                        response.set_cookie(
                            key=cookie_name,
                            value=session.sid,
                            max_age=int(timedelta(days=7).total_seconds()),
                            path=current_app.config.get('SESSION_COOKIE_PATH', '/'),
                            domain=cookie_domain,
                            secure=cookie_secure,
                            httponly=cookie_httponly,
                            samesite=cookie_samesite
                        )
                        
                        current_app.logger.debug(
                            f"[AFTER_REQUEST] Forced session cookie. "
                            f"Name: {cookie_name}, "
                            f"Secure: {cookie_secure}, "
                            f"HttpOnly: {cookie_httponly}, "
                            f"SameSite: {cookie_samesite}"
                        )
                
                current_app.logger.debug(
                    f"[AFTER_REQUEST] Session saved. Modified: {getattr(session, 'modified', False)}, "
                    f"User: {session.get('user_id', 'none')}"
                )
        except Exception as e:
            current_app.logger.error(
                f"[AFTER_REQUEST] Error saving session: {str(e)}", 
                exc_info=True
            )
    
    # Add security headers
    for header, value in get_security_headers().items():
        if header not in response.headers:
            response.headers[header] = value
    
    # Set cache control headers for all responses
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # Log response details for debugging
    current_app.logger.debug(f"[AFTER_REQUEST] Response status: {response.status}")
    
    return response



@app.route('/')
@login_required
def index():
    """
    Home page - displays list of all projects and estimations for the current user
    """
    from flask import session, current_app, redirect, url_for, render_template, request, jsonify
    from session_utils import get_current_user_id
    
    try:
        current_app.logger.debug("[INDEX] ===== Starting index route =====")
        current_app.logger.debug(f"[INDEX] Session data: {dict(session)}")
        current_app.logger.debug(f"[INDEX] Request headers: {dict(request.headers)}")
        
        # Get user from session
        user = session.get('user')
        user_id = session.get('user_id')
        
        current_app.logger.debug(f"[INDEX] Initial user from session - user: {bool(user)}, user_id: {user_id}")
        
        # Ensure user_id is a string (not a dictionary)
        if isinstance(user_id, dict):
            current_app.logger.warning("[INDEX] Found dictionary in user_id, extracting ID")
            user_id = user_id.get('id')
            if user_id:
                session['user_id'] = user_id
                current_app.logger.debug(f"[INDEX] Updated user_id in session: {user_id}")
        
        # If user data is not in session or user_id is invalid, try to get it from the database
        if not user and user_id:
            try:
                current_app.logger.debug(f"[INDEX] Fetching user from database with ID: {user_id}, type: {type(user_id)}")
                user = user_storage.get_user_by_id(str(user_id))
                if user:
                    current_app.logger.debug(f"[INDEX] Successfully retrieved user from database: {user.get('email')}")
                    # Update session with fresh user data
                    session['user'] = user
                    session['user_id'] = user['id']  # Ensure we store just the ID as a string
                    current_app.logger.debug("[INDEX] Updated session with user data from database")
                else:
                    current_app.logger.warning(f"[INDEX] No user found in database with ID: {user_id}")
            except Exception as e:
                current_app.logger.error(f"[INDEX] Error fetching user from database: {str(e)}", exc_info=True)
                user = None
        
        # If we still don't have a user, clear the session and redirect to login
        if not user or not user_id:
            current_app.logger.warning("[INDEX] No valid user data in session, redirecting to login")
            session.clear()
            flash('Your session has expired. Please log in again.', 'error')
            return redirect(url_for('web_login'))
        
        current_app.logger.debug(f"Loading projects for user_id: {user_id}")
        projects = []
        if hasattr(storage, 'load_user_projects'):
            projects = storage.load_user_projects(user_id)
            current_app.logger.debug(f"Loaded {len(projects)} projects for user_id {user_id}")
        else:
            current_app.logger.warning("Storage does not have load_user_projects method")
        
        # Sort by creation date (newest first)
        projects.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        current_app.logger.debug(f"Sorted projects: {[p.get('name') for p in projects]}")
        
        current_app.logger.debug("Loading user estimations...")
        estimations = storage.load_user_estimations(user_id) if hasattr(storage, 'load_user_estimations') else []
        
        # Get any flash messages
        messages = []
        with app.test_request_context():
            from flask import get_flashed_messages
            messages = get_flashed_messages(with_categories=True)
        
        current_app.logger.debug("Rendering index template...")
        return render_template('index.html', 
                             projects=projects, 
                             estimations=estimations,
                             current_user=user,
                             messages=messages)
    except Exception as e:
        current_app.logger.exception("Error in index route:")
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('error.html', 
                             error_message='Failed to load dashboard. Please try again.',
                             status_code=500), 500


@app.route('/create', methods=['GET'])
@login_required
def create_project_form():
    """
    Display the create project form
    """
    return render_template('create.html')


@app.route('/create-estimation', methods=['GET'])
@login_required
def create_estimation_form():
    """
    Display the create estimation form
    """
    return render_template('estimation_create.html')


@app.route('/web_login', methods=['GET', 'POST'])
def web_login():
    """
    Handle web login page display and form submission with improved session handling
    """
    from flask import session, redirect, url_for, request, render_template, flash, current_app, make_response, jsonify
    from session_utils import setup_user_session, set_session_cookie, clear_session
    
    # Handle GET request
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('auth/login.html')
    
    # Handle POST request
    try:
        # Get form data
        if request.headers.get('Content-Type') == 'application/json':
            data = request.get_json()
        else:
            data = request.form.to_dict()
            
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        remember = data.get('remember_me') == 'on'
        
        # Validate input
        if not email or not password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Email and password are required'}), 400
            flash('Email and password are required', 'error')
            return render_template('auth/login.html', email=email)
        
        # Get user from database
        user = user_storage.get_user_by_email(email)
        if not user or not verify_password(user.get('password_hash', ''), password):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Invalid email or password'}), 401
            flash('Invalid email or password', 'error')
            return render_template('auth/login.html', email=email)
        
        # Update last login
        try:
            user_storage.update_last_login(user['id'])
        except Exception as e:
            current_app.logger.error(f"Error updating last login: {str(e)}")
        
        # Set up user session
        user_data = {
            'id': str(user['id']),
            'email': user['email'],
            'name': user.get('name', ''),
            'created_at': user.get('created_at', ''),
            'updated_at': user.get('updated_at', ''),
            'is_active': bool(user.get('is_active', True))
        }
        
        setup_user_session(user_data)
        session.permanent = True
        current_app.permanent_session_lifetime = timedelta(days=30 if remember else 1)
        
        # Create JWT token
        token = create_jwt_token(str(user['id']))
        
        # Prepare response
        response_data = {
            'message': 'Login successful',
            'token': token,
            'user': user_data,
            'redirect': url_for('index')
        }
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(response_data)
            
        # For regular form submission
        response = redirect(url_for('index'))
        response.set_cookie(
            'token',
            token,
            httponly=True,
            secure=app.config.get('PREFERRED_URL_SCHEME', 'https') == 'https',
            samesite='Strict',
            max_age=30 * 24 * 60 * 60 if remember else None
        )
        return response
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'An error occurred during login'}), 500
        flash('An error occurred. Please try again.', 'error')
        return render_template('auth/login.html', email=request.form.get('email', ''))
@app.route('/web_signup', methods=['GET', 'POST'])
def web_signup():
    """Handle web form signup"""
    # If user is already logged in, redirect to home
    if 'user_id' in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'redirect': url_for('index')})
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Get form data
            if request.headers.get('Content-Type') == 'application/json':
                data = request.get_json()
            else:
                data = request.form.to_dict()
                
            email = data.get('email', '').strip().lower()
            name = data.get('name', '').strip()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')

            # Validate input
            if not all([email, name, password, confirm_password]):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'All fields are required'}), 400
                flash('All fields are required', 'error')
                return render_template('auth/signup.html', 
                                    email=email, 
                                    name=name)

            if password != confirm_password:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Passwords do not match'}), 400
                flash('Passwords do not match', 'error')
                return render_template('auth/signup.html',
                                    email=email,
                                    name=name)

            # Check if user already exists
            if user_storage.get_user_by_email(email):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Email already registered'}), 400
                flash('Email already registered', 'error')
                return render_template('auth/signup.html',
                                    email=email,
                                    name=name)

            # Hash the password before creating the user
            from auth import hash_password
            try:
                password_hash = hash_password(password)
                user_data = user_storage.create_user(email, name, password_hash)
                if not user_data or 'id' not in user_data:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': 'Failed to create user. Please try again.'}), 500
                    flash('Failed to create user. Please try again.', 'error')
                    return render_template('auth/signup.html',
                                        email=email,
                                        name=name)
            except Exception as e:
                current_app.logger.error(f"Error hashing password: {str(e)}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Error processing your request. Please try again.'}), 500
                flash('An error occurred. Please try again.', 'error')
                return render_template('auth/signup.html',
                                    email=email,
                                    name=name)

            # Get the newly created user using the ID from the returned user data
            user = user_storage.get_user_by_id(str(user_data['id']))
            if not user:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Failed to retrieve user after creation'}), 500
                flash('Failed to retrieve user after creation', 'error')
                return render_template('auth/signup.html',
                                    email=email,
                                    name=name)

            # Store user data in session
            session['user'] = user
            session['user_id'] = user['id']  # Use the ID from the user dictionary
            token = create_jwt_token(str(user['id']))
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'message': 'Registration successful',
                    'token': token,
                    'user': user,
                    'redirect': url_for('index')
                })
                
            flash('Registration successful!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            current_app.logger.error(f"Error during signup: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'An error occurred during signup. Please try again.'}), 500
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/signup.html',
                                email=request.form.get('email', ''),
                                name=request.form.get('name', ''))

    # GET request - show signup form
    return render_template('auth/signup.html')

@app.route('/logout')
def logout():
    """
    Logout endpoint - clears the user session, invalidates JWT tokens,
    and removes session cookies
    """
    from flask import session, redirect, url_for, request, current_app, g
    from session_utils import clear_session
    
    # Get the current user ID before clearing the session
    user_id = session.get('user_id') or session.get('_user_id')
    
    # Get token from cookie if exists
    token = request.cookies.get('token')
    
    # Invalidate the token if it exists
    if token:
        TokenBlacklist.add_to_blacklist(token)
    
    # Clear the session data and force a new session
    clear_session(force_new_session=True)
    
    # Create response to clear all auth-related cookies
    response = redirect(url_for('web_login'))
    
    # Clear all possible session data
    session.clear()
    
    # Clear Flask's g object
    if hasattr(g, 'user'):
        del g.user
    
    # Clear the token cookie with the exact same settings used in login
    response.delete_cookie(
        'token',
        path='/',
        domain=current_app.config.get('SESSION_COOKIE_DOMAIN', None),
        secure=current_app.config.get('PREFERRED_URL_SCHEME', 'https') == 'https',
        httponly=True,
        samesite='Strict',
        expires=0  # Expire immediately
    )
    
    # Clear the session cookie
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    
    # Clear session cookie with proper settings
    response.delete_cookie(
        session_cookie_name,
        path='/',
        domain=current_app.config.get('SESSION_COOKIE_DOMAIN', None),
        secure=current_app.config.get('PREFERRED_URL_SCHEME', 'https') == 'https',
        httponly=True,
        samesite='Strict',
        expires=0  # Expire immediately
    )
    
    # Clear any other potential session-related cookies
    for cookie_name in list(request.cookies.keys()):
        if cookie_name.startswith('session') or cookie_name.startswith('_session'):
            response.delete_cookie(
                cookie_name,
                path='/',
                domain=current_app.config.get('SESSION_COOKIE_DOMAIN', None)
            )
    
    # Force session to be regenerated
    session.regenerate()
    
    # Add headers to prevent caching of the page with the auth state
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, no-transform'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Log the logout
    if user_id:
        current_app.logger.info(f"[AUTH] User {user_id} logged out successfully")
    
    flash('You have been successfully logged out.', 'info')
    return response


@app.route('/api/auth/logout', methods=['POST'])
@login_required(api_auth=True)
def api_logout():
    """
    API logout endpoint - invalidates the current JWT token and clears session
    """
    from session_utils import clear_session
    
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    token = None
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        if token:
            # Add token to blacklist
            TokenBlacklist.add_to_blacklist(token)
    
    # Also check for token in cookies
    token_from_cookie = request.cookies.get('token')
    if token_from_cookie and token_from_cookie != token:
        TokenBlacklist.add_to_blacklist(token_from_cookie)
    
    # Clear the session data
    clear_session(force_new_session=True)
    
    # Create response
    response = jsonify({
        'status': 'success',
        'message': 'Successfully logged out',
        'redirect': url_for('web_login')
    })
    
    # Clear all possible auth cookies
    cookies_to_clear = [
        'token',
        current_app.config.get('SESSION_COOKIE_NAME', 'session')
    ]
    
    for cookie_name in cookies_to_clear:
        # Clear with explicit domain
        response.delete_cookie(
            cookie_name,
            path='/',
            domain=current_app.config.get('SESSION_COOKIE_DOMAIN', None),
            secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
            httponly=True,
            samesite=current_app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')
        )
        # Clear without domain (for subdomains)
        response.delete_cookie(cookie_name)
    
    # Add security headers
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

# Example usage in a route
@app.route('/check-user')
def check_user():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    exists = check_user_exists(email)
    return jsonify({'exists': exists, 'email': email})
@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """
    Get current user information from session
    """
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
            
        return jsonify({
            'id': session['user_id'],
            'email': session.get('user_email', ''),
            'name': session.get('user_name', '')
        })
        
    except Exception as e:
        current_app.logger.error(f"[AUTH] Error getting current user: {str(e)}")
        return jsonify({'error': 'Failed to get user information'}), 500


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """
    Handle API login requests with enhanced security and token management
    """
    try:
        data = request.get_json()
        if not data:
            current_app.logger.warning("[API LOGIN] No data provided in login request")
            return jsonify({'error': 'No data provided'}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        remember_me = data.get('remember_me', False)

        # Validate input
        if not email or not password:
            current_app.logger.warning("[API LOGIN] Missing email or password")
            return jsonify({'error': 'Email and password are required'}), 400

        # Get user from database
        user = user_storage.get_user_by_email(email)
        if not user or not verify_password(user.get('password_hash', ''), password):
            current_app.logger.warning(f"[API LOGIN] Failed login attempt for email: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        # Invalidate any existing tokens for this user (optional, for enhanced security)
        # This would require tracking tokens by user ID in the blacklist
        
        # Generate JWT token
        token = create_jwt_token(str(user['id']))
        
        # Log the login attempt
        current_app.logger.info(f"[API LOGIN] Successful login for user: {user['email']} (ID: {user['id']})")

        # Update last login
        try:
            user_storage.update_last_login(user['id'])
        except Exception as e:
            current_app.logger.error(f"[API LOGIN] Error updating last login: {str(e)}")

        # Prepare user data for response
        user_data = {
            'id': user['id'],
            'email': user['email'],
            'name': user.get('name', '')
        }
        
        # Create response
        response = jsonify({
            'message': 'Login successful',
            'token': token,
            'user': user_data
        })
        
        # Set secure cookie if remember_me is True
        if remember_me:
            secure = app.config.get('SESSION_COOKIE_SECURE', request.is_secure)
            response.set_cookie(
                'token',
                value=token,
                httponly=True,
                secure=secure,
                samesite='Lax',
                max_age=2592000,  # 30 days
                path='/'  # Important: must match the path used in other cookie operations
            )
            current_app.logger.debug("[API LOGIN] 'Remember me' cookie set")
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response

    except Exception as e:
        current_app.logger.error(f"[API LOGIN] Error during login: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred during login'}), 500


@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """Handle API user registration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()
        confirm_password = data.get('confirmPassword', data.get('confirm_password', '')).strip()
        remember_me = data.get('remember_me', False)

        # Validate input
        errors = {}
        if not name:
            errors['name'] = 'Name is required'
        if not email or '@' not in email:
            errors['email'] = 'Valid email is required'
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters long'
        if password != confirm_password:
            errors['confirmPassword'] = 'Passwords do not match'

        if errors:
            return jsonify({'errors': errors}), 400

        # Check if user exists
        if user_storage.get_user_by_email(email):
            return jsonify({'error': 'An account with this email already exists'}), 400

        # Create user
        from auth import hash_password
        password_hash = hash_password(password)
        user = user_storage.create_user(email, name, password_hash)

        if not user or 'id' not in user:
            return jsonify({'error': 'Failed to create user account'}), 500

        # Generate JWT token
        token = create_jwt_token(user['id'])

        response = jsonify({
            'message': 'Registration successful',
            'token': token,
            'user': {
                'id': user['id'],
                'email': email,
                'name': name
            }
        })
        
        # Set secure cookie if remember_me is True
        if remember_me:
            response.set_cookie(
                'token',
                value=token,
                httponly=True,
                secure=app.config.get('SESSION_COOKIE_SECURE', False),
                samesite='Lax',
                max_age=2592000,  # 30 days
                path='/'
            )
            
        return response, 201

    except Exception as e:
        current_app.logger.error(f"API signup error: {str(e)}")
        return jsonify({'error': 'An error occurred during registration. Please try again.'}), 500


    except Exception:
        pass

    return response

@app.route('/api/generate-plan', methods=['POST'])
@login_required
def generate_project_plan():
    """
    API endpoint to generate AI plan for a project
    Receives project name and description, returns AI-generated data
    """
    try:
        data = request.get_json()
        project_name = data.get('name', '').strip()
        project_description = data.get('description', '').strip()
        
        # Validate input
        if not project_name or not project_description:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400
        
        # Generate AI plan
        ai_data = generate_plan(project_name, project_description)
        
        return jsonify({
            'success': True,
            'ai_data': ai_data
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate plan: {str(e)}'
        }), 500


@app.route('/api/projects', methods=['POST'])
@login_required
def save_project():
    """
    Save a project with its AI-generated data
    """
    user_id = get_current_user_id()
    try:
        current_app.logger.debug(f"[SAVE_PROJECT] Starting save_project for user_id: {user_id}")
        data = request.get_json()
        project_name = data.get('name', '').strip()
        project_brief = data.get('brief', '').strip()
        ai_data = data.get('ai_data', {})
        
        current_app.logger.debug(f"[SAVE_PROJECT] Received data - name: {project_name}, brief: {project_brief}, ai_data keys: {list(ai_data.keys()) if isinstance(ai_data, dict) else 'not a dict'}")
        
        # Validate input
        if not project_name or not project_brief:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400
        
        if not ai_data:
            return jsonify({
                'error': 'AI data is required. Please generate a plan first.'
            }), 400
        
        # Prepare project data with user_id
        project_data = {
            'name': project_name,
            'brief': project_brief,
            'ai_data': ai_data,
            'user_id': user_id
        }
        
        # Save project
        saved_project = storage.save_project(project_data)
        
        return jsonify({
            'success': True,
            'project_id': saved_project['id'],
            'message': 'Project saved successfully!'
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        current_app.logger.error(f'Error saving project: {str(e)}\n{error_trace}')
        
        # Check if it's a database error
        if 'no such table' in str(e).lower():
            return jsonify({
                'error': 'Database error: Required tables not found. Please run database migrations.',
                'details': str(e)
            }), 500
            
        return jsonify({
            'error': f'Failed to save project: {str(e)}',
            'type': type(e).__name__
        }), 500


@app.route('/project/<project_id>')
@login_required
def view_project(project_id):
    """
    View detailed information about a specific project
    """
    try:
        user_id = get_current_user_id()
        project = storage.load_project(project_id)
        
        # Check if project exists and belongs to the user
        if not project or project.get('user_id') != user_id:
            return render_template('error.html', 
                                 error_code=404, 
                                 error_message='Project not found'), 404
            
        # Get current user for the template
        current_user = session.get('user')
        return render_template('project_detail.html', 
                             project=project, 
                             current_user=current_user)
        
    except Exception as e:
        return render_template('error.html', 
                             error_code=500, 
                             error_message=f'Error loading project: {str(e)}'), 500


@app.route('/delete-project/<project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    """
    Delete a project by ID
    """
    try:
        success = storage.delete_project(project_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Project deleted successfully'
            })
        else:
            return jsonify({
                'error': 'Project not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to delete project: {str(e)}'
        }), 500


@app.route('/create-weekly-summary', methods=['POST'])
@login_required
def create_weekly_summary():
    """
    Create a new weekly summary for a project
    """
    try:
        data = request.get_json()
        project_name = data.get('project_name', '').strip()
        
        if not project_name:
            return jsonify({
                'error': 'Project name is required'
            }), 400
        
        # Get the current user's ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                'error': 'User not authenticated'
            }), 401
        
        # Get the project ID from the project name
        conn = sqlite3.connect('projects.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM projects WHERE name = ? AND user_id = ?', (project_name, user_id))
        project = cursor.fetchone()
        conn.close()
        
        if not project:
            return jsonify({
                'error': f'Project "{project_name}" not found'
            }), 404
            
        project_id = project[0]
        
        # Create new weekly summary
        summary = weekly_storage.create_weekly_summary(project_id)
        
        return jsonify({
            'success': True,
            'summary_id': summary['id'],
            'message': 'Weekly summary created successfully!'
        })
        
    except Exception as e:
        current_app.logger.error(f'Error creating weekly summary: {str(e)}')
        return jsonify({
            'error': f'Failed to create weekly summary: {str(e)}'
        }), 500


@app.route('/weekly-summary/<summary_id>')
@login_required
def view_weekly_summary(summary_id):
    """
    View and edit a specific weekly summary
    """
    summary = weekly_storage.get_weekly_summary_by_id(summary_id)
    
    if not summary:
        return render_template('error.html', 
                             error_code=404, 
                             error_message='Weekly summary not found'), 404
    
    # Get list of all projects for the dropdown
    projects = storage.load_all_projects()
    project_names = [p['name'] for p in projects]
    
    # Find the project ID for the back button
    project_id = None
    for project in projects:
        if project['name'] == summary['project_name']:
            project_id = project['id']
            break
    
    return render_template('weekly_summary.html', summary=summary, project_names=project_names, project_id=project_id)


@app.route('/update-weekly-summary/<summary_id>', methods=['POST'])
@login_required
def update_weekly_summary(summary_id):
    """
    Update weekly summary notes
    """
    try:
        data = request.get_json()
        week_notes = data.get('week_notes')
        
        if not week_notes:
            return jsonify({
                'error': 'Week notes are required'
            }), 400
        
        # Update the summary
        success = weekly_storage.update_weekly_summary(summary_id, week_notes=week_notes)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Weekly notes saved successfully!'
            })
        else:
            return jsonify({
                'error': 'Weekly summary not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to update weekly summary: {str(e)}'
        }), 500


@app.route('/generate-week-summary', methods=['POST'])
@login_required
def generate_week_summary():
    """
    API endpoint to generate AI summary from weekly notes
    """
    try:
        data = request.get_json()
        summary_id = data.get('summary_id', '').strip()
        project_name = data.get('project_name', '').strip()
        week_notes = data.get('week_notes', {})
        
        if not project_name or not week_notes:
            return jsonify({
                'error': 'Project name and week notes are required'
            }), 400
        
        # Generate AI summary
        ai_summary = generate_weekly_summary(project_name, week_notes)
        
        # Update the summary in database if summary_id provided
        if summary_id:
            weekly_storage.update_weekly_summary(summary_id, ai_summary=ai_summary)
        
        return jsonify({
            'success': True,
            'summary': ai_summary
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate summary: {str(e)}'
        }), 500


@app.route('/delete-weekly-summary/<summary_id>', methods=['POST'])
@login_required
def delete_weekly_summary(summary_id):
    """
    Delete a weekly summary by ID
    """
    try:
        success = weekly_storage.delete_weekly_summary(summary_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Weekly summary deleted successfully'
            })
        else:
            return jsonify({
                'error': 'Weekly summary not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to delete weekly summary: {str(e)}'
        }), 500


@app.route('/generate-feature-suggestions', methods=['POST'])
@login_required
def generate_feature_suggestions_endpoint():
    """
    API endpoint to generate AI feature suggestions from project audit
    """
    try:
        data = request.get_json()
        project_id = data.get('project_id', '').strip()
        project_name = data.get('project_name', '').strip()
        audit_text = data.get('audit_text', '').strip()
        
        # Validate input
        if not project_id or not project_name:
            return jsonify({
                'error': 'Project ID and name are required'
            }), 400
        
        if not audit_text:
            return jsonify({
                'error': 'Project audit text is required'
            }), 400
        
        # Generate AI feature suggestions
        suggestions = generate_feature_suggestions(project_name, audit_text)
        
        # Save suggestions to database
        saved_suggestion = storage.save_feature_suggestions(
            project_id=project_id,
            project_name=project_name,
            audit_text=audit_text,
            suggestions=suggestions
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'suggestion_id': saved_suggestion['id']
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate feature suggestions: {str(e)}'
        }), 500


@app.route('/generate-estimation', methods=['POST'])
@login_required
def generate_estimation_endpoint():
    """
    API endpoint to generate AI project estimation
    """
    try:
        # Initialize response data with detailed debug info
        response_data = {
            'error': '',
            'details': '',
            'request_headers': dict(request.headers),
            'request_content_type': request.content_type,
            'request_method': request.method,
            'request_data': None,
            'debug_info': {
                'user_authenticated': bool(get_current_user_id()),
                'content_type': request.content_type,
                'content_length': request.content_length,
                'is_json': request.is_json,
                'form_data': dict(request.form) if request.form else None,
                'json_data': request.get_json(silent=True),
                'raw_data': request.get_data(as_text=True)[:1000] if request.data else None
            }
        }
        
        # Log the request details
        current_app.logger.info("=== New Estimation Request ===")
        current_app.logger.info(f"Method: {request.method}")
        current_app.logger.info(f"Content-Type: {request.content_type}")
        current_app.logger.info(f"Headers: {dict(request.headers)}")
        current_app.logger.info(f"Form data: {dict(request.form) if request.form else 'No form data'}")
        current_app.logger.info(f"JSON data: {request.get_json(silent=True) or 'No JSON data'}")
        
        # Extract data based on content type
        if request.is_json:
            data = request.get_json()
            current_app.logger.info("Processing JSON request data")
        elif request.form:
            data = {
                'project_name': request.form.get('projectName') or request.form.get('project_name'),
                'project_description': request.form.get('projectInfo') or request.form.get('project_description')
            }
            current_app.logger.info("Processing form request data")
        else:
            # Try to parse as JSON even if content-type is not set correctly
            try:
                data = request.get_json(force=True, silent=True)
                if data:
                    current_app.logger.info("Processed as JSON (forced)")
                else:
                    raise ValueError("No valid data found in request")
            except Exception as e:
                error_msg = f"Unsupported content type: {str(e)}. Please send JSON or form data"
                current_app.logger.error(error_msg, exc_info=True)
                response_data.update({
                    'error': 'Invalid request format',
                    'details': error_msg,
                    'debug_info': {
                        'content_type': request.content_type,
                        'content_length': request.content_length,
                        'request_headers': dict(request.headers),
                        'exception': str(e)
                    }
                })
                return jsonify(response_data), 400
        
        # Validate required fields
        if not data:
            error_msg = "No data provided in the request"
            current_app.logger.error(error_msg)
            response_data.update({
                'error': 'Missing data',
                'details': error_msg,
                'debug_info': {
                    'received_data': data,
                    'content_type': request.content_type,
                    'is_json': request.is_json
                }
            })
            return jsonify(response_data), 400
            
        # Extract and validate project name and description
        project_name = data.get('project_name', '').strip()
        project_description = data.get('project_description', '').strip()
        
        if not project_name:
            error_msg = "Project name is required"
            current_app.logger.error(error_msg)
            response_data.update({
                'error': 'Validation error',
                'details': error_msg,
                'debug_info': {
                    'received_data': data,
                    'missing_fields': ['project_name']
                }
            })
            return jsonify(response_data), 400
            
        if not project_description:
            error_msg = "Project description is required"
            current_app.logger.error(error_msg)
            response_data.update({
                'error': 'Validation error',
                'details': error_msg,
                'debug_info': {
                    'received_data': data,
                    'missing_fields': ['project_description']
                }
            })
            return jsonify(response_data), 400
            
        # Log successful data extraction
        current_app.logger.info(f"Successfully extracted data - Project: {project_name}")
        
        try:
            # Generate estimation using AI service
            current_app.logger.info(f"Generating estimation for project: {project_name}")
            estimation_data = generate_estimation(project_name, project_description)
            
            if not estimation_data:
                error_msg = "Failed to generate estimation: Empty response from AI service"
                current_app.logger.error(error_msg)
                response_data.update({
                    'error': 'Estimation generation failed',
                    'details': error_msg,
                    'debug_info': {
                        'project_name': project_name,
                        'project_description_length': len(project_description)
                    }
                })
                return jsonify(response_data), 500
                
            # Validate the AI response
            if not isinstance(estimation_data, dict):
                error_msg = f"Invalid response format from AI service. Expected dictionary, got {type(estimation_data).__name__}"
                current_app.logger.error(error_msg)
                response_data.update({
                    'error': 'Invalid response format',
                    'details': error_msg,
                    'debug_info': {
                        'ai_response_type': type(estimation_data).__name__,
                        'ai_response': str(estimation_data)[:500]  # Log first 500 chars
                    }
                })
                return jsonify(response_data), 500
                
            # Check for required fields in the AI response
            required_fields = ['phases', 'total_hours']
            missing_fields = [field for field in required_fields if field not in estimation_data]
            
            if missing_fields:
                error_msg = f"Missing required fields in AI response: {', '.join(missing_fields)}"
                current_app.logger.error(error_msg)
                response_data.update({
                    'error': 'Incomplete AI response',
                    'details': error_msg,
                    'debug_info': {
                        'missing_fields': missing_fields,
                        'available_fields': list(estimation_data.keys())
                    }
                })
                return jsonify(response_data), 500
                
            # Prepare the estimation data for saving
            estimation_data = {
                'project_name': project_name,
                'project_description': project_description,
                'phases': estimation_data['phases'],
                'total_hours': int(estimation_data['total_hours']),
                'user_id': get_current_user_id(),
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Save the estimation
            saved_estimation = storage.save_estimation(estimation_data)
            
            if not saved_estimation or 'id' not in saved_estimation:
                error_msg = "Failed to save estimation to database"
                current_app.logger.error(error_msg)
                response_data.update({
                    'error': 'Database error',
                    'details': error_msg,
                    'debug_info': {
                        'estimation_data': estimation_data,
                        'saved_estimation': saved_estimation
                    }
                })
                return jsonify(response_data), 500
            
            # Return success response
            response_data.update({
                'success': True,
                'estimation_id': saved_estimation['id'],
                'phases': estimation_data['phases'],
                'total_hours': estimation_data['total_hours']
            })
            return jsonify(response_data), 201
            
        except Exception as e:
            error_msg = f"Error generating estimation: {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            response_data.update({
                'error': 'Internal server error',
                'details': 'An unexpected error occurred while generating the estimation',
                'debug_info': {
                    'exception': str(e),
                    'exception_type': type(e).__name__,
                    'project_name': project_name,
                    'project_description_length': len(project_description) if project_description else 0
                }
            })
            return jsonify(response_data), 500
            
    except Exception as e:
        error_msg = f"Unexpected error in generate_estimation_endpoint: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'details': 'An unexpected error occurred',
            'debug_info': {
                'exception': str(e),
                'exception_type': type(e).__name__,
                'raw_request_data': str(request.data)[:500] if request.data else None,
                'content_type': request.content_type,
                'request_data': str(request.data)[:500] if request.data else None
            }
        }), 500



@app.route('/estimation/<string:estimation_id>')
@login_required
def view_estimation(estimation_id):
    """
    View detailed information about a specific estimation
    """
    try:
        # Debug logging
        from flask import session
        from session_utils import get_current_user_id
        
        # Get current user ID using the session utility
        user_id = get_current_user_id()
        if not user_id:
            current_app.logger.warning("[ESTIMATION_VIEW] No valid user session, redirecting to login")
            return redirect(url_for('web_login'))
            
        current_app.logger.debug(f"[ESTIMATION_VIEW] Session data: {dict(session)}")
        current_app.logger.debug(f"[ESTIMATION_VIEW] Current user_id: {user_id}")
        
        try:
            # Get the current user from the database
            current_user = user_storage.get_user_by_id(user_id)
            if not current_user:
                current_app.logger.error(f"[ESTIMATION_VIEW] User {user_id} not found in database")
                flash('User account not found', 'error')
                return redirect(url_for('web_login'))
                
            current_app.logger.debug(f"[ESTIMATION_VIEW] Current user from DB: {current_user}")
            
        except Exception as e:
            current_app.logger.error(f"[ESTIMATION_VIEW] Error fetching user data: {str(e)}", exc_info=True)
            flash('Error loading user data', 'error')
            return redirect(url_for('index'))
        
        if not current_user:
            current_app.logger.warning("[ESTIMATION_VIEW] User not found in database, clearing session")
            from session_utils import clear_session
            clear_session()
            return redirect(url_for('web_login'))
            
        estimation = storage.get_estimation_by_id(estimation_id)
        
        if not estimation:
            return render_template('error.html', 
                                error_code=404, 
                                error_message='Estimation not found'), 404
        
        # Verify the estimation belongs to the current user
        if str(estimation.get('user_id')) != str(g.user_id):
            return render_template('error.html',
                                error_code=403,
                                error_message='You do not have permission to view this estimation'), 403
        
        return render_template('estimation_detail.html', 
                             estimation=estimation,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error viewing estimation {estimation_id}: {str(e)}")
        return render_template('error.html',
                            error_code=500,
                            error_message='An error occurred while loading the estimation'), 500


@app.route('/delete-estimation/<string:estimation_id>', methods=['POST'])
@login_required
def delete_estimation(estimation_id):
    """
    Delete an estimation by ID
    """
    try:
        # Get the storage instance
        storage = get_storage()
        
        # First get the estimation to verify ownership
        estimation = storage.get_estimation_by_id(estimation_id)
        if not estimation:
            return jsonify({'error': 'Estimation not found'}), 404
            
        # Verify the estimation belongs to the current user
        if str(estimation.get('user_id')) != str(g.user_id):
            current_app.logger.warning(f"User {g.user_id} attempted to delete estimation {estimation_id} without permission")
            return jsonify({'error': 'You do not have permission to delete this estimation'}), 403
            
        # Delete the estimation
        success = storage.delete_estimation(estimation_id)
        
        if not success:
            return jsonify({'error': 'Failed to delete estimation'}), 500
            
        current_app.logger.info(f"Estimation {estimation_id} deleted by user {g.user_id}")
        
        # Return success response
        return jsonify({
            'success': True, 
            'message': 'Estimation deleted successfully',
            'redirect': url_for('index')
        })
        
    except Exception as e:
        current_app.logger.error(f'Error deleting estimation {estimation_id}: {str(e)}', exc_info=True)
        return jsonify({
            'error': 'An error occurred while deleting the estimation',
            'details': str(e)
        }), 500


@app.route('/refine-estimation/<string:estimation_id>', methods=['POST'])
@login_required
def refine_estimation(estimation_id):
    """
    Refine an existing estimation based on user feedback
    """
    current_app.logger.info(f"Refine estimation request received for ID: {estimation_id}")
    
    # Verify the estimation exists and belongs to the current user
    estimation = storage.get_estimation(estimation_id)
    if not estimation:
        return jsonify({'error': 'Estimation not found'}), 404
        
    if str(estimation.get('user_id')) != str(g.user_id):
        current_app.logger.warning(f"User {g.user_id} attempted to refine estimation {estimation_id} without permission")
        return jsonify({'error': 'You do not have permission to refine this estimation'}), 403
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # For AJAX requests, we'll return JSON, otherwise we'll redirect
    def error_response(message, status_code=400):
        if is_ajax:
            return jsonify({'error': message}), status_code
        flash(message, 'error')
        return redirect(request.referrer or url_for('index'))
    
    # Ensure request is JSON for API calls
    if is_ajax and not request.is_json:
        current_app.logger.error("AJAX request is not JSON")
        return error_response('Content-Type must be application/json')
    
    # Get the CSRF token from header or form data
    csrf_token = request.headers.get('X-CSRFToken') or request.json.get('csrf_token') if request.is_json else request.form.get('csrf_token')
    
    # Verify CSRF token
    if not csrf_token or not verify_csrf_token(csrf_token):
        current_app.logger.warning("Invalid or missing CSRF token")
        return error_response('Invalid or missing CSRF token', 403)

    try:
        data = request.get_json()
        feedback = data.get('feedback', '').strip()
        current_app.logger.info(f"Feedback received (first 100 chars): {feedback[:100]}")
        
        if not feedback:
            return jsonify({
                'error': 'Feedback is required to refine the estimation'
            }), 400
            
        # Get the original estimation
        storage = StorageClass(STORAGE_FILE)
        estimation = storage.get_estimation(estimation_id)
        
        if not estimation:
            current_app.logger.error(f"Estimation not found: {estimation_id}")
            return jsonify({
                'error': 'Estimation not found'
            }), 404

        # Verify the current user owns this estimation
        current_user_id = get_current_user_id()
        if str(estimation.get('user_id')) != str(current_user_id):
            current_app.logger.error(f"Unauthorized access attempt by user {current_user_id} for estimation {estimation_id}")
            return jsonify({
                'error': 'Unauthorized: You do not have permission to modify this estimation'
            }), 403
            
        try:
            # Call the AI service to refine the estimation
            from ai_service import generate_estimation_refinement
            current_app.logger.info("Generating estimation refinement...")
            
            refined_estimation = generate_estimation_refinement(
                estimation['project_name'],
                estimation['project_description'],
                estimation,
                feedback
            )
            
            if not refined_estimation or not isinstance(refined_estimation, dict):
                raise ValueError("Invalid response from AI service")
                
            # Add metadata to the refined estimation
            refined_estimation.update({
                'updated_at': datetime.utcnow().isoformat(),
                'refined_from': estimation_id,
                'user_id': current_user_id
            })
            
            # Save as a new estimation or update existing one based on your requirements
            # Here we'll update the existing one
            try:
                updated = storage.update_estimation(estimation_id, refined_estimation)
                if not updated:
                    raise Exception("Storage update failed")
                    
                current_app.logger.info(f"Successfully refined estimation {estimation_id}")
                return jsonify({
                    'success': True,
                    'estimation': refined_estimation
                })
                
            except Exception as e:
                current_app.logger.error(f"Failed to update estimation in storage: {str(e)}", exc_info=True)
                return jsonify({
                    'error': 'Failed to save refined estimation',
                    'details': str(e) if current_app.debug else 'An error occurred while saving the refined estimation'
                }), 500
            
        except ImportError as e:
            current_app.logger.error(f"Failed to load AI service: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Failed to load AI service',
                'details': str(e)
            }), 500
            
        except Exception as e:
            current_app.logger.error(f"Error during estimation refinement: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Failed to generate refined estimation',
                'details': str(e) if current_app.debug else 'An error occurred while generating the refined estimation'
            }), 500
            
    except Exception as e:
        import traceback
        error_msg = f'Unexpected error in refine_estimation: {str(e)}\n{traceback.format_exc()}'
        current_app.logger.error(error_msg)
        return jsonify({
            'error': 'An unexpected error occurred',
            'details': str(e) if current_app.debug else 'Please try again later.'
        }), 500


@app.route('/clickup/check-config', methods=['GET'])
@login_required
def check_clickup_config():
    """
    Check if ClickUp API token is configured in environment
    """
    try:
        clickup = get_clickup_service()
        has_token = bool(clickup.api_token and clickup.api_token.strip())
        
        return jsonify({
            'configured': has_token,
            'message': 'Token configured in .env' if has_token else 'No token configured'
        })
    except Exception as e:
        return jsonify({
            'configured': False,
            'error': str(e)
        }), 500


@app.route('/clickup/workspaces', methods=['GET'])
@login_required
def get_clickup_workspaces():
    """
    Get all ClickUp workspaces for the authenticated user
    """
    try:
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Check if token is configured
        if not clickup.api_token:
            return jsonify({
                'error': 'ClickUp API token not configured. Please add it to .env file or provide it in the request.'
            }), 401
        
        # Fetch workspaces
        result = clickup.get_workspaces()
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch workspaces: {str(e)}'
        }), 500


@app.route('/clickup/spaces/<team_id>', methods=['GET'])
@login_required
def get_clickup_spaces(team_id):
    """
    Get all spaces (projects) within a ClickUp workspace
    """
    try:
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Fetch spaces
        result = clickup.get_spaces(team_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch spaces: {str(e)}'
        }), 500


@app.route('/clickup/shared-lists/<team_id>', methods=['GET'])
@login_required
def get_clickup_shared_lists(team_id):
    """
    Get all lists shared with the user in a workspace
    """
    try:
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Fetch shared lists
        result = clickup.get_shared_lists(team_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch shared lists: {str(e)}'
        }), 500


@app.route('/clickup/folders/<space_id>', methods=['GET'])
@login_required
def get_clickup_folders(space_id):
    """
    Get all folders within a ClickUp space
    """
    try:
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Fetch folders
        result = clickup.get_folders(space_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch folders: {str(e)}'
        }), 500


@app.route('/clickup/lists/<space_id>', methods=['GET'])
@app.route('/clickup/lists/<space_id>/<folder_id>', methods=['GET'])
@login_required
def get_clickup_lists(space_id, folder_id=None):
    """
    Get all lists within a ClickUp space or folder
    """
    try:
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Fetch lists
        result = clickup.get_lists(space_id, folder_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch lists: {str(e)}'
        }), 500


@app.route('/clickup/create-tasks', methods=['POST'])
@login_required
def create_clickup_tasks():
    """
    Create tasks in ClickUp from project phases
    """
    try:
        data = request.get_json()
        list_id = data.get('list_id')
        phases = data.get('phases', [])
        
        # Get API token from request header, or use environment variable
        api_token = request.headers.get('X-ClickUp-Token') or None
        
        # Validate input
        if not list_id:
            return jsonify({
                'error': 'List ID is required'
            }), 400
        
        if not phases:
            return jsonify({
                'error': 'No tasks to create'
            }), 400
        
        # Get ClickUp service
        clickup = get_clickup_service(api_token)
        
        # Create tasks
        result = clickup.create_tasks_from_phases(list_id, phases)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to create tasks: {str(e)}'
        }), 500


@app.route('/health')
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'app': 'Dev Project Organizer',
        'version': '1.0.0'
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('error.html', 
                         error_code=404, 
                         error_message='Page not found'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('error.html',
                         error_code=500,
                         error_message='Internal server error'), 500

@app.errorhandler(AuthError)
def handle_auth_error(ex):
    """Handle authentication errors"""
    response = jsonify({
        'error': ex.message,
        'status_code': ex.status_code
    })
    response.status_code = ex.status_code
    return response


@app.route('/api/projects/<project_id>/section-states', methods=['GET'])
@login_required
def get_section_states(project_id):
    """
    Get all section states for a project
    """
    try:
        print(f"Fetching section states for project: {project_id}")
        section_states = storage.get_section_states(project_id)
        print(f"Retrieved section states: {section_states}")
        
        if section_states is None:
            print("No section states found, returning empty dict")
            section_states = {}
            
        return jsonify({
            'status': 'success',
            'section_states': section_states
        })
        
    except Exception as e:
        error_msg = f'Failed to load section states: {str(e)}'
        print(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'error_type': type(e).__name__
        }), 500

@app.route('/api/projects/<project_id>/section-states/<section_id>', methods=['POST'])
def save_section_state(project_id, section_id):
    """
    Save the state of a section for a project
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided in request'
            }), 400
            
        is_expanded = data.get('is_expanded', False)
        
        print(f"Saving section state - Project: {project_id}, Section: {section_id}, Expanded: {is_expanded}")
        
        success = storage.save_section_state(project_id, section_id, is_expanded)
        
        if success:
            print("Section state saved successfully")
            return jsonify({
                'status': 'success',
                'message': 'Section state saved successfully'
            })
        else:
            error_msg = 'Failed to save section state to database'
            print(error_msg)
            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 500
            
    except Exception as e:
        error_msg = f'Failed to save section state: {str(e)}'
        print(error_msg)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'error_type': type(e).__name__
        }), 500

# Exempt API routes from CSRF protection
csrf.exempt(generate_project_plan)
csrf.exempt(generate_week_summary)
csrf.exempt(generate_feature_suggestions_endpoint)
csrf.exempt(generate_estimation_endpoint)
csrf.exempt(generate_estimation_endpoint)

if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)
    
    # Ensure database exists and run migrations
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, 'projects.db')
    
    # Ensure the database directory exists and is writable
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    print(f"Using database at: {db_path}")
    
    # Run migrations
    try:
        from migrate_db import migrate_database
        print("Running database migrations...")
        migrate_database(db_path)
        print("Database migrations completed successfully")
    except Exception as e:
        print(f"Error running database migrations: {str(e)}")
        print("Please check database permissions and try again")
        import sys
        sys.exit(1)
    
    # Print startup message
    print("🚀 Dev Project Organizer Starting...")
    print("=" * 60)
    print(f"📂 Database: {db_path}")
    print("🌐 Server: http://127.0.0.1:5000")
    print("=" * 60)
    
    # Start the development server
    app.run(debug=True, host='127.0.0.1', port=5000)
