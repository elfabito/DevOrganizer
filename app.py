"""
Dev Project Organizer - Main Flask Application
A tool to help developers organize and plan new projects with AI assistance
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g, flash, make_response, current_app, send_from_directory
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
import os
import logging
import calendar
from storage_redis import RedisProjectStorage, RedisUserStorage
from clickup_service import get_clickup_service
from auth import AuthError, verify_password, login_required, get_current_user_id
from ai_service import generate_plan, generate_weekly_summary, generate_feature_suggestions, generate_estimation
from functools import wraps
import uuid
import redis
from daily_notes_storage import DailyNotesStorage
from PIL import Image
from cloudinary_service import cloudinary_service
from stripe_service import (
    create_checkout_session,
    create_customer_portal_session,
    handle_webhook_event,
    get_stripe_config
)
from subscription_limits import (
    check_resource_limit,
    require_plan,
    get_user_plan_limits,
    can_use_clickup
)
from linear_service import LinearService, validate_linear_token
from oauth_service import init_oauth, get_google_user_info, get_github_user_info

from dotenv import load_dotenv
load_dotenv('.env') 
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


# Initialize Flask app
app = Flask(__name__)

# Configure ProxyFix for Render (nginx reverse proxy)
# This is critical for HTTPS detection behind a proxy
# x_for=1: trust 1 proxy for X-Forwarded-For
# x_proto=1: trust 1 proxy for X-Forwarded-Proto (HTTP vs HTTPS)
# x_host=1: trust 1 proxy for X-Forwarded-Host
# x_prefix=1: trust 1 proxy for X-Forwarded-Prefix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Set secret key for session management
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')


# Small helpers used by a few routes
def check_user_exists(email):
    """Return True if a user with the given email exists."""
    try:
        return user_storage.get_user_by_email(email) is not None
    except Exception:
        return False


def get_storage():
    """Return the configured storage instance."""
    return storage

# Load configuration from file if it exists
app.config.from_pyfile('config.py', silent=True)

# Environment configuration
app.config['ENV'] = os.getenv('FLASK_ENV', 'development')
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', '1' if app.config['ENV'] == 'development' else '0').lower() in ('1', 'true', 'on')

# --- Redis client + session config (REQUIRED) ---
redis_url = os.getenv('REDIS_URL')
if not redis_url:
    raise RuntimeError(
        "REDIS_URL environment variable is required. "
        "Please set it in your .env file. "
        "Example: REDIS_URL=redis://localhost:6379/0"
    )

try:
    # Initialize Redis client for JSON data (users, projects)
    # decode_responses=True converts bytes to strings automatically
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()

    # Initialize separate Redis client for Flask-Session
    # decode_responses=False keeps binary data for pickle serialization
    redis_session_client = redis.from_url(redis_url, decode_responses=False)
    redis_session_client.ping()

    # Initialize Redis storage classes
    storage = RedisProjectStorage(redis_client)
    user_storage = RedisUserStorage(redis_client)
    weekly_storage = storage  # RedisProjectStorage handles weekly summaries

    # Initialize daily notes storage (SQLite-based for image management)
    daily_notes_storage = DailyNotesStorage()

    app.logger.info("✓ Successfully connected to Redis")
except Exception as e:
    raise RuntimeError(f"Failed to connect to Redis: {str(e)}. Please check your REDIS_URL configuration.")

# Configure server-side sessions to use Redis
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis_session_client
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Session cookie configuration for production (HTTPS)
# In production, cookies must be secure. In development, allow non-secure.
is_production = app.config['ENV'] == 'production'
app.config['SESSION_COOKIE_SECURE'] = is_production  # Only send over HTTPS in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_NAME'] = 'devorg_session'  # Custom name to avoid conflicts

# Additional session configuration for production reliability
app.config['SESSION_KEY_PREFIX'] = 'devorg:'  # Prefix for Redis keys to avoid collisions
if is_production:
    app.config['PREFERRED_URL_SCHEME'] = 'https'  # Force HTTPS URLs in production

# File upload configuration for daily notes images
app.config['UPLOAD_FOLDER'] = 'uploads/note_images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# File upload configuration for project documents
app.config['PROJECT_DOCUMENTS_FOLDER'] = 'uploads/project_documents'
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'txt', 'md', 'markdown'}

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROJECT_DOCUMENTS_FOLDER'], exist_ok=True)





# Initialize Flask-Session (configuration is already set above)
from flask_session import Session
Session(app)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize OAuth
oauth = init_oauth(app)

# Refresh user data on each request to ensure plan changes are reflected
@app.before_request
def refresh_user_data():
    """
    Refresh user data from Redis on each request to ensure changes
    (like plan updates) are reflected immediately without requiring logout/login.
    """
    from flask import session, request

    # Skip for static files, OPTIONS requests, and public endpoints
    if request.endpoint in ('static', 'web_login', 'web_signup', 'forgot_password', 'reset_password', 'api_login', 'api_signup', 'landing'):
        return

    if request.method == 'OPTIONS':
        return

    # Get user_id from session
    user_id = session.get('user_id') or session.get('_user_id')

    if user_id:
        try:
            # Fetch fresh user data from Redis
            fresh_user = user_storage.get_user_by_id(str(user_id))

            if fresh_user:
                # Update session with fresh data
                # This ensures plan_type and other fields are always current
                session['user'] = fresh_user
                session.modified = True

                # Store in g for easy access within request
                g.user = fresh_user
                g.user_id = user_id
            else:
                # User not found in database - clear session
                current_app.logger.warning(f"User {user_id} not found in database during refresh, clearing session")
                session.clear()
        except Exception as e:
            # Log error but don't break the request
            current_app.logger.error(f"Error refreshing user data: {str(e)}")

@app.after_request
def after_request(response):
    """Minimal after_request - Flask-Session handles session saving automatically"""
    from flask import session, request

    # Skip for static files
    if request.endpoint == 'static' or request.method == 'OPTIONS':
        return response

    # For authenticated users, ensure session is permanent
    if 'user_id' in session or '_user_id' in session:
        session.permanent = True

    # Add CSRF token header for AJAX requests
    try:
        response.headers.set('X-CSRF-Token', generate_csrf())
    except:
        pass

    # Basic security headers
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Cache-Control', 'no-store, no-cache, must-revalidate')

    return response



@app.route('/')
def index():
    """
    Home page - displays list of all projects and estimations for the current user
    Redirects to landing page if not logged in
    """
    from flask import session, current_app, redirect, url_for, render_template, request, jsonify

    # If user is not logged in, redirect to landing page
    if 'user_id' not in session:
        return redirect(url_for('landing_page'))

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
        current_app.logger.debug(f"[DEBUG] current_user plan_type: {user.get('plan_type', 'NOT SET')}")
        current_app.logger.debug(f"[DEBUG] current_user subscription_status: {user.get('subscription_status', 'NOT SET')}")
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
    # Get current user from session
    user = session.get('user')
    user_id = session.get('user_id')

    # If user data not in session, try to get from database
    if not user and user_id:
        try:
            user = user_storage.get_user_by_id(str(user_id))
            if user:
                session['user'] = user
                session.modified = True
        except Exception as e:
            current_app.logger.error(f"Error fetching user in create_project_form: {str(e)}")

    return render_template('create.html', current_user=user)


@app.route('/create-estimation', methods=['GET'])
@login_required
def create_estimation_form():
    """
    Display the create estimation form
    """
    # Get current user from session
    user = session.get('user')
    user_id = session.get('user_id')

    # If user data not in session, try to get from database
    if not user and user_id:
        try:
            user = user_storage.get_user_by_id(str(user_id))
            if user:
                session['user'] = user
                session.modified = True
        except Exception as e:
            current_app.logger.error(f"Error fetching user in create_estimation_form: {str(e)}")

    return render_template('estimation_create.html', current_user=user)


@app.route('/web_login', methods=['GET', 'POST'])
def web_login():
    """
    Handle web login page display and form submission with improved session handling
    """
    from flask import session, redirect, url_for, request, render_template, flash, current_app, make_response, jsonify

    # Handle GET request
    if request.method == 'GET':
        # Allow users to view login page even if logged in
        # (they might want to switch accounts)

        # Clean up problematic 'next' URLs that could cause loops
        next_url = session.get('next')
        if next_url:
            # If 'next' points to /web_login itself, clear it (loop prevention)
            if '/web_login' in next_url or '/logout' in next_url:
                current_app.logger.warning(f"[LOGIN] Clearing problematic next URL: {next_url}")
                session.pop('next', None)
                session.modified = True

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
        
        # Set up user session - preserve CSRF token and session ID
        # Don't use session.clear() as it removes CSRF token
        session['user_id'] = str(user['id'])
        session['_user_id'] = str(user['id'])  # For compatibility
        session['user'] = user_data
        session.permanent = True
        session.modified = True
        current_app.permanent_session_lifetime = timedelta(days=30 if remember else 1)

        # Get the 'next' URL if it exists, then clear it
        next_url = session.pop('next', None)
        if next_url:
            current_app.logger.debug(f"[LOGIN] Redirecting to next URL: {next_url}")
            redirect_url = next_url
        else:
            redirect_url = url_for('index')

        # For AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'message': 'Login successful',
                'user': user_data,
                'redirect': redirect_url
            })

        # For regular form submission
        return redirect(redirect_url)
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'An error occurred during login'}), 500
        flash('An error occurred. Please try again.', 'error')
        return render_template('auth/login.html', email=request.form.get('email', ''))
@app.route('/web_signup', methods=['GET', 'POST'])
def web_signup():
    """Handle web form signup"""
    # Allow users to view signup page even if logged in
    # (they might want to create another account or switch)

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

            # Check if user wants Pro plan (before creating user)
            plan_param = request.args.get('plan', 'free')

            # Hash the password before creating the user
            from auth import hash_password
            try:
                password_hash = hash_password(password)
                # Always create users as 'free' initially
                # They will be upgraded to 'pro' via webhook when they complete Stripe checkout
                user_data = user_storage.create_user(email, name, password_hash, plan_type='free')
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

            # Set up user session - simple and direct
            user_data = {
                'id': str(user['id']),
                'email': user['email'],
                'name': user.get('name', ''),
                'created_at': user.get('created_at', ''),
                'updated_at': user.get('updated_at', ''),
                'is_active': bool(user.get('is_active', True))
            }
            
            # Set up session - preserve CSRF token and session ID
            # Don't use session.clear() as it removes CSRF token
            session['user_id'] = str(user['id'])
            session['_user_id'] = str(user['id'])  # For compatibility
            session['user'] = user_data
            session.permanent = True
            session.modified = True

            # plan_param was already checked before user creation (line 463)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                redirect_url = url_for('create_stripe_checkout') if plan_param == 'pro' else url_for('index')
                return jsonify({
                    'message': 'Registration successful',
                    'user': user_data,
                    'redirect': redirect_url
                })

            if plan_param == 'pro':
                # Redirect to checkout for Pro subscription
                flash('Complete your Pro subscription to unlock all features!', 'info')
                return redirect(url_for('create_stripe_checkout'))

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
    """Simple logout - clears session and redirects to login"""
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('web_login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests"""
    if request.method == 'POST':
        try:
            # Get email from form
            if request.headers.get('Content-Type') == 'application/json':
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            email = data.get('email', '').strip().lower()
            
            if not email:
                flash('Email is required', 'error')
                return render_template('auth/forgot_password.html')
            
            # Always show success message for security (don't reveal if email exists)
            # But only send email if user actually exists
            user = user_storage.get_user_by_email(email)
            if user:
                # Generate reset token
                reset_token = user_storage.create_password_reset_token(email)
                
                if reset_token:
                    # Send password reset email
                    from email_service import email_service
                    base_url = request.url_root.rstrip('/')
                    
                    email_sent = email_service.send_password_reset_email(
                        to_email=email,
                        reset_token=reset_token,
                        base_url=base_url
                    )
                    
                    if email_sent:
                        current_app.logger.info(f"Password reset email sent to {email}")
                    else:
                        current_app.logger.warning(f"Failed to send password reset email to {email}")
            
            # Always show success message for security
            flash('If an account exists with that email, a password reset link has been sent.', 'success')
            return render_template('auth/forgot_password.html')
            
        except Exception as e:
            current_app.logger.error(f"Error in forgot password: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/forgot_password.html')
    
    # GET request - show forgot password form
    return render_template('auth/forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Handle password reset with token"""
    token = request.args.get('token') or request.form.get('token')
    
    if not token:
        flash('Invalid password reset link', 'error')
        return redirect(url_for('web_login'))
    
    if request.method == 'POST':
        try:
            # Get form data
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            # Validate input
            if not password or not confirm_password:
                flash('All fields are required', 'error')
                return render_template('auth/reset_password.html', token=token, token_valid=True)
            
            if len(password) < 8:
                flash('Password must be at least 8 characters long', 'error')
                return render_template('auth/reset_password.html', token=token, token_valid=True)
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('auth/reset_password.html', token=token, token_valid=True)
            
            # Hash the new password
            from auth import hash_password
            password_hash = hash_password(password)
            
            # Reset password with token
            success = user_storage.reset_password_with_token(token, password_hash)
            
            if success:
                flash('Your password has been reset successfully. You can now log in with your new password.', 'success')
                return redirect(url_for('web_login'))
            else:
                flash('Invalid or expired password reset link', 'error')
                return render_template('auth/reset_password.html', token=token, token_valid=False)
                
        except Exception as e:
            current_app.logger.error(f"Error resetting password: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/reset_password.html', token=token, token_valid=True)
    
    # GET request - verify token and show reset form
    user = user_storage.verify_reset_token(token)
    token_valid = user is not None
    
    return render_template('auth/reset_password.html', token=token, token_valid=token_valid)


@app.route('/clear-session')
def clear_session():
    """Emergency route to clear stuck sessions - useful if user gets stuck in redirect loop"""
    session.clear()
    flash('Your session has been cleared. Please log in again.', 'info')
    return redirect(url_for('web_login'))


# ============================================================================
# OAuth Routes (Google, GitHub, etc.)
# ============================================================================

@app.route('/auth/google')
def oauth_google():
    """Initiate Google OAuth login"""
    try:
        redirect_uri = url_for('oauth_google_callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception as e:
        current_app.logger.error(f"Error initiating Google OAuth: {str(e)}")
        flash('Google login is not configured. Please use regular login.', 'error')
        return redirect(url_for('web_login'))


@app.route('/auth/google/callback')
def oauth_google_callback():
    """Handle Google OAuth callback"""
    try:
        # Get OAuth token
        token = oauth.google.authorize_access_token()

        # Get user info from Google
        user_info = get_google_user_info(token)

        if not user_info.get('email'):
            flash('Could not retrieve email from Google. Please try again.', 'error')
            return redirect(url_for('web_login'))

        # Create or get user
        user = user_storage.get_or_create_oauth_user(
            provider='google',
            oauth_id=user_info['oauth_id'],
            email=user_info['email'],
            name=user_info['name'],
            avatar_url=user_info.get('avatar_url')
        )

        # Create session
        session['user_id'] = user['id']
        session['user'] = user
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        session.permanent = True

        # Update last login
        user_storage.update_last_login(user['id'])

        current_app.logger.info(f"User {user['email']} logged in via Google OAuth")

        # Redirect to next page or dashboard
        next_page = session.pop('next', None)
        return redirect(next_page or url_for('index'))

    except Exception as e:
        current_app.logger.error(f"Error in Google OAuth callback: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('An error occurred during Google login. Please try again.', 'error')
        return redirect(url_for('web_login'))


@app.route('/auth/github')
def oauth_github():
    """Initiate GitHub OAuth login"""
    try:
        redirect_uri = url_for('oauth_github_callback', _external=True)
        return oauth.github.authorize_redirect(redirect_uri)
    except Exception as e:
        current_app.logger.error(f"Error initiating GitHub OAuth: {str(e)}")
        flash('GitHub login is not configured. Please use regular login.', 'error')
        return redirect(url_for('web_login'))


@app.route('/auth/github/callback')
def oauth_github_callback():
    """Handle GitHub OAuth callback"""
    try:
        # Get OAuth token
        token = oauth.github.authorize_access_token()

        # Get user info from GitHub
        user_info = get_github_user_info(token)

        if not user_info.get('email'):
            flash('Could not retrieve email from GitHub. Please make sure your email is public or try another login method.', 'error')
            return redirect(url_for('web_login'))

        # Create or get user
        user = user_storage.get_or_create_oauth_user(
            provider='github',
            oauth_id=user_info['oauth_id'],
            email=user_info['email'],
            name=user_info['name'],
            avatar_url=user_info.get('avatar_url')
        )

        # Create session
        session['user_id'] = user['id']
        session['user'] = user
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        session.permanent = True

        # Update last login
        user_storage.update_last_login(user['id'])

        current_app.logger.info(f"User {user['email']} logged in via GitHub OAuth")

        # Redirect to next page or dashboard
        next_page = session.pop('next', None)
        return redirect(next_page or url_for('index'))

    except Exception as e:
        current_app.logger.error(f"Error in GitHub OAuth callback: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('An error occurred during GitHub login. Please try again.', 'error')
        return redirect(url_for('web_login'))


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    """API logout endpoint - clears session"""
    session.clear()
    return jsonify({
        'status': 'success',
        'message': 'Successfully logged out',
        'redirect': url_for('web_login')
    })

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

        # Validate input
        if not email or not password:
            current_app.logger.warning("[API LOGIN] Missing email or password")
            return jsonify({'error': 'Email and password are required'}), 400

        # Get user from database
        user = user_storage.get_user_by_email(email)
        if not user or not verify_password(user.get('password_hash', ''), password):
            current_app.logger.warning(f"[API LOGIN] Failed login attempt for email: {email}")
            return jsonify({'error': 'Invalid email or password'}), 401

        # Update last login
        try:
            user_storage.update_last_login(user['id'])
        except Exception as e:
            current_app.logger.error(f"Error updating last login: {str(e)}")

        # Set up session - preserve CSRF token
        session['user_id'] = str(user['id'])
        session['_user_id'] = str(user['id'])
        session['user'] = {
            'id': str(user['id']),
            'email': user['email'],
            'name': user.get('name', '')
        }
        session.permanent = True
        session.modified = True

        return jsonify({
            'message': 'Login successful',
            'user': session['user']
        })

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

        # Set up session - preserve CSRF token
        session['user_id'] = str(user['id'])
        session['_user_id'] = str(user['id'])
        session['user'] = {
            'id': str(user['id']),
            'email': email,
            'name': name
        }
        session.permanent = True
        session.modified = True

        return jsonify({
            'message': 'Registration successful',
            'user': session['user']
        }), 201

    except Exception as e:
        current_app.logger.error(f"API signup error: {str(e)}")
        return jsonify({'error': 'An error occurred during registration. Please try again.'}), 500

@app.route('/api/generate-plan', methods=['POST'])
@login_required
def generate_project_plan():
    """
    API endpoint to generate AI plan for a project
    Receives project name, description, options, and optional file uploads
    Returns AI-generated data
    """
    try:
        from file_processor import process_uploaded_files
        
        # Handle both JSON and multipart/form-data
        if request.content_type and 'multipart/form-data' in request.content_type:
            project_name = request.form.get('name', '').strip()
            project_description = request.form.get('description', '').strip()
            is_new_project = request.form.get('is_new_project', 'true').lower() == 'true'
            has_missing_info = request.form.get('has_missing_info', 'false').lower() == 'true'
            
            # Process uploaded files
            uploaded_text = None
            files = request.files.getlist('documents')
            
            if files and files[0].filename:  # Check if files were actually uploaded
                try:
                    result = process_uploaded_files(files, app.config['PROJECT_DOCUMENTS_FOLDER'])
                    
                    if result['errors']:
                        current_app.logger.warning(f"File processing errors: {result['errors']}")
                    
                    if result['combined_text']:
                        uploaded_text = result['combined_text']
                        current_app.logger.info(f"Processed {len(result['files'])} files, extracted {len(uploaded_text)} characters")
                except Exception as file_error:
                    current_app.logger.error(f"Error processing uploaded files: {str(file_error)}")
                    # Don't fail the entire request, just log the error
        else:
            data = request.get_json()
            project_name = data.get('name', '').strip()
            project_description = data.get('description', '').strip()
            is_new_project = data.get('is_new_project', True)
            has_missing_info = data.get('has_missing_info', False)
            uploaded_text = None
        
        # Validate input
        if not project_name or not project_description:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400
        
        # Generate AI plan with new parameters
        ai_data = generate_plan(
            project_name, 
            project_description,
            is_new_project=is_new_project,
            has_missing_info=has_missing_info,
            uploaded_text=uploaded_text
        )
        
        return jsonify({
            'success': True,
            'ai_data': ai_data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating plan: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Failed to generate plan: {str(e)}'
        }), 500


@app.route('/api/projects', methods=['POST'])
@login_required
@check_resource_limit('project')
def save_project():
    """
    Save a project with its AI-generated data
    """
    try:
        # Get user_id with better error handling
        user_id = get_current_user_id()

        # Verify we have a valid user_id
        if not user_id:
            current_app.logger.error("[SAVE_PROJECT] No user_id found in session")
            current_app.logger.debug(f"[SAVE_PROJECT] Session data: {dict(session)}")
            return jsonify({
                'error': 'User session not found. Please log in again.',
                'details': 'No user_id in session'
            }), 401

        current_app.logger.debug(f"[SAVE_PROJECT] Starting save_project for user_id: {user_id}")

        # Get and validate request data
        data = request.get_json()
        if not data:
            current_app.logger.error("[SAVE_PROJECT] No JSON data received")
            return jsonify({
                'error': 'No data provided in request'
            }), 400

        project_name = data.get('name', '').strip()
        project_brief = data.get('brief', '').strip()
        ai_data = data.get('ai_data', {})
        is_new_project = data.get('is_new_project', True)
        has_missing_info = data.get('has_missing_info', False)
        uploaded_files = data.get('uploaded_files', [])

        current_app.logger.debug(f"[SAVE_PROJECT] Received data - name: {project_name}, brief: {project_brief}, is_new: {is_new_project}, has_missing: {has_missing_info}, files: {len(uploaded_files)}")

        # Validate input
        if not project_name or not project_brief:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400

        if not ai_data:
            return jsonify({
                'error': 'AI data is required. Please generate a plan first.'
            }), 400

        # Verify user exists in database
        try:
            user = user_storage.get_user_by_id(str(user_id))
            if not user:
                current_app.logger.error(f"[SAVE_PROJECT] User {user_id} not found in database")
                return jsonify({
                    'error': 'User account not found. Please log in again.',
                    'details': 'User not found in database'
                }), 401
        except Exception as e:
            current_app.logger.error(f"[SAVE_PROJECT] Error verifying user: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Error verifying user account',
                'details': str(e)
            }), 500

        # Prepare project data with user_id and timestamp
        project_data = {
            'name': project_name,
            'brief': project_brief,
            'ai_data': ai_data,
            'user_id': str(user_id),  # Ensure it's a string
            'created_at': datetime.now(timezone.utc).isoformat(),  # Add timestamp
            'is_new_project': is_new_project,
            'has_missing_info': has_missing_info,
            'uploaded_files': uploaded_files
        }

        # Save project
        current_app.logger.debug(f"[SAVE_PROJECT] Attempting to save project for user {user_id}")
        saved_project = storage.save_project(project_data)

        if not saved_project or 'id' not in saved_project:
            current_app.logger.error(f"[SAVE_PROJECT] Failed to save project - invalid response from storage")
            return jsonify({
                'error': 'Failed to save project to database',
                'details': 'Invalid response from storage layer'
            }), 500

        current_app.logger.info(f"[SAVE_PROJECT] Successfully saved project {saved_project['id']} for user {user_id}")

        return jsonify({
            'success': True,
            'project_id': saved_project['id'],
            'message': 'Project saved successfully!'
        })

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        current_app.logger.error(f'[SAVE_PROJECT] Unexpected error: {str(e)}\n{error_trace}')

        # Check if it's a database error
        if 'no such table' in str(e).lower():
            return jsonify({
                'error': 'Database error: Required tables not found. Please run database migrations.',
                'details': str(e)
            }), 500

        # Check if it's a Redis connection error
        if 'redis' in str(e).lower() or 'connection' in str(e).lower():
            return jsonify({
                'error': 'Database connection error. Please try again.',
                'details': 'Failed to connect to database'
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

        # Get current user from session or database
        user = session.get('user')
        if not user and user_id:
            try:
                user = user_storage.get_user_by_id(str(user_id))
                if user:
                    session['user'] = user
                    session.modified = True
            except Exception as e:
                current_app.logger.error(f"Error fetching user in view_project: {str(e)}")

        project = storage.load_project(project_id)

        # Check if project exists and belongs to the user
        if not project or project.get('user_id') != user_id:
            return render_template('error.html',
                                 error_code=404,
                                 error_message='Project not found',
                                 current_user=user), 404

        # Get weekly summaries for this project
        weekly_summaries = weekly_storage.get_weekly_summaries_by_project(project_id)

        # Get the latest feature suggestions for this project
        feature_suggestions = storage.get_latest_feature_suggestions(project_id)

        return render_template('project_detail.html',
                             project=project,
                             weekly_summaries=weekly_summaries,
                             feature_suggestions=feature_suggestions,
                             current_user=user)

    except Exception as e:
        current_app.logger.error(f'Error loading project: {str(e)}', exc_info=True)

        # Get current user for error template
        user = session.get('user')
        user_id = get_current_user_id()
        if not user and user_id:
            try:
                user = user_storage.get_user_by_id(str(user_id))
            except:
                pass

        return render_template('error.html',
                             error_code=500,
                             error_message=f'Error loading project: {str(e)}',
                             current_user=user), 500


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


@app.route('/refine-project-tasks/<string:project_id>', methods=['POST'])
@login_required
def refine_project_tasks(project_id):
    """
    Refine project tasks based on user feedback using AI
    """
    current_app.logger.info(f"Refine project tasks request received for ID: {project_id}")

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        feedback = data.get('feedback', '').strip()
        current_app.logger.info(f"Feedback received (first 100 chars): {feedback[:100]}")

        if not feedback:
            return jsonify({
                'error': 'Feedback is required to refine the tasks'
            }), 400

        # Get the current user ID
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the project
        project = storage.load_project(project_id)

        if not project:
            current_app.logger.error(f"Project not found: {project_id}")
            return jsonify({
                'error': 'Project not found'
            }), 404

        # Verify the current user owns this project
        if str(project.get('user_id')) != str(current_user_id):
            current_app.logger.error(f"Unauthorized access attempt by user {current_user_id} for project {project_id}")
            return jsonify({
                'error': 'Unauthorized: You do not have permission to modify this project'
            }), 403

        # Check if project has a plan to refine
        if not project.get('ai_data') or not project['ai_data'].get('clickup_plan'):
            return jsonify({
                'error': 'This project does not have a task plan to refine'
            }), 400

        try:
            # Call the AI service to refine the task plan
            from ai_service import generate_plan_refinement
            current_app.logger.info("Generating task plan refinement...")

            current_plan = project['ai_data']['clickup_plan']
            project_name = project.get('name', 'Project')
            project_brief = project.get('brief', '')

            refined_plan = generate_plan_refinement(
                project_name,
                project_brief,
                current_plan,
                feedback
            )

            if not refined_plan or not isinstance(refined_plan, dict):
                raise ValueError("Invalid response from AI service")

            # Update the project's clickup_plan with the refined plan
            project['ai_data']['clickup_plan'] = refined_plan

            # Save the updated project
            try:
                updated_project = storage.save_project(project)
                if not updated_project:
                    raise Exception("Storage update failed")

                current_app.logger.info(f"Successfully refined tasks for project {project_id}")
                return jsonify({
                    'success': True,
                    'plan': refined_plan,
                    'message': 'Tasks refined successfully!'
                })

            except Exception as e:
                current_app.logger.error(f"Failed to update project in storage: {str(e)}", exc_info=True)
                return jsonify({
                    'error': 'Failed to save refined tasks',
                    'details': str(e) if current_app.debug else 'An error occurred while saving the refined tasks'
                }), 500

        except ImportError as e:
            current_app.logger.error(f"Failed to load AI service: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Failed to load AI service',
                'details': str(e)
            }), 500

        except Exception as e:
            current_app.logger.error(f"Error during task refinement: {str(e)}", exc_info=True)
            return jsonify({
                'error': 'Failed to generate refined tasks',
                'details': str(e) if current_app.debug else 'An error occurred while generating the refined tasks'
            }), 500

    except Exception as e:
        import traceback
        error_msg = f'Unexpected error in refine_project_tasks: {str(e)}\n{traceback.format_exc()}'
        current_app.logger.error(error_msg)
        return jsonify({
            'error': 'An unexpected error occurred',
            'details': str(e) if current_app.debug else 'Please try again later'
        }), 500


@app.route('/create-weekly-summary', methods=['POST'])
@login_required
def create_weekly_summary():
    """
    Create a new weekly summary for a project
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id') or data.get('projectId')

        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400

        # Get the current user's ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Verify ownership and existence
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Project not found or unauthorized'}), 404

        # Create new weekly summary using the storage layer with project name
        payload = {
            'project_name': project.get('name'),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        summary = weekly_storage.create_weekly_summary(project_id, payload)

        return jsonify({
            'success': True,
            'summary_id': summary['id'],
            'message': 'Weekly summary created successfully!'
        })

    except Exception as e:
        current_app.logger.error(f'Error creating weekly summary: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to create weekly summary: {str(e)}'}), 500


@app.route('/weekly-summary/<summary_id>')
@login_required
def view_weekly_summary(summary_id):
    """
    View and edit a specific weekly summary
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return redirect(url_for('web_login'))

        # Get the weekly summary
        summary = weekly_storage.get_weekly_summary_by_id(summary_id)

        if not summary:
            return render_template('error.html',
                                 error_code=404,
                                 error_message='Weekly summary not found'), 404

        # Get the associated project
        project_id = summary.get('project_id')
        project = storage.load_project(project_id) if project_id else None

        # Verify user has access to this project
        if not project or str(project.get('user_id')) != str(user_id):
            return render_template('error.html',
                                 error_code=403,
                                 error_message='You do not have permission to view this summary'), 403

        # Add project name to summary for template
        summary['project_name'] = project.get('name', 'Unknown Project')

        # Get current user for the template
        current_user = session.get('user')

        return render_template('weekly_summary.html',
                             summary=summary,
                             project_id=project_id,
                             current_user=current_user)

    except Exception as e:
        current_app.logger.error(f'Error viewing weekly summary: {str(e)}', exc_info=True)
        return render_template('error.html',
                             error_code=500,
                             error_message='An error occurred while loading the weekly summary'), 500


@app.route('/update-weekly-summary/<summary_id>', methods=['POST'])
@login_required
def update_weekly_summary(summary_id):
    """
    Update weekly summary notes with proper database integration and security
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the request data
        data = request.get_json()
        week_notes = data.get('week_notes')

        if not week_notes:
            return jsonify({'error': 'Week notes are required'}), 400

        # Verify the summary exists and get its project
        summary = weekly_storage.get_weekly_summary_by_id(summary_id)
        if not summary:
            return jsonify({'error': 'Weekly summary not found'}), 404

        # Verify user owns the project associated with this summary
        project = storage.load_project(summary.get('project_id'))
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Update the summary in the database
        success = weekly_storage.update_weekly_summary(summary_id, week_notes=week_notes)

        if success:
            current_app.logger.info(f'Weekly summary {summary_id} notes updated by user {user_id}')
            return jsonify({
                'success': True,
                'message': 'Weekly notes saved successfully!'
            })
        else:
            return jsonify({'error': 'Failed to update summary'}), 500

    except Exception as e:
        current_app.logger.error(f'Error updating weekly summary: {str(e)}', exc_info=True)
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
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json() or {}
        summary_id = data.get('summary_id', '').strip()
        week_notes = data.get('week_notes') or data.get('weekNotes') or {}

        if not summary_id:
            return jsonify({'error': 'Summary ID is required'}), 400
        if not week_notes:
            return jsonify({'error': 'Week notes are required'}), 400

        # Get the summary to verify ownership
        summary = weekly_storage.get_weekly_summary_by_id(summary_id)
        if not summary:
            return jsonify({'error': 'Weekly summary not found'}), 404

        # Verify user owns the project
        project = storage.load_project(summary.get('project_id'))
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Generate AI summary
        project_name = project.get('name', 'Unknown Project')
        ai_summary = generate_weekly_summary(project_name, week_notes)

        # Update the summary in database
        success = weekly_storage.update_weekly_summary(summary_id, ai_summary=ai_summary)

        if not success:
            return jsonify({'error': 'Failed to update summary'}), 500

        return jsonify({'success': True, 'summary': ai_summary})

    except Exception as e:
        current_app.logger.error(f'Failed to generate summary: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to generate summary: {str(e)}'}), 500


@app.route('/delete-weekly-summary/<summary_id>', methods=['POST'])
@login_required
def delete_weekly_summary(summary_id):
    """
    Delete a weekly summary by ID with proper authentication and database integration
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Verify the summary exists and get its project
        summary = weekly_storage.get_weekly_summary_by_id(summary_id)
        if not summary:
            return jsonify({'error': 'Weekly summary not found'}), 404

        # Verify user owns the project associated with this summary
        project = storage.load_project(summary.get('project_id'))
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Delete the summary from the database
        success = weekly_storage.delete_weekly_summary(summary_id)

        if success:
            current_app.logger.info(f'Weekly summary {summary_id} deleted by user {user_id}')
            return jsonify({
                'success': True,
                'message': 'Weekly summary deleted successfully'
            })
        else:
            return jsonify({'error': 'Failed to delete summary'}), 500

    except Exception as e:
        current_app.logger.error(f'Error deleting weekly summary: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to delete weekly summary: {str(e)}'
        }), 500


# ===== Daily Notes Routes =====

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image(file):
    """Validate that the uploaded file is a valid image"""
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)  # Reset file pointer after verify
        return True
    except Exception:
        return False


def get_note_upload_path(user_id, project_id, note_id):
    """Get the upload path for a note's images"""
    return os.path.join(app.config['UPLOAD_FOLDER'], user_id, project_id, note_id)


def add_image_urls_to_notes(notes):
    """
    Add web-accessible URLs to note images.
    Uses Cloudinary URLs if available, otherwise local URLs.
    """
    if not isinstance(notes, list):
        notes = [notes]

    for note in notes:
        images = note.get('images', [])
        for image in images:
            # Check if image is stored in Cloudinary
            if image.get('cloudinary_url'):
                # Use Cloudinary URL directly
                image['url'] = image['cloudinary_url']
            else:
                # Fallback to local file URL
                # Extract path components from file_path
                # file_path format: uploads/note_images/user_id/project_id/note_id/filename
                file_path = image.get('file_path', '')

                # Extract filename from path (works for both Windows and Unix paths)
                filename = os.path.basename(file_path)

                # Get IDs from the note
                user_id = note.get('user_id')
                project_id = note.get('project_id')
                note_id = note.get('id')

                if user_id and project_id and note_id and filename:
                    # Generate proper web URL
                    image['url'] = url_for('serve_note_image',
                                          user_id=user_id,
                                          project_id=project_id,
                                          note_id=note_id,
                                          filename=filename,
                                          _external=False)

    return notes


@app.route('/project/<project_id>/daily-notes')
@login_required
def daily_notes_page(project_id):
    """Display the daily notes page for a project"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return redirect(url_for('login'))

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            flash('Unauthorized access to project', 'error')
            return redirect(url_for('index'))

        # Get selected date from query param or use today
        selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

        return render_template('daily_notes.html',
                             project=project,
                             selected_date=selected_date)

    except Exception as e:
        current_app.logger.error(f'Error loading daily notes page: {str(e)}', exc_info=True)
        flash('Error loading daily notes', 'error')
        return redirect(url_for('index'))


@app.route('/api/daily-notes/create', methods=['POST'])
@login_required
def create_daily_note():
    """Create a new daily note"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json()
        project_id = data.get('project_id')
        title = data.get('title')
        content = data.get('content', '')
        note_date = data.get('note_date')
        note_time = data.get('note_time')

        # Validate required fields
        if not all([project_id, title, note_date, note_time]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Create the note
        note = daily_notes_storage.create_note(
            project_id=project_id,
            user_id=user_id,
            title=title,
            content=content,
            note_date=note_date,
            note_time=note_time
        )

        current_app.logger.info(f'Daily note created: {note["id"]} by user {user_id}')
        return jsonify({'success': True, 'note': note}), 201

    except Exception as e:
        current_app.logger.error(f'Error creating daily note: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to create note: {str(e)}'}), 500


@app.route('/api/daily-notes/<note_id>', methods=['GET'])
@login_required
def get_daily_note(note_id):
    """Get a specific daily note"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the note
        note = daily_notes_storage.get_note(note_id)
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Verify user owns the project
        project = storage.load_project(note['project_id'])
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Add web URLs to images
        note = add_image_urls_to_notes([note])[0]

        return jsonify({'success': True, 'note': note})

    except Exception as e:
        current_app.logger.error(f'Error getting daily note: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to get note: {str(e)}'}), 500


@app.route('/api/daily-notes/<note_id>', methods=['PUT'])
@login_required
def update_daily_note(note_id):
    """Update an existing daily note"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the note
        note = daily_notes_storage.get_note(note_id)
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Verify user owns the project
        project = storage.load_project(note['project_id'])
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Get update data
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')
        note_date = data.get('note_date')
        note_time = data.get('note_time')

        # Update the note
        success = daily_notes_storage.update_note(
            note_id=note_id,
            title=title,
            content=content,
            note_date=note_date,
            note_time=note_time
        )

        if not success:
            return jsonify({'error': 'Failed to update note'}), 500

        # Get updated note
        updated_note = daily_notes_storage.get_note(note_id)

        current_app.logger.info(f'Daily note updated: {note_id} by user {user_id}')
        return jsonify({'success': True, 'note': updated_note})

    except Exception as e:
        current_app.logger.error(f'Error updating daily note: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to update note: {str(e)}'}), 500


@app.route('/api/daily-notes/<note_id>', methods=['DELETE'])
@login_required
def delete_daily_note(note_id):
    """Delete a daily note"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the note
        note = daily_notes_storage.get_note(note_id)
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Verify user owns the project
        project = storage.load_project(note['project_id'])
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Delete the note (this also deletes associated images)
        success = daily_notes_storage.delete_note(note_id)

        if not success:
            return jsonify({'error': 'Failed to delete note'}), 500

        # Clean up empty directories
        try:
            upload_path = get_note_upload_path(user_id, note['project_id'], note_id)
            if os.path.exists(upload_path) and not os.listdir(upload_path):
                os.rmdir(upload_path)
        except Exception:
            pass  # Ignore directory cleanup errors

        current_app.logger.info(f'Daily note deleted: {note_id} by user {user_id}')
        return jsonify({'success': True, 'message': 'Note deleted successfully'})

    except Exception as e:
        current_app.logger.error(f'Error deleting daily note: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to delete note: {str(e)}'}), 500


@app.route('/api/daily-notes/by-date', methods=['GET'])
@login_required
def get_notes_by_date():
    """Get all notes for a specific project and date"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        project_id = request.args.get('project_id')
        note_date = request.args.get('date')

        if not project_id or not note_date:
            return jsonify({'error': 'Missing project_id or date'}), 400

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Get notes for the date
        notes = daily_notes_storage.get_notes_by_date(project_id, note_date)

        # Add web URLs to images
        notes = add_image_urls_to_notes(notes)

        return jsonify({'success': True, 'notes': notes})

    except Exception as e:
        current_app.logger.error(f'Error getting notes by date: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to get notes: {str(e)}'}), 500


@app.route('/api/daily-notes/by-project/<project_id>', methods=['GET'])
@login_required
def get_notes_by_project(project_id):
    """Get recent notes for a project"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        limit = request.args.get('limit', 50, type=int)

        # Get notes for the project
        notes = daily_notes_storage.get_notes_by_project(project_id, limit)

        # Add web URLs to images
        notes = add_image_urls_to_notes(notes)

        return jsonify({'success': True, 'notes': notes})

    except Exception as e:
        current_app.logger.error(f'Error getting notes by project: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to get notes: {str(e)}'}), 500


@app.route('/api/daily-notes/<note_id>/upload-image', methods=['POST'])
@login_required
def upload_image_to_note(note_id):
    """Upload an image to a note using Cloudinary"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the note
        note = daily_notes_storage.get_note(note_id)
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Verify user owns the project
        project = storage.load_project(note['project_id'])
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400

        file = request.files['image']

        if file.filename == '':
            return jsonify({'error': 'No image file selected'}), 400

        # Validate file
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400

        if not validate_image(file):
            return jsonify({'error': 'Invalid image file'}), 400

        # Check image limit (max 5 per note)
        image_count = daily_notes_storage.get_image_count_for_note(note_id)
        if image_count >= 5:
            return jsonify({'error': 'Maximum 5 images per note'}), 400

        # Generate secure filename
        original_filename = secure_filename(file.filename)
        
        # Check if Cloudinary is configured
        if cloudinary_service.is_configured():
            # Upload to Cloudinary
            current_app.logger.info(f'Uploading image to Cloudinary for note {note_id}')
            
            # Create a folder path for organization: user_id/project_id/note_id
            folder_path = f"dev-organizer/notes/{user_id}/{note['project_id']}/{note_id}"
            
            cloudinary_result = cloudinary_service.upload_image(file, folder=folder_path)
            
            if not cloudinary_result:
                return jsonify({'error': 'Failed to upload image to Cloudinary'}), 500
            
            # Add image to database with Cloudinary info
            image_data = daily_notes_storage.add_image_to_note(
                note_id=note_id,
                filename=cloudinary_result['public_id'].split('/')[-1],
                original_filename=original_filename,
                file_path=cloudinary_result['secure_url'],  # Store Cloudinary URL
                file_size=cloudinary_result['bytes'],
                mime_type=f"image/{cloudinary_result['format']}",
                cloudinary_public_id=cloudinary_result['public_id'],
                cloudinary_url=cloudinary_result['secure_url'],
                width=cloudinary_result.get('width'),
                height=cloudinary_result.get('height')
            )
            
            # Use Cloudinary URL directly
            image_data['url'] = cloudinary_result['secure_url']
            
            current_app.logger.info(f'Image uploaded to Cloudinary: {cloudinary_result["public_id"]}')
            
        else:
            # Fallback to local storage if Cloudinary is not configured
            current_app.logger.warning('Cloudinary not configured, using local storage')
            
            file_ext = original_filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{file_ext}"

            # Create upload directory
            upload_dir = get_note_upload_path(user_id, note['project_id'], note_id)
            os.makedirs(upload_dir, exist_ok=True)

            # Save file locally
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)

            # Get file size
            file_size = os.path.getsize(file_path)

            # Get MIME type
            mime_type = file.content_type or f'image/{file_ext}'

            # Add image to database (local storage)
            image_data = daily_notes_storage.add_image_to_note(
                note_id=note_id,
                filename=filename,
                original_filename=original_filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type
            )

            # Generate URL for accessing the image
            image_url = url_for('serve_note_image',
                               user_id=user_id,
                               project_id=note['project_id'],
                               note_id=note_id,
                               filename=filename)

            image_data['url'] = image_url

        current_app.logger.info(f'Image uploaded to note {note_id} by user {user_id}')
        return jsonify({'success': True, 'image': image_data}), 201

    except Exception as e:
        current_app.logger.error(f'Error uploading image: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to upload image: {str(e)}'}), 500


