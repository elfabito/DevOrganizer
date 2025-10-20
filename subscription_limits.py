"""
Subscription Limits and Access Control for DevOrganizer
Defines plan limits and provides decorators to enforce them
"""
from functools import wraps
from flask import current_app, jsonify, session
from typing import Tuple, Optional

# Plan limits configuration
PLAN_LIMITS = {
    'free': {
        'projects': 1,
        'estimations': 1,
        'feature_suggestions': 1,
        'clickup_integration': False
    },
    'pro': {
        'projects': 20,
        'estimations': 20,
        'feature_suggestions': 20,
        'clickup_integration': True
    }
}


def get_user_plan_limits(plan_type: str) -> dict:
    """
    Get the limits for a specific plan type

    Args:
        plan_type: 'free' or 'pro'

    Returns:
        Dictionary with plan limits
    """
    return PLAN_LIMITS.get(plan_type, PLAN_LIMITS['free'])


def check_usage_limit(user_id: str, resource_type: str, user_storage) -> Tuple[bool, int, int]:
    """
    Check if user can create more resources of a given type

    Args:
        user_id: The user's ID
        resource_type: 'project', 'estimation', or 'feature_suggestion'
        user_storage: Instance of RedisUserStorage

    Returns:
        Tuple of (allowed: bool, current_count: int, max_count: int)
    """
    try:
        # Get user's plan
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return (False, 0, 0)

        plan_type = user.get('plan_type', 'free')
        limits = get_user_plan_limits(plan_type)

        # Map resource type to limit key
        limit_key_map = {
            'project': 'projects',
            'estimation': 'estimations',
            'feature_suggestion': 'feature_suggestions'
        }

        limit_key = limit_key_map.get(resource_type)
        if not limit_key:
            return (False, 0, 0)

        # Get current usage
        usage = user_storage.get_user_usage_counts(user_id)
        current_count = usage.get(limit_key, 0)
        max_count = limits.get(limit_key, 0)

        # Check if under limit
        allowed = current_count < max_count

        return (allowed, current_count, max_count)

    except Exception as e:
        current_app.logger.error(f"Error checking usage limit: {str(e)}")
        return (False, 0, 0)


def require_plan(required_plan: str = 'pro'):
    """
    Decorator to require a specific plan for a route

    Usage:
        @require_plan('pro')
        def my_route():
            ...

    Args:
        required_plan: The minimum plan required ('pro')

    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            from auth import get_current_user_id
            from storage_redis import RedisUserStorage
            import redis
            import os

            # Get user ID
            user_id = get_current_user_id()
            if not user_id:
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                return jsonify({'error': 'Authentication required'}), 401

            # Get user's plan
            try:
                redis_url = os.getenv('REDIS_URL')
                redis_client = redis.from_url(redis_url, decode_responses=True)
                user_storage = RedisUserStorage(redis_client)

                user = user_storage.get_user_by_id(user_id)
                if not user:
                    return jsonify({'error': 'User not found'}), 404

                user_plan = user.get('plan_type', 'free')

                # Check if user has required plan
                if required_plan == 'pro' and user_plan != 'pro':
                    # Check if subscription is active
                    subscription_status = user.get('subscription_status')

                    # Allow if in trial or active
                    if subscription_status not in ['trialing', 'active']:
                        if request.path.startswith('/api/') or request.is_json:
                            return jsonify({
                                'error': 'This feature requires a Pro subscription',
                                'required_plan': 'pro',
                                'current_plan': user_plan,
                                'upgrade_url': '/create-checkout-session'
                            }), 403

                        return jsonify({
                            'error': 'This feature requires a Pro subscription',
                            'upgrade_url': '/create-checkout-session'
                        }), 403

            except Exception as e:
                current_app.logger.error(f"Error checking plan requirement: {str(e)}")
                return jsonify({'error': 'Internal server error'}), 500

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def check_resource_limit(resource_type: str):
    """
    Decorator to check resource creation limits before allowing the action

    Usage:
        @check_resource_limit('project')
        def create_project():
            ...

    Args:
        resource_type: 'project', 'estimation', or 'feature_suggestion'

    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            from auth import get_current_user_id
            from storage_redis import RedisUserStorage
            import redis
            import os

            # Get user ID
            user_id = get_current_user_id()
            if not user_id:
                return jsonify({'error': 'Authentication required'}), 401

            # Check usage limit
            try:
                redis_url = os.getenv('REDIS_URL')
                redis_client = redis.from_url(redis_url, decode_responses=True)
                user_storage = RedisUserStorage(redis_client)

                allowed, current_count, max_count = check_usage_limit(
                    user_id, resource_type, user_storage
                )

                if not allowed:
                    # Get user's plan
                    user = user_storage.get_user_by_id(user_id)
                    user_plan = user.get('plan_type', 'free')

                    resource_name = resource_type.replace('_', ' ').title()

                    return jsonify({
                        'error': f'You have reached your {resource_name} limit',
                        'current_count': current_count,
                        'max_count': max_count,
                        'current_plan': user_plan,
                        'message': f'Your {user_plan.title()} plan allows up to {max_count} {resource_name.lower()}s. You currently have {current_count}.',
                        'upgrade_url': '/create-checkout-session' if user_plan == 'free' else None
                    }), 403

            except Exception as e:
                current_app.logger.error(f"Error checking resource limit: {str(e)}")
                return jsonify({'error': 'Internal server error'}), 500

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def can_use_clickup(user_id: str, user_storage) -> bool:
    """
    Check if user can use ClickUp integration

    Args:
        user_id: The user's ID
        user_storage: Instance of RedisUserStorage

    Returns:
        True if user can use ClickUp integration
    """
    try:
        user = user_storage.get_user_by_id(user_id)
        if not user:
            return False

        plan_type = user.get('plan_type', 'free')
        subscription_status = user.get('subscription_status')

        # ClickUp is only available for Pro plan
        if plan_type == 'pro':
            # Must have active or trialing subscription
            return subscription_status in ['trialing', 'active']

        return False

    except Exception as e:
        current_app.logger.error(f"Error checking ClickUp access: {str(e)}")
        return False
