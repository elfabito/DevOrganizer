import os
import json
import uuid
import redis
from datetime import datetime, timezone
from typing import Optional, Dict, List

def get_redis_client():
    url = os.getenv("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL not set")
    return redis.from_url(url, decode_responses=True)

class RedisProjectStorage:
    def __init__(self, client=None):
        self.r = client or get_redis_client()

    def _proj_key(self, project_id: str) -> str:
        return f"project:{project_id}"

    def _user_index(self, user_id: str) -> str:
        return f"user_projects:{user_id}"

    def save_project(self, project_data: Dict) -> Dict:
        project_id = project_data.get("id") or str(uuid.uuid4())
        project = {
            "id": project_id,
            "name": project_data.get("name"),
            "brief": project_data.get("brief", ""),
            "user_id": str(project_data.get("user_id")),
            "ai_data": project_data.get("ai_data", {}),
            "created_at": project_data.get("created_at") or datetime.now(timezone.utc).isoformat()
        }
        # store JSON string
        self.r.set(self._proj_key(project_id), json.dumps(project))
        # index by user
        self.r.sadd(self._user_index(project["user_id"]), project_id)
        return project

    def load_project(self, project_id: str) -> Optional[Dict]:
        raw = self.r.get(self._proj_key(project_id))
        return json.loads(raw) if raw else None

    def load_user_projects(self, user_id: str) -> List[Dict]:
        ids = self.r.smembers(self._user_index(str(user_id))) or []
        projects = []
        for pid in ids:
            p = self.load_project(pid)
            if p:
                projects.append(p)
        return projects

    # Weekly summaries stored similarly
    def create_weekly_summary(self, project_id: str, payload: Dict = None) -> Dict:
        sid = str(uuid.uuid4())
        summary = {
            "id": sid,
            "project_id": project_id,
            "project_name": payload.get("project_name") if payload else None,
            "week_notes": payload.get("week_notes", {}) if payload else {},
            "ai_summary": payload.get("ai_summary", "") if payload else "",
            "created_at": payload.get("created_at") if payload else datetime.now(timezone.utc).isoformat()
        }
        self.r.set(f"weekly:{sid}", json.dumps(summary))
        self.r.rpush(f"project_weekly:{project_id}", sid)  # list of summaries per project
        return summary

    def get_weekly_summary_by_id(self, summary_id: str) -> Optional[Dict]:
        raw = self.r.get(f"weekly:{summary_id}")
        return json.loads(raw) if raw else None

    # optional: update summary
    def update_weekly_summary(self, summary_id: str, **fields) -> bool:
        cur = self.get_weekly_summary_by_id(summary_id)
        if not cur:
            return False
        cur.update(fields)
        self.r.set(f"weekly:{summary_id}", json.dumps(cur))
        return True

    def get_weekly_summaries_by_project(self, project_id: str) -> List[Dict]:
        """Get all weekly summaries for a project"""
        summary_ids = self.r.lrange(f"project_weekly:{project_id}", 0, -1) or []
        summaries = []
        for sid in summary_ids:
            s = self.get_weekly_summary_by_id(sid)
            if s:
                summaries.append(s)
        return summaries

    def delete_weekly_summary(self, summary_id: str) -> bool:
        """Delete a weekly summary"""
        summary = self.get_weekly_summary_by_id(summary_id)
        if not summary:
            return False

        project_id = summary.get('project_id')
        # Remove from weekly summary key
        self.r.delete(f"weekly:{summary_id}")
        # Remove from project's weekly list
        if project_id:
            self.r.lrem(f"project_weekly:{project_id}", 0, summary_id)
        return True

    # Project deletion
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all related data"""
        project = self.load_project(project_id)
        if not project:
            return False

        user_id = project.get('user_id')

        # Delete weekly summaries for this project
        summary_ids = self.r.lrange(f"project_weekly:{project_id}", 0, -1) or []
        for sid in summary_ids:
            self.r.delete(f"weekly:{sid}")
        self.r.delete(f"project_weekly:{project_id}")

        # Delete the project itself
        self.r.delete(self._proj_key(project_id))

        # Remove from user index
        if user_id:
            self.r.srem(self._user_index(user_id), project_id)

        return True

    # Estimation methods
    def save_estimation(self, estimation_data: Dict) -> Dict:
        """Save a project estimation"""
        estimation_id = estimation_data.get("id") or str(uuid.uuid4())
        estimation = {
            "id": estimation_id,
            "project_name": estimation_data.get("project_name"),
            "project_description": estimation_data.get("project_description"),
            "phases": estimation_data.get("phases", []),
            "total_hours": estimation_data.get("total_hours", 0),
            "user_id": str(estimation_data.get("user_id")),
            "created_at": estimation_data.get("created_at") or datetime.now(timezone.utc).isoformat()
        }

        # Store estimation
        self.r.set(f"estimation:{estimation_id}", json.dumps(estimation))
        # Index by user
        self.r.sadd(f"user_estimations:{estimation['user_id']}", estimation_id)

        return estimation

    def get_estimation_by_id(self, estimation_id: str) -> Optional[Dict]:
        """Get an estimation by ID"""
        raw = self.r.get(f"estimation:{estimation_id}")
        return json.loads(raw) if raw else None

    def load_user_estimations(self, user_id: str) -> List[Dict]:
        """Get all estimations for a user"""
        ids = self.r.smembers(f"user_estimations:{str(user_id)}") or []
        estimations = []
        for eid in ids:
            e = self.get_estimation_by_id(eid)
            if e:
                estimations.append(e)
        return estimations

    def delete_estimation(self, estimation_id: str) -> bool:
        """Delete an estimation"""
        estimation = self.get_estimation_by_id(estimation_id)
        if not estimation:
            return False

        user_id = estimation.get('user_id')

        # Delete the estimation
        self.r.delete(f"estimation:{estimation_id}")

        # Remove from user index
        if user_id:
            self.r.srem(f"user_estimations:{user_id}", estimation_id)

        return True

    def update_estimation(self, estimation_id: str, estimation_data: Dict, user_id: str = None) -> bool:
        """Update an existing estimation"""
        current = self.get_estimation_by_id(estimation_id)
        if not current:
            return False

        # Verify user ownership if provided
        if user_id and str(current.get('user_id')) != str(user_id):
            return False

        # Update fields
        current.update({
            "project_name": estimation_data.get("project_name", current.get("project_name")),
            "project_description": estimation_data.get("project_description", current.get("project_description")),
            "phases": estimation_data.get("phases", current.get("phases")),
            "total_hours": estimation_data.get("total_hours", current.get("total_hours"))
        })

        # Save updated estimation
        self.r.set(f"estimation:{estimation_id}", json.dumps(current))
        return True

    # Feature suggestions
    def save_feature_suggestions(self, project_id: str, project_name: str,
                                 audit_text: str, suggestions: str) -> Dict:
        """Save feature suggestions for a project"""
        suggestion_id = str(uuid.uuid4())
        suggestion_data = {
            "id": suggestion_id,
            "project_id": project_id,
            "project_name": project_name,
            "audit_text": audit_text,
            "suggestions": suggestions,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Store suggestion
        self.r.set(f"feature_suggestion:{suggestion_id}", json.dumps(suggestion_data))
        # Link to project
        self.r.rpush(f"project_suggestions:{project_id}", suggestion_id)

        return suggestion_data

    def get_latest_feature_suggestions(self, project_id: str) -> Optional[Dict]:
        """Get the most recent feature suggestions for a project"""
        # Get the list of suggestion IDs for this project
        suggestion_ids = self.r.lrange(f"project_suggestions:{project_id}", 0, -1)

        if not suggestion_ids:
            return None

        # Get the last (most recent) suggestion ID
        latest_id = suggestion_ids[-1]

        # Retrieve the suggestion data
        raw = self.r.get(f"feature_suggestion:{latest_id}")
        return json.loads(raw) if raw else None

    # Section states for collapsible UI
    def save_section_state(self, project_id: str, section_id: str,
                          is_expanded: bool, user_id: str) -> bool:
        """Save the state of a collapsible section"""
        key = f"section_state:{user_id}:{project_id}"
        # Store as hash: section_id -> is_expanded (1 or 0)
        self.r.hset(key, section_id, 1 if is_expanded else 0)
        return True

    def get_section_states(self, project_id: str, user_id: str) -> Dict:
        """Get all section states for a project and user"""
        key = f"section_state:{user_id}:{project_id}"
        states = self.r.hgetall(key)
        if not states:
            return {}

        # Convert string values to booleans
        return {k: (v == '1' or v == 1 or v == True) for k, v in states.items()}


class RedisUserStorage:
    """Manages user data persistence in Redis"""

    def __init__(self, client=None):
        self.r = client or get_redis_client()

    def _user_key(self, user_id: str) -> str:
        return f"user:{user_id}"

    def _user_email_index(self, email: str) -> str:
        return f"user_email:{email}"

    def create_user(self, email: str, name: str, password_hash: str, plan_type: str = 'free') -> Dict:
        """Create a new user"""
        # Check if user already exists
        existing_id = self.r.get(self._user_email_index(email))
        if existing_id:
            raise ValueError(f"Email '{email}' is already registered")

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        user_data = {
            'id': user_id,
            'email': email,
            'name': name,
            'password_hash': password_hash,
            'created_at': now,
            'updated_at': now,
            'is_active': True,
            'clickup_token': None,
            'linear_token': None,
            'last_login': None,
            # OAuth fields
            'oauth_provider': None,  # 'google', 'github', None (for regular users)
            'oauth_id': None,  # Unique ID from OAuth provider
            'avatar_url': None,  # Profile picture URL from OAuth
            # Subscription fields
            'plan_type': plan_type,  # 'free' or 'pro'
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'subscription_status': None,  # 'trialing', 'active', 'canceled', 'past_due'
            'subscription_current_period_end': None,
            'trial_end': None
        }

        # Store user data
        self.r.set(self._user_key(user_id), json.dumps(user_data))
        # Create email index
        self.r.set(self._user_email_index(email), user_id)

        return {
            'id': user_id,
            'email': email,
            'name': name,
            'created_at': now,
            'updated_at': now,
            'is_active': True,
            'plan_type': plan_type
        }

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get a user by their ID"""
        if not user_id:
            return None

        raw = self.r.get(self._user_key(user_id))
        if not raw:
            return None

        user = json.loads(raw)
        user['is_active'] = bool(user.get('is_active', True))
        return user

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get a user by their email address"""
        user_id = self.r.get(self._user_email_index(email))
        if not user_id:
            return None

        return self.get_user_by_id(user_id)

    def update_last_login(self, user_id: str):
        """Update the last login timestamp for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return

        now = datetime.now(timezone.utc).isoformat()
        user['last_login'] = now
        user['updated_at'] = now

        self.r.set(self._user_key(user_id), json.dumps(user))

    def update_user(self, user_id: str, **updates) -> Dict:
        """Update user information"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        if not updates:
            return user

        allowed_fields = {'name', 'email', 'password_hash'}
        updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}

        if not updates:
            return user

        # If email is being changed, update the email index
        old_email = user.get('email')
        new_email = updates.get('email')

        if new_email and new_email != old_email:
            # Check if new email is already taken
            existing_id = self.r.get(self._user_email_index(new_email))
            if existing_id and existing_id != user_id:
                raise ValueError(f"Email '{new_email}' is already in use")

            # Delete old email index
            self.r.delete(self._user_email_index(old_email))
            # Create new email index
            self.r.set(self._user_email_index(new_email), user_id)

        # Update user data
        user.update(updates)
        user['updated_at'] = datetime.now(timezone.utc).isoformat()

        self.r.set(self._user_key(user_id), json.dumps(user))
        return user

    def save_user_clickup_token(self, user_id: str, token: str) -> bool:
        """Save ClickUp API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user['clickup_token'] = token
        user['updated_at'] = datetime.now(timezone.utc).isoformat()

        self.r.set(self._user_key(user_id), json.dumps(user))
        return True

    def get_user_clickup_token(self, user_id: str) -> Optional[str]:
        """Get ClickUp API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        return user.get('clickup_token')

    def delete_user_clickup_token(self, user_id: str) -> bool:
        """Delete ClickUp API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user['clickup_token'] = None
        user['updated_at'] = datetime.now(timezone.utc).isoformat()

        self.r.set(self._user_key(user_id), json.dumps(user))
        return True

    def save_user_linear_token(self, user_id: str, token: str) -> bool:
        """Save Linear API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user['linear_token'] = token
        user['updated_at'] = datetime.now(timezone.utc).isoformat()

        self.r.set(self._user_key(user_id), json.dumps(user))
        return True

    def get_user_linear_token(self, user_id: str) -> Optional[str]:
        """Get Linear API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        return user.get('linear_token')

    def delete_user_linear_token(self, user_id: str) -> bool:
        """Delete Linear API token for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        user['linear_token'] = None
        user['updated_at'] = datetime.now(timezone.utc).isoformat()

        self.r.set(self._user_key(user_id), json.dumps(user))
        return True

    # Subscription management methods
    def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """Get user's subscription information"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None

        return {
            'plan_type': user.get('plan_type', 'free'),
            'stripe_customer_id': user.get('stripe_customer_id'),
            'stripe_subscription_id': user.get('stripe_subscription_id'),
            'subscription_status': user.get('subscription_status'),
            'subscription_current_period_end': user.get('subscription_current_period_end'),
            'trial_end': user.get('trial_end')
        }

    def update_user_subscription(self, user_id: str, **fields) -> bool:
        """Update user's subscription information"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # Allowed subscription fields to update
        allowed_fields = {
            'plan_type', 'stripe_customer_id', 'stripe_subscription_id',
            'subscription_status', 'subscription_current_period_end', 'trial_end'
        }

        # Update only allowed fields
        for key, value in fields.items():
            if key in allowed_fields:
                user[key] = value

        user['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.r.set(self._user_key(user_id), json.dumps(user))
        return True

    def get_user_usage_counts(self, user_id: str) -> Dict:
        """Get count of user's projects, estimations, and feature suggestions"""
        # Count projects
        project_ids = self.r.smembers(f"user_projects:{user_id}") or set()
        projects_count = len(project_ids)

        # Count estimations
        estimation_ids = self.r.smembers(f"user_estimations:{user_id}") or set()
        estimations_count = len(estimation_ids)

        # Count feature suggestions
        suggestions_count = 0
        for pid in project_ids:
            suggestion_ids = self.r.lrange(f"project_suggestions:{pid}", 0, -1) or []
            suggestions_count += len(suggestion_ids)

        return {
            'projects': projects_count,
            'estimations': estimations_count,
            'feature_suggestions': suggestions_count
        }

    def get_or_create_oauth_user(self, provider: str, oauth_id: str, email: str, name: str, avatar_url: str = None, plan_type: str = 'free') -> Dict:
        """
        Get existing OAuth user or create a new one

        Args:
            provider: OAuth provider name ('google', 'github', etc.)
            oauth_id: Unique ID from OAuth provider
            email: User's email from OAuth
            name: User's name from OAuth
            avatar_url: Profile picture URL (optional)
            plan_type: Subscription plan (default: 'free')

        Returns:
            User dict with all user information
        """
        # Try to find existing user by email
        existing_user = self.get_user_by_email(email)

        if existing_user:
            # Update OAuth info if not already set
            if not existing_user.get('oauth_provider'):
                existing_user['oauth_provider'] = provider
                existing_user['oauth_id'] = oauth_id
                existing_user['avatar_url'] = avatar_url
                existing_user['updated_at'] = datetime.now(timezone.utc).isoformat()
                self.r.set(self._user_key(existing_user['id']), json.dumps(existing_user))
            return existing_user

        # Create new OAuth user
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        user_data = {
            'id': user_id,
            'email': email,
            'name': name,
            'password_hash': None,  # OAuth users don't have passwords
            'created_at': now,
            'updated_at': now,
            'is_active': True,
            'clickup_token': None,
            'linear_token': None,
            'last_login': now,
            # OAuth fields
            'oauth_provider': provider,
            'oauth_id': oauth_id,
            'avatar_url': avatar_url,
            # Subscription fields
            'plan_type': plan_type,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'subscription_status': None,
            'subscription_current_period_end': None,
            'trial_end': None
        }

        # Store user data
        self.r.set(self._user_key(user_id), json.dumps(user_data))
        # Create email index
        self.r.set(self._user_email_index(email), user_id)

        return user_data