@app.route('/api/daily-notes/images/<image_id>', methods=['DELETE'])
@login_required
def delete_note_image(image_id):
    """Delete an image from a note (including Cloudinary)"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get the image
        image = daily_notes_storage.get_image(image_id)
        if not image:
            return jsonify({'error': 'Image not found'}), 404

        # Get the note
        note = daily_notes_storage.get_note(image['note_id'])
        if not note:
            return jsonify({'error': 'Note not found'}), 404

        # Verify user owns the project
        project = storage.load_project(note['project_id'])
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # If image is stored in Cloudinary, delete from there first
        if image.get('cloudinary_public_id') and cloudinary_service.is_configured():
            current_app.logger.info(f'Deleting image from Cloudinary: {image["cloudinary_public_id"]}')
            cloudinary_deleted = cloudinary_service.delete_image(image['cloudinary_public_id'])
            if not cloudinary_deleted:
                current_app.logger.warning(f'Failed to delete from Cloudinary: {image["cloudinary_public_id"]}')

        # Delete the image record from database (this also deletes local file if applicable)
        success = daily_notes_storage.delete_note_image(image_id, delete_from_cloudinary=False)

        if not success:
            return jsonify({'error': 'Failed to delete image'}), 500

        current_app.logger.info(f'Image deleted: {image_id} by user {user_id}')
        return jsonify({'success': True, 'message': 'Image deleted successfully'})

    except Exception as e:
        current_app.logger.error(f'Error deleting image: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to delete image: {str(e)}'}), 500


@app.route('/media/<path:filename>')
def serve_media(filename):
    """Serve media files (public assets like landing page images)"""
    try:
        return send_from_directory('media', filename)
    except Exception as e:
        current_app.logger.error(f'Error serving media file: {str(e)}', exc_info=True)
        return 'File not found', 404


@app.route('/uploads/note_images/<user_id>/<project_id>/<note_id>/<filename>')
@login_required
def serve_note_image(user_id, project_id, note_id, filename):
    """Serve a note image with authentication check"""
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return 'Unauthorized', 401

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(current_user_id):
            return 'Unauthorized', 403

        # Verify user_id matches
        if str(user_id) != str(current_user_id):
            return 'Unauthorized', 403

        # Serve the file
        directory = os.path.join(app.config['UPLOAD_FOLDER'], user_id, project_id, note_id)
        return send_from_directory(directory, filename)

    except Exception as e:
        current_app.logger.error(f'Error serving image: {str(e)}', exc_info=True)
        return 'File not found', 404


@app.route('/api/daily-notes/dates/<project_id>/<int:year>/<int:month>', methods=['GET'])
@login_required
def get_note_dates_for_month(project_id, year, month):
    """Get all dates that have notes for a specific month (for calendar highlighting)"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Get dates with notes
        dates = daily_notes_storage.get_note_dates_for_month(project_id, year, month)

        return jsonify({'success': True, 'dates': dates})

    except Exception as e:
        current_app.logger.error(f'Error getting note dates: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to get note dates: {str(e)}'}), 500


