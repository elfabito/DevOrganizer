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
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_email 
            ON users(email)
        ''')
        
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
            SELECT id, email, name, password_hash, created_at, updated_at, last_login, is_active
            FROM users
            WHERE id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        user = dict(row)
        user['is_active'] = bool(user.get('is_active', 1))
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
            SELECT id, email, name, password_hash, created_at, updated_at, last_login, is_active
            FROM users
            WHERE email = ?
        ''', (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        user = dict(row)
        user['is_active'] = bool(user.get('is_active', 1))
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
