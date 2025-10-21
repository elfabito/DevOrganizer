"""
OAuth Service for DevOrganizer
Handles OAuth 2.0 authentication with Google, GitHub, and other providers
"""
import os
from authlib.integrations.flask_client import OAuth
from flask import url_for

# Initialize OAuth registry
oauth = OAuth()

def init_oauth(app):
    """
    Initialize OAuth providers with Flask app

    Args:
        app: Flask application instance
    """
    oauth.init_app(app)

    # Get app URL from environment
    app_url = os.getenv('APP_URL', 'http://127.0.0.1:5000')

    # Register Google OAuth
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    if google_client_id and google_client_secret:
        oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile'
            }
        )
        app.logger.info("Google OAuth configured successfully")
    else:
        app.logger.warning("Google OAuth not configured - missing CLIENT_ID or CLIENT_SECRET")

    # Register GitHub OAuth
    github_client_id = os.getenv('GITHUB_CLIENT_ID')
    github_client_secret = os.getenv('GITHUB_CLIENT_SECRET')

    if github_client_id and github_client_secret:
        oauth.register(
            name='github',
            client_id=github_client_id,
            client_secret=github_client_secret,
            access_token_url='https://github.com/login/oauth/access_token',
            access_token_params=None,
            authorize_url='https://github.com/login/oauth/authorize',
            authorize_params=None,
            api_base_url='https://api.github.com/',
            client_kwargs={'scope': 'user:email'},
        )
        app.logger.info("GitHub OAuth configured successfully")
    else:
        app.logger.warning("GitHub OAuth not configured - missing CLIENT_ID or CLIENT_SECRET")

    return oauth


def get_google_user_info(token):
    """
    Get user information from Google OAuth token

    Args:
        token: OAuth token dict from Google

    Returns:
        dict: User information (email, name, picture, sub)
    """
    google = oauth.create_client('google')
    resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo', token=token)
    user_info = resp.json()

    return {
        'email': user_info.get('email'),
        'name': user_info.get('name'),
        'avatar_url': user_info.get('picture'),
        'oauth_id': user_info.get('sub')  # Google's unique user ID
    }


def get_github_user_info(token):
    """
    Get user information from GitHub OAuth token

    Args:
        token: OAuth token dict from GitHub

    Returns:
        dict: User information (email, name, avatar_url, id)
    """
    github = oauth.create_client('github')

    # Get user profile
    resp = github.get('user', token=token)
    user_info = resp.json()

    # Get primary email (GitHub may not return email in profile)
    email = user_info.get('email')
    if not email:
        emails_resp = github.get('user/emails', token=token)
        emails = emails_resp.json()
        # Find primary verified email
        for email_obj in emails:
            if email_obj.get('primary') and email_obj.get('verified'):
                email = email_obj.get('email')
                break
        # Fallback to first email if no primary found
        if not email and emails:
            email = emails[0].get('email')

    return {
        'email': email,
        'name': user_info.get('name') or user_info.get('login'),  # Use login if name not set
        'avatar_url': user_info.get('avatar_url'),
        'oauth_id': str(user_info.get('id'))  # GitHub's unique user ID
    }