@app.route('/api/daily-notes/calendar/<project_id>/<int:year>/<int:month>', methods=['GET'])
@login_required
def get_calendar_html(project_id, year, month):
    """Generate calendar HTML for a specific month using Python calendar module"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Get dates with notes for highlighting
        dates_with_notes = daily_notes_storage.get_note_dates_for_month(project_id, year, month)

        # Get today's date
        today = datetime.now().date()
        today_str = today.isoformat()

        # Create calendar
        cal = calendar.monthcalendar(year, month)

        # Generate HTML (just the inner content, not the wrapper)
        html = ''

        # Weekday headers (Monday first, as Python calendar uses Monday=0)
        weekdays = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
        for day in weekdays:
            html += f'<div class="calendar-weekday">{day}</div>'

        # Calendar days
        for week in cal:
            for day in week:
                if day == 0:
                    # Empty cell for days outside the month
                    html += '<div class="calendar-date-empty"></div>'
                else:
                    # Create date string
                    date_str = f'{year}-{month:02d}-{day:02d}'

                    # Determine classes
                    classes = ['calendar-date']
                    if date_str == today_str:
                        classes.append('today')
                    if date_str in dates_with_notes:
                        classes.append('has-notes')

                    html += f'<div class="{" ".join(classes)}" data-date="{date_str}" onclick="selectDate(\'{date_str}\')">{day}</div>'

        return jsonify({'success': True, 'html': html, 'year': year, 'month': month})

    except Exception as e:
        current_app.logger.error(f'Error generating calendar: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to generate calendar: {str(e)}'}), 500


@app.route('/api/daily-notes/generate-date-range-summary', methods=['POST'])
@login_required
@check_resource_limit('feature_suggestion')
def generate_date_range_summary():
    """Generate AI summary for notes within a date range"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json()
        project_id = data.get('project_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # Validate input
        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400

        # Verify user owns the project
        project = storage.load_project(project_id)
        if not project or str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        # Validate date format and order
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            if start_dt > end_dt:
                return jsonify({'error': 'Start date must be before or equal to end date'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Get notes in date range
        notes = daily_notes_storage.get_notes_by_date_range(project_id, start_date, end_date)

        if not notes:
            return jsonify({
                'success': True,
                'summary': 'No notes found for the selected date range.',
                'note_count': 0,
                'date_range': {'start': start_date, 'end': end_date}
            })

        # Format notes by date for AI context
        notes_by_date = {}
        for note in notes:
            note_date = note['note_date']
            if note_date not in notes_by_date:
                notes_by_date[note_date] = []

            # Format note content
            note_text = f"**{note['title']}** ({note['note_time']})"
            if note.get('content'):
                note_text += f"\n{note['content']}"
            notes_by_date[note_date].append(note_text)

        # Create formatted text for AI
        formatted_notes = []
        for date in sorted(notes_by_date.keys()):
            day_notes = notes_by_date[date]
            formatted_notes.append(f"### {date}\n" + "\n\n".join(day_notes))

        notes_text = "\n\n".join(formatted_notes)

        # Generate AI summary using existing function
        project_name = project.get('name', 'Project')

        # Create a temporary week_notes structure for the AI function
        # The AI function expects this format, so we'll adapt our data
        summary_prompt = f"""
Summarize the following daily notes from {start_date} to {end_date} for project "{project_name}".

{notes_text}

Please provide:
1. A brief overview of the work done
2. Key accomplishments
3. Main challenges or issues encountered
4. Notable progress or milestones
"""

        # Use the existing AI summary function
        summary = generate_weekly_summary(project_name, {'summary_prompt': summary_prompt})

        return jsonify({
            'success': True,
            'summary': summary,
            'note_count': len(notes),
            'date_range': {
                'start': start_date,
                'end': end_date
            }
        })

    except Exception as e:
        current_app.logger.error(f'Error generating date range summary: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to generate summary: {str(e)}'}), 500


@app.route('/generate-feature-suggestions', methods=['POST'])
@login_required
@check_resource_limit('feature_suggestion')
def generate_feature_suggestions_endpoint():
    """
    API endpoint to generate AI feature suggestions from project audit with database integration
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json() or {}
        project_id = data.get('project_id') or data.get('projectId')
        audit_text = (data.get('audit_text') or data.get('auditText') or '').strip()

        # Validate input
        if not project_id:
            return jsonify({'error': 'Project ID is required'}), 400
        if not audit_text:
            return jsonify({'error': 'Project audit text is required'}), 400

        # Load project and verify ownership
        project = storage.load_project(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        if str(project.get('user_id')) != str(user_id):
            return jsonify({'error': 'Unauthorized access'}), 403

        project_name = project.get('name', 'Unknown Project')

        # Generate AI feature suggestions
        current_app.logger.info(f'Generating feature suggestions for project {project_id} by user {user_id}')
        suggestions = generate_feature_suggestions(project_name, audit_text)

        # Save suggestions to database
        saved_suggestion = storage.save_feature_suggestions(
            project_id=project_id,
            project_name=project_name,
            audit_text=audit_text,
            suggestions=suggestions
        )

        current_app.logger.info(f'Feature suggestions saved with ID: {saved_suggestion["id"]}')

        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'suggestion_id': saved_suggestion['id']
        })

    except Exception as e:
        current_app.logger.error(f'Failed to generate feature suggestions: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to generate feature suggestions: {str(e)}'}), 500


@app.route('/generate-estimation', methods=['POST'])
@login_required
@check_resource_limit('estimation')
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
                'created_at': datetime.now(timezone.utc).isoformat()
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

        # Get current user ID from session
        user_id = session.get('user_id') or session.get('_user_id')
        if not user_id:
            current_app.logger.warning("[ESTIMATION_VIEW] No valid user session, redirecting to login")
            return redirect(url_for('web_login'))
        
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
            session.clear()
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

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        feedback = data.get('feedback', '').strip()
        current_app.logger.info(f"Feedback received (first 100 chars): {feedback[:100]}")

        if not feedback:
            return jsonify({
                'error': 'Feedback is required to refine the estimation'
            }), 400

        # Get the original estimation
        estimation = storage.get_estimation_by_id(estimation_id)

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
                
                'id': estimation_id,
                'user_id': current_user_id
            })
            
            # Save as a new estimation or update existing one based on your requirements
            # Here we'll update the existing one
            try:
                updated = storage.update_estimation(estimation_id, refined_estimation, user_id=current_user_id)
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
@require_plan('pro')
def check_clickup_config():
    """
    Check if current user has ClickUp API token configured
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Check if user has token configured
        user_token = user_storage.get_user_clickup_token(user_id)
        has_token = bool(user_token and user_token.strip())

        return jsonify({
            'configured': has_token,
            'has_token': has_token,
            'message': 'Token configured' if has_token else 'No token configured'
        })

    except Exception as e:
        current_app.logger.error(f'Error checking ClickUp config: {str(e)}', exc_info=True)
        return jsonify({
            'configured': False,
            'error': str(e)
        }), 500


@app.route('/clickup/workspaces', methods=['GET'])
@login_required
@require_plan('pro')
def get_clickup_workspaces():
    """
    Get all ClickUp workspaces for the authenticated user using their personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured. Please configure your ClickUp token first.',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

        # Fetch workspaces
        result = clickup.get_workspaces()

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Failed to fetch workspaces: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to fetch workspaces: {str(e)}'
        }), 500


@app.route('/clickup/spaces/<team_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_clickup_spaces(team_id):
    """
    Get all spaces (projects) within a ClickUp workspace using user's personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

        # Fetch spaces
        result = clickup.get_spaces(team_id)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Failed to fetch spaces: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to fetch spaces: {str(e)}'
        }), 500


