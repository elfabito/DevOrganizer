"""
User storage module for DevOrganizer
Handles user data persistence in SQLite database
"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

class UserStorage:
    """Manages user data persistence in SQLite database"""
    
    def __init__(self, db_file: str = "projects.db"):
        """
        Initialize user storage with a SQLite database
        
        Args:
            db_file: Path to the SQLite database file
        """
        self.db_file = db_file
        self._init_database()
    
    def _get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login TEXT,
                is_active BOOLEAN DEFAULT 1,
                clickup_token TEXT,
                reset_token TEXT,
                reset_token_expires TEXT
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_email 
            ON users(email)
        ''')
        
        # Add reset token columns if they don't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token_expires TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add subscription columns if they don't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN plan_type TEXT DEFAULT "free"')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN subscription_status TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN stripe_customer_id TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN trial_end TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN subscription_current_period_end TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
        conn.close()
    
    def create_user(self, email: str, name: str, password_hash: str) -> Dict[str, Any]:
        """
        Create a new user
        
        Args:
            email: User's email address (must be unique)
            name: User's full name
            password_hash: Hashed password
            
        Returns:
            Dictionary containing the created user data
            
        Raises:
            sqlite3.IntegrityError: If a user with the email already exists
        """
        user_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (id, email, name, password_hash, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, email, name, password_hash, now, now))
            
            conn.commit()
            
            return {
                'id': user_id,
                'email': email,
                'name': name,
                'created_at': now,
                'updated_at': now,
                'is_active': True
            }
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed: users.email' in str(e):
                raise ValueError(f"Email '{email}' is already registered")
            raise
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by their ID
        
        Args:
            user_id: The user's unique ID
            
        Returns:
            User data as a dictionary, or None if not found
        """
        print(f"[DEBUG] get_user_by_id called with user_id: {user_id}, type: {type(user_id)}")
        if not user_id:
            print("[DEBUG] user_id is empty or None")
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, name, password_hash, created_at, updated_at, last_login, is_active, clickup_token,
                   plan_type, subscription_status, stripe_customer_id, stripe_subscription_id, 
                   trial_end, subscription_current_period_end
            FROM users
            WHERE id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        user = dict(row)
        user['is_active'] = bool(user.get('is_active', 1))
        # Default to 'free' if plan_type is not set
        if not user.get('plan_type'):
            user['plan_type'] = 'free'
        return user
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by their email address
        
        Args:
            email: The user's email address
            
        Returns:
            User data as a dictionary (including password_hash), or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, name, password_hash, created_at, updated_at, last_login, is_active, clickup_token,
                   plan_type, subscription_status, stripe_customer_id, stripe_subscription_id,
                   trial_end, subscription_current_period_end
            FROM users
            WHERE email = ?
        ''', (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        user = dict(row)
        user['is_active'] = bool(user.get('is_active', 1))
        # Default to 'free' if plan_type is not set
        if not user.get('plan_type'):
            user['plan_type'] = 'free'
        return user
    
    def update_last_login(self, user_id: str):
        """
        Update the last login timestamp for a user
        
        Args:
            user_id: The user's unique ID
        """
        now = datetime.utcnow().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users
            SET last_login = ?, updated_at = ?
            WHERE id = ?
        ''', (now, now, user_id))
        
        conn.commit()
        conn.close()
    
    def update_user(self, user_id: str, **updates) -> Dict[str, Any]:
        """
        Update user information
        
        Args:
            user_id: The user's unique ID
            **updates: Dictionary of fields to update
                
        Returns:
            Updated user data
            
        Raises:
            ValueError: If user not found or update fails
        """
        if not updates:
            return self.get_user_by_id(user_id)
        
        allowed_fields = {'name', 'email', 'password_hash'}
        updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}
        
        if not updates:
            return self.get_user_by_id(user_id)
        
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        set_clause = ', '.join(f"{field} = ?" for field in updates.keys())
        values = list(updates.values())
        values.append(user_id)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'''
                UPDATE users
                SET {set_clause}
                WHERE id = ?
            ''', values)
            
            if cursor.rowcount == 0:
                conn.close()
                raise ValueError(f"User with ID {user_id} not found")
            
            conn.commit()
            return self.get_user_by_id(user_id)
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed: users.email' in str(e):
                raise ValueError(f"Email '{updates.get('email')}' is already in use")
            raise
        finally:
            conn.close()

    def save_user_clickup_token(self, user_id: str, token: str) -> bool:
        """
        Save ClickUp API token for a user

        Args:
            user_id: The user's unique ID
            token: The ClickUp API token

        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.utcnow().isoformat()
            cursor.execute('''
                UPDATE users
                SET clickup_token = ?, updated_at = ?
                WHERE id = ?
            ''', (token, now, user_id))

            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"[ERROR] Failed to save ClickUp token: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_user_clickup_token(self, user_id: str) -> Optional[str]:
        """
        Get ClickUp API token for a user

        Args:
            user_id: The user's unique ID

        Returns:
            The ClickUp token or None if not set
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT clickup_token
                FROM users
                WHERE id = ?
            ''', (user_id,))

            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None
        finally:
            conn.close()

    def delete_user_clickup_token(self, user_id: str) -> bool:
        """
        Delete ClickUp API token for a user

        Args:
            user_id: The user's unique ID

        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.utcnow().isoformat()
            cursor.execute('''
                UPDATE users
                SET clickup_token = NULL, updated_at = ?
                WHERE id = ?
            ''', (now, user_id))

            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"[ERROR] Failed to delete ClickUp token: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def create_password_reset_token(self, email: str) -> Optional[str]:
        """
        Create a password reset token for a user
        
        Args:
            email: The user's email address
            
        Returns:
            The reset token if successful, None if user not found
        """
        user = self.get_user_by_email(email)
        if not user:
            return None
        
        # Generate a secure random token
        reset_token = str(uuid.uuid4())
        
        # Token expires in 1 hour
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users
                SET reset_token = ?, reset_token_expires = ?, updated_at = ?
                WHERE email = ?
            ''', (reset_token, expires_at, datetime.utcnow().isoformat(), email))
            
            conn.commit()
            return reset_token
        except Exception as e:
            print(f"[ERROR] Failed to create reset token: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def verify_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a password reset token and return the user if valid
        
        Args:
            token: The reset token to verify
            
        Returns:
            User data if token is valid, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, email, name, reset_token_expires
                FROM users
                WHERE reset_token = ?
            ''', (token,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            user = dict(row)
            
            # Check if token has expired
            expires_at = datetime.fromisoformat(user['reset_token_expires'])
            if datetime.utcnow() > expires_at:
                return None
            
            return user
        finally:
            conn.close()
    
    def reset_password_with_token(self, token: str, new_password_hash: str) -> bool:
        """
        Reset a user's password using a valid reset token
        
        Args:
            token: The reset token
            new_password_hash: The new hashed password
            
        Returns:
            True if successful, False otherwise
        """
        user = self.verify_reset_token(token)
        if not user:
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.utcnow().isoformat()
            cursor.execute('''
                UPDATE users
                SET password_hash = ?, 
                    reset_token = NULL, 
                    reset_token_expires = NULL,
                    updated_at = ?
                WHERE id = ?
            ''', (new_password_hash, now, user['id']))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"[ERROR] Failed to reset password: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_user_subscription(
        self,
        user_id: str,
        plan_type: Optional[str] = None,
        subscription_status: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        trial_end: Optional[str] = None,
        subscription_current_period_end: Optional[str] = None
    ) -> bool:
        """
        Update user's subscription information
        
        Args:
            user_id: The user's ID
            plan_type: The plan type ('free' or 'pro')
            subscription_status: Status ('trialing', 'active', 'past_due', 'canceled', etc.)
            stripe_customer_id: Stripe customer ID
            stripe_subscription_id: Stripe subscription ID
            trial_end: Trial end date
            subscription_current_period_end: Current subscription period end date
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            now = datetime.utcnow().isoformat()
            
            # Build dynamic UPDATE query based on provided parameters
            updates = ['updated_at = ?']
            params = [now]
            
            if plan_type is not None:
                updates.append('plan_type = ?')
                params.append(plan_type)
            
            if subscription_status is not None:
                updates.append('subscription_status = ?')
                params.append(subscription_status)
            
            if stripe_customer_id is not None:
                updates.append('stripe_customer_id = ?')
                params.append(stripe_customer_id)
            
            if stripe_subscription_id is not None:
                updates.append('stripe_subscription_id = ?')
                params.append(stripe_subscription_id)
            
            if trial_end is not None:
                updates.append('trial_end = ?')
                params.append(trial_end)
            
            if subscription_current_period_end is not None:
                updates.append('subscription_current_period_end = ?')
                params.append(subscription_current_period_end)
            
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                print(f"[INFO] Updated subscription for user {user_id}: plan_type={plan_type}, status={subscription_status}")
            
            return success
        except Exception as e:
            print(f"[ERROR] Failed to update subscription: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def clear_reset_token(self, user_id: str) -> bool:
        """
        Clear the reset token for a user
        
        Args:
            user_id: The user's unique ID
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users
                SET reset_token = NULL, reset_token_expires = NULL, updated_at = ?
                WHERE id = ?
            ''', (datetime.utcnow().isoformat(), user_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"[ERROR] Failed to clear reset token: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