@app.route('/clickup/shared-lists/<team_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_clickup_shared_lists(team_id):
    """
    Get all lists shared with the user in a workspace using user's personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

        # Fetch shared lists
        result = clickup.get_shared_lists(team_id)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Failed to fetch shared lists: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to fetch shared lists: {str(e)}'
        }), 500


@app.route('/clickup/folders/<space_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_clickup_folders(space_id):
    """
    Get all folders within a ClickUp space using user's personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

        # Fetch folders
        result = clickup.get_folders(space_id)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Failed to fetch folders: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to fetch folders: {str(e)}'
        }), 500


@app.route('/clickup/lists/<space_id>', methods=['GET'])
@app.route('/clickup/lists/<space_id>/<folder_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_clickup_lists(space_id, folder_id=None):
    """
    Get all lists within a ClickUp space or folder using user's personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

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
@require_plan('pro')
def create_clickup_tasks():
    """
    Create tasks in ClickUp from project phases using user's personal token
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json()
        list_id = data.get('list_id')
        phases = data.get('phases', [])

        # Validate input
        if not list_id:
            return jsonify({'error': 'List ID is required'}), 400

        if not phases:
            return jsonify({'error': 'No tasks to create'}), 400

        # Get user's ClickUp token from database
        user_token = user_storage.get_user_clickup_token(user_id)

        if not user_token or not user_token.strip():
            return jsonify({
                'error': 'ClickUp API token not configured',
                'needs_config': True
            }), 401

        # Get ClickUp service with user's token
        clickup = get_clickup_service(user_token)

        # Create tasks
        current_app.logger.info(f'Creating {len(phases)} phases of tasks in ClickUp for user {user_id}')
        result = clickup.create_tasks_from_phases(list_id, phases)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f'Failed to create tasks: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Failed to create tasks: {str(e)}'
        }), 500


@app.route('/api/user/clickup-token', methods=['POST'])
@login_required
def save_user_clickup_token():
    """
    Save ClickUp API token for the current user
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        data = request.get_json() or {}
        token = (data.get('token') or '').strip()

        if not token:
            return jsonify({'error': 'ClickUp API token is required'}), 400

        # Save token to database
        success = user_storage.save_user_clickup_token(user_id, token)

        if success:
            current_app.logger.info(f'ClickUp token saved for user {user_id}')
            return jsonify({
                'success': True,
                'message': 'ClickUp token saved successfully'
            })
        else:
            return jsonify({'error': 'Failed to save token'}), 500

    except Exception as e:
        current_app.logger.error(f'Error saving ClickUp token: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to save token: {str(e)}'}), 500


@app.route('/api/user/clickup-token/check', methods=['GET'])
@login_required
def check_user_clickup_token():
    """
    Check if current user has a ClickUp API token configured
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        token = user_storage.get_user_clickup_token(user_id)
        has_token = bool(token and token.strip())

        return jsonify({
            'configured': has_token,
            'has_token': has_token
        })

    except Exception as e:
        current_app.logger.error(f'Error checking ClickUp token: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to check token: {str(e)}'}), 500


@app.route('/api/user/clickup-token', methods=['DELETE'])
@login_required
def delete_user_clickup_token():
    """
    Delete ClickUp API token for the current user
    """
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        success = user_storage.delete_user_clickup_token(user_id)

        if success:
            current_app.logger.info(f'ClickUp token deleted for user {user_id}')
            return jsonify({
                'success': True,
                'message': 'ClickUp token removed successfully'
            })
        else:
            return jsonify({'error': 'Failed to remove token'}), 500

    except Exception as e:
        current_app.logger.error(f'Error deleting ClickUp token: {str(e)}', exc_info=True)
        return jsonify({'error': f'Failed to remove token: {str(e)}'}), 500

@app.route('/api/user/linear-token', methods=['POST'])
@login_required
def save_linear_token():
    """Save Linear API token for current user"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()

        if not token:
            return jsonify({'success': False, 'error': 'Token is required'}), 400

        # Validate token format
        if not token.startswith('lin_api_'):
            return jsonify({'success': False, 'error': 'Invalid Linear token format. Token should start with "lin_api_"'}), 400

        # Validate token by making a test API call
        if not validate_linear_token(token):
            return jsonify({'success': False, 'error': 'Invalid Linear API token. Please check your token and try again.'}), 401

        # Save token to database
        user_id = session.get('user_id')
        success = user_storage.save_user_linear_token(user_id, token)

        if success:
            return jsonify({'success': True, 'message': 'Linear token saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save token'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/linear-token/check', methods=['GET'])
@login_required
def check_linear_token():
    """Check if current user has Linear token configured"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        return jsonify({
            'configured': bool(token)
        })

    except Exception as e:
        return jsonify({'configured': False, 'error': str(e)}), 500


@app.route('/api/user/linear-token', methods=['DELETE'])
@login_required
def delete_linear_token():
    """Delete Linear API token for current user"""
    try:
        user_id = session.get('user_id')
        success = user_storage.delete_user_linear_token(user_id)

        if success:
            return jsonify({'success': True, 'message': 'Linear token deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete token'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# -----------------
# Linear API Endpoints (Pro Plan Required)
# -----------------

@app.route('/linear/check-config', methods=['GET'])
@login_required
@require_plan('pro')
def check_linear_config():
    """Check if Linear is configured for current user"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        return jsonify({
            'configured': bool(token)
        })

    except Exception as e:
        return jsonify({'configured': False, 'error': str(e)}), 500


@app.route('/linear/teams', methods=['GET'])
@login_required
@require_plan('pro')
def get_linear_teams():
    """Get all Linear teams for authenticated user"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        linear = LinearService(token)
        teams = linear.get_teams()

        return jsonify({'teams': teams})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/linear/projects/<team_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_linear_projects(team_id):
    """Get all projects in a Linear team"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        linear = LinearService(token)
        projects = linear.get_projects(team_id)

        return jsonify({'projects': projects})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/linear/create-issues', methods=['POST'])
@login_required
@require_plan('pro')
def create_linear_issues():
    """Create issues in Linear from project phases"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        data = request.get_json()
        team_id = data.get('team_id')
        project_id = data.get('project_id')  # Optional
        phases = data.get('phases', [])

        if not team_id:
            return jsonify({'error': 'Team ID is required'}), 400

        if not phases:
            return jsonify({'error': 'No phases provided'}), 400

        linear = LinearService(token)
        result = linear.create_issues_from_phases(
            team_id=team_id,
            phases=phases,
            project_id=project_id if project_id else None
        )

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'created_count': 0,
            'failed_count': 0
        }), 500

@app.route('/home')
def landing_page():
    '''Landing page - can be viewed by anyone (logged in or not)'''
    # Get current user if logged in
    user = None
    user_id = session.get('user_id')
    if user_id:
        try:
            user = user_storage.get_user_by_id(user_id)
            print(f"[LANDING] User ID: {user_id}")
            print(f"[LANDING] User plan_type: {user.get('plan_type', 'NOT SET') if user else 'NO USER'}")
            print(f"[LANDING] User subscription_status: {user.get('subscription_status', 'NOT SET') if user else 'NO USER'}")
            print(f"[LANDING] User object: {user}")
        except Exception as e:
            print(f"[LANDING] Error getting user: {e}")
            pass

    return render_template('landing.html', current_user=user)


@app.route('/manage-subscription')
@login_required
def manage_subscription():
    '''Manage subscription page - shows upgrade or downgrade options based on current plan'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            flash('Please log in to manage your subscription', 'error')
            return redirect(url_for('web_login'))
        
        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('index'))
        
        return render_template('manage_subscription.html', user=user, current_user=user)
    
    except Exception as e:
        current_app.logger.error(f'Error loading manage subscription page: {str(e)}', exc_info=True)
        flash('Failed to load subscription page. Please try again.', 'error')
        return redirect(url_for('index'))


@app.route('/cancel-subscription', methods=['POST'])
@login_required
@require_plan('pro')
def cancel_subscription():
    '''Cancel Pro subscription and downgrade to Free plan'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get Stripe customer ID and subscription ID
        customer_id = user.get('stripe_customer_id')
        stripe_subscription_id = user.get('stripe_subscription_id')
        
        if not customer_id or not stripe_subscription_id:
            # User doesn't have an active Stripe subscription, just downgrade them
            user_storage.update_user_subscription(
                user_id=user_id,
                plan_type='free',
                subscription_status='canceled'
            )
            flash('Your subscription has been canceled. You are now on the Free plan.', 'success')
            return redirect(url_for('index'))
        
        # Cancel the Stripe subscription
        from stripe_service import cancel_stripe_subscription
        result = cancel_stripe_subscription(stripe_subscription_id)
        
        if result.get('success'):
            # Update user to Free plan
            user_storage.update_user_subscription(
                user_id=user_id,
                plan_type='free',
                subscription_status='canceled',
                stripe_subscription_id=None
            )
            
            current_app.logger.info(f'User {user_id} canceled Pro subscription and downgraded to Free')
            flash('Your Pro subscription has been canceled. You are now on the Free plan.', 'success')
            return redirect(url_for('index'))
        else:
            flash(f'Failed to cancel subscription: {result.get("error")}', 'error')
            return redirect(url_for('manage_subscription'))
    
    except Exception as e:
        current_app.logger.error(f'Error canceling subscription: {str(e)}', exc_info=True)
        flash('Failed to cancel subscription. Please try again or contact support.', 'error')
        return redirect(url_for('manage_subscription'))


@app.route('/create-checkout-session', methods=['POST', 'GET'])
@login_required
def create_stripe_checkout():
    '''Create a Stripe Checkout Session for Pro subscription'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Check if user already has Pro
        if user.get('plan_type') == 'pro':
            subscription_status = user.get('subscription_status')
            if subscription_status in ['trialing', 'active']:
                return jsonify({
                    'error': 'You already have an active Pro subscription',
                    'redirect': url_for('index')
                }), 400

        # Create Stripe Checkout Session
        session_data = create_checkout_session(
            user_id=user_id,
            email=user['email'],
            plan='pro'
        )

        # For GET requests, redirect to Stripe Checkout
        if request.method == 'GET':
            return redirect(session_data['checkout_url'])

        # For POST requests (AJAX), return JSON
        return jsonify(session_data)

    except Exception as e:
        current_app.logger.error(f'Error creating checkout session: {str(e)}', exc_info=True)
        if request.method == 'GET':
            flash('Failed to create checkout session. Please try again.', 'error')
            return redirect(url_for('index'))
        return jsonify({'error': str(e)}), 500


@app.route('/create-portal-session', methods=['POST', 'GET'])
@login_required
@require_plan('pro')
def create_stripe_portal():
    '''Create a Stripe Customer Portal Session for subscription management'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user info
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get Stripe customer ID
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            return jsonify({'error': 'No active subscription found'}), 400

        # Create portal session
        portal_data = create_customer_portal_session(customer_id)

        # For GET requests, redirect to portal
        if request.method == 'GET':
            return redirect(portal_data['portal_url'])

        # For POST requests, return JSON
        return jsonify(portal_data)

    except Exception as e:
        current_app.logger.error(f'Error creating portal session: {str(e)}', exc_info=True)
        if request.method == 'GET':
            flash('Failed to open subscription portal. Please try again.', 'error')
            return redirect(url_for('index'))
        return jsonify({'error': str(e)}), 500


@app.route('/subscription/success')
@login_required
def subscription_success():
    '''Success page after successful subscription'''
    return render_template('subscription_success.html')


@app.route('/subscription/cancel')
def subscription_cancel():
    '''Cancel page when user cancels subscription checkout'''
    return render_template('subscription_cancel.html')


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    '''Handle Stripe webhook events'''
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Process the webhook event
        event_data = handle_webhook_event(payload, sig_header)

        if not event_data:
            # Event not handled
            return jsonify({'status': 'ignored'}), 200

        event_type = event_data['event_type']
        current_app.logger.info(f'Processing webhook: {event_type}')

        # Handle checkout completion
        if event_type == 'checkout_completed':
            user_id = event_data.get('user_id')
            customer_id = event_data.get('customer_id')
            subscription_id = event_data.get('subscription_id')

            if user_id and customer_id:
                # Update user with Stripe customer and subscription IDs
                user_storage.update_user_subscription(
                    user_id,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=subscription_id,
                    plan_type='pro',
                    subscription_status='trialing'
                )
                current_app.logger.info(f'User {user_id} upgraded to Pro (trial)')

        # Handle subscription creation
        elif event_type == 'subscription_created':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status=event_data.get('status'),
                    trial_end=event_data.get('trial_end'),
                    subscription_current_period_end=event_data.get('current_period_end')
                )

        # Handle subscription updates (e.g., trial ending, plan changes)
        elif event_type == 'subscription_updated':
            customer_id = event_data.get('customer_id')

            # Find user by customer_id
            # Note: This requires iterating through users or having a reverse index
            # For now, we'll skip if user_id is not in metadata
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status=event_data.get('status'),
                    trial_end=event_data.get('trial_end'),
                    subscription_current_period_end=event_data.get('current_period_end')
                )

        # Handle subscription deletion/cancellation
        elif event_type == 'subscription_deleted':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    plan_type='free',
                    subscription_status='canceled',
                    stripe_subscription_id=None
                )
                current_app.logger.info(f'User {user_id} downgraded to Free')

        # Handle successful payments
        elif event_type == 'payment_succeeded':
            current_app.logger.info(f'Payment succeeded for subscription {event_data.get("subscription_id")}')

        # Handle failed payments
        elif event_type == 'payment_failed':
            user_id = event_data.get('user_id')
            if user_id:
                user_storage.update_user_subscription(
                    user_id,
                    subscription_status='past_due'
                )
                current_app.logger.warning(f'Payment failed for user {user_id}')

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        current_app.logger.error(f'Webhook error: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 400


@app.route('/api/user/subscription', methods=['GET'])
@login_required
def get_user_subscription_info():
    '''Get current user's subscription information'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        subscription = user_storage.get_user_subscription(user_id)
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404

        return jsonify(subscription)

    except Exception as e:
        current_app.logger.error(f'Error getting subscription: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/usage', methods=['GET'])
@login_required
def get_user_usage():
    '''Get current user's usage statistics and limits'''
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get user's plan
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        plan_type = user.get('plan_type', 'free')

        # Get usage counts
        usage = user_storage.get_user_usage_counts(user_id)

        # Get plan limits
        limits = get_user_plan_limits(plan_type)

        return jsonify({
            'plan_type': plan_type,
            'usage': usage,
            'limits': limits,
            'subscription_status': user.get('subscription_status')
        })

    except Exception as e:
        current_app.logger.error(f'Error getting usage: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/stripe/config', methods=['GET'])
@login_required
def get_stripe_public_config():
    '''Get Stripe publishable key for client-side'''
    try:
        config = get_stripe_config()
        return jsonify({
            'publishable_key': config['publishable_key']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User not authenticated'
            }), 401

        # Verify the project belongs to the current user
        project = storage.load_project(project_id)
        if not project:
            return jsonify({
                'status': 'error',
                'message': 'Project not found'
            }), 404

        if str(project.get('user_id')) != str(user_id):
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized access to project'
            }), 403

        current_app.logger.debug(f"Fetching section states for project: {project_id}, user: {user_id}")
        section_states = storage.get_section_states(project_id, user_id)
        current_app.logger.debug(f"Retrieved section states: {section_states}")

        if section_states is None:
            current_app.logger.debug("No section states found, returning empty dict")
            section_states = {}

        return jsonify({
            'status': 'success',
            'section_states': section_states
        })

    except Exception as e:
        error_msg = f'Failed to load section states: {str(e)}'
        current_app.logger.error(error_msg, exc_info=True)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'error_type': type(e).__name__
        }), 500

@app.route('/api/projects/<project_id>/section-states/<section_id>', methods=['POST'])
@login_required
def save_section_state(project_id, section_id):
    """
    Save the state of a section for a project
    """
    try:
        # Get current user ID
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': 'User not authenticated'
            }), 401

        # Verify the project belongs to the current user
        project = storage.load_project(project_id)
        if not project:
            return jsonify({
                'status': 'error',
                'message': 'Project not found'
            }), 404

        if str(project.get('user_id')) != str(user_id):
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized access to project'
            }), 403

        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided in request'
            }), 400

        is_expanded = data.get('is_expanded', False)

        current_app.logger.debug(f"Saving section state - Project: {project_id}, Section: {section_id}, Expanded: {is_expanded}, User: {user_id}")

        success = storage.save_section_state(project_id, section_id, is_expanded, user_id)
        
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
# AI Generation endpoints
csrf.exempt(generate_project_plan)
csrf.exempt(generate_week_summary)
csrf.exempt(generate_feature_suggestions_endpoint)
csrf.exempt(generate_estimation_endpoint)
csrf.exempt(refine_estimation)

# Project management endpoints
csrf.exempt(save_project)
csrf.exempt(delete_project)
csrf.exempt(refine_project_tasks)

# Weekly summary endpoints
csrf.exempt(create_weekly_summary)
csrf.exempt(update_weekly_summary)
csrf.exempt(delete_weekly_summary)

# Section state endpoints
csrf.exempt(save_section_state)
csrf.exempt(get_section_states)

# Estimation endpoints
csrf.exempt(delete_estimation)

# ClickUp integration endpoints
csrf.exempt(check_clickup_config)
csrf.exempt(get_clickup_workspaces)
csrf.exempt(get_clickup_spaces)
csrf.exempt(get_clickup_shared_lists)
csrf.exempt(get_clickup_folders)
csrf.exempt(get_clickup_lists)
csrf.exempt(create_clickup_tasks)
csrf.exempt(save_user_clickup_token)
csrf.exempt(check_user_clickup_token)
csrf.exempt(delete_user_clickup_token)


csrf.exempt(stripe_webhook)
csrf.exempt(get_user_subscription_info)
csrf.exempt(get_user_usage)




if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)

    # Print startup message
    print("🚀 Dev Project Organizer Starting...")
    print("=" * 60)
    print(f"📊 Storage: Redis")
    print(f"🔗 Redis URL: {redis_url.split('@')[1] if '@' in redis_url else redis_url.replace('redis://', '')}")
    print(f"🌐 Server: http://127.0.0.1:5000")
    print("=" * 60)

    # Start the development server
    app.run(debug=True, host='127.0.0.1', port=5000)
