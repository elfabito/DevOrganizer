"""
Storage module for Dev Project Organizer using SQLite
Handles saving and loading projects from SQLite database
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
import uuid
from flask import current_app


def get_db_connection() -> sqlite3.Connection:
    """
    Get a database connection with proper configuration
    
    Returns:
        sqlite3.Connection: A connection to the SQLite database
    """
    try:
        # Get database path from config or use default
        db_path = current_app.config.get('DATABASE', 'projects.db')
        
        # Ensure the directory exists
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:  # Only try to create directory if path is not empty
            os.makedirs(db_dir, exist_ok=True)
        
        current_app.logger.debug(f"Connecting to database at: {os.path.abspath(db_path)}")
        
        # Create connection with proper settings
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-style access
        
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Verify we can execute a test query
        conn.execute('PRAGMA foreign_keys')
        
        return conn
        
    except Exception as e:
        current_app.logger.error(f"Failed to connect to database: {str(e)}", exc_info=True)
        raise

def normalize_for_sqlite(val):
    """Normalize values to types sqlite3 accepts."""
    if val is None:
        return None
    # sqlite accepts str, int, float, bytes; bool is subclass of int
    if isinstance(val, (str, int, float, bytes, bool)):
        return val
    # Convert Decimal, UUID, datetime, etc.
    try:
        from decimal import Decimal
        import uuid as _uuid
        if isinstance(val, Decimal):
            return float(val)
        if isinstance(val, _uuid.UUID):
            return str(val)
    except Exception:
        pass
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, (list, dict, tuple, set)):
        return json.dumps(val, default=str)
    # Fallback: stringify
    return str(val)
class ProjectStorageSQLite:
    """Manages project data persistence using SQLite database"""
    
    def __init__(self, db_file: str = "projects.db"):
        """
        Initialize storage with a SQLite database
        
        Args:
            db_file: Path to the SQLite database file
        """
        self.db_file = db_file
        self._init_database()
    
    def _init_database(self):
        """Create database and tables if they don't exist"""
        conn = sqlite3.connect(self.db_file)
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        # Create users table
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
        
        # Create projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                brief TEXT NOT NULL,
                ai_data TEXT NOT NULL,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create weekly summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                week_start_date TEXT NOT NULL,
                week_notes TEXT NOT NULL,
                ai_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for weekly_summaries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_project 
            ON weekly_summaries(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week 
            ON weekly_summaries(week_start_date)
        ''')
        
        # Create section_states table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_states (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                is_expanded BOOLEAN NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, section_id, user_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create feature suggestions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_suggestions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                audit_text TEXT NOT NULL,
                suggestions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Create estimations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estimations (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                project_description TEXT NOT NULL,
                phases TEXT NOT NULL,
                total_hours INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Create index for faster searches
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON projects(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_user 
            ON estimations(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_created 
            ON estimations(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_created 
            ON weekly_summaries(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_project 
            ON weekly_summaries(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week 
            ON weekly_summaries(week_start_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_suggestions_project 
            ON feature_suggestions(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_created_at 
            ON estimations(created_at DESC)
        ''')
        
        # Add indexes for section_states queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_section_states_project
            ON section_states(project_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_section_states_user
            ON section_states(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_section_states_updated 
            ON section_states(updated_at DESC)
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_file)
    
    def load_all_projects(self) -> List[Dict]:
        """Load all projects from the database (for backward compatibility)"""
        return self.load_user_projects(None)
        
    def load_user_projects(self, user_id: Optional[str]) -> List[Dict]:
        """
        Load projects for a specific user
        
        Args:
            user_id: The user ID to filter by. If None, returns all projects.
            
        Returns:
            List of project dictionaries
        """
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        logger.debug(f"[LOAD_USER_PROJECTS] Loading projects for user_id: {user_id}")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT id, name, created_at, brief, ai_data, user_id
            FROM projects
        '''
        params = ()
        
        if user_id is not None:
            query += ' WHERE user_id = ?'
            params = (user_id,)
            
        query += ' ORDER BY created_at DESC'
        
        logger.debug(f"[LOAD_USER_PROJECTS] Executing query: {query} with params: {params}")
        
        cursor.execute(query, params)
        
        projects = []
        rows = cursor.fetchall()
        logger.debug(f"[LOAD_USER_PROJECTS] Found {len(rows)} projects")
        
        if rows and cursor.description:  # Check if there are results and description is available
            columns = [desc[0] for desc in cursor.description]  # Get column names
            
            for row in rows:
                # Create a dictionary by zipping column names with row values
                project = dict(zip(columns, row))
                logger.debug(f"[LOAD_USER_PROJECTS] Processing project: {project.get('name')} (id: {project.get('id')}, user_id: {project.get('user_id')})")
                
                # Parse AI data from JSON string if it exists
                if project.get('ai_data'):
                    try:
                        project['ai_data'] = json.loads(project['ai_data'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"[LOAD_USER_PROJECTS] Error parsing AI data for project {project.get('id')}: {str(e)}")
                        project['ai_data'] = {}
                
                projects.append(project)
        else:
            logger.debug("[LOAD_USER_PROJECTS] No projects found or no cursor description")
            
        conn.close()
        return projects
    
    def load_project(self, project_id: str) -> Optional[Dict]:
        """
        Load a single project by ID
        
        Args:
            project_id: The ID of the project to load
            
        Returns:
            Project data as a dictionary, or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, created_at, brief, ai_data, user_id
            FROM projects
            WHERE id = ?
        ''', (project_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description]
        # Create dictionary with column names as keys
        project = dict(zip(columns, row))
        
        # Parse AI data if it exists
        if project.get('ai_data'):
            try:
                project['ai_data'] = json.loads(project['ai_data'])
            except (json.JSONDecodeError, TypeError):
                project['ai_data'] = {}
                
        return project
    
    def save_project(self, project_data: Dict) -> str:
        """
        Save a project to the database
        
        Args:
            project_data: Dictionary containing project data
                Required keys: name, brief, ai_data, user_id
                Optional keys: id (auto-generated if not provided), created_at (defaults to now)
                
        Returns:
            The ID of the saved project
            
        Raises:
            ValueError: If required fields are missing or saving fails
        """
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        logger.debug(f"[SAVE_PROJECT] Received project data: {project_data}")
        
        project_id = project_data.get('id') or str(uuid.uuid4())
        created_at = project_data.get('created_at') or datetime.utcnow().isoformat()
        user_id = project_data.get('user_id')
        
        logger.debug(f"[SAVE_PROJECT] user_id from project_data: {user_id}")
        
        if not user_id:
            raise ValueError("user_id is required")
            
        # Convert AI data to JSON string
        ai_data = project_data.get('ai_data', {})
        if isinstance(ai_data, dict):
            ai_data = json.dumps(ai_data)
            
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO projects 
                (id, name, created_at, brief, ai_data, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                project_id,
                project_data['name'],
                created_at,
                project_data.get('brief', ''),
                ai_data,
                user_id
            ))
            
            conn.commit()
            
            # Return the complete project data
            return {
                'id': project_id,
                'name': project_data['name'],
                'brief': project_data.get('brief', ''),
                'created_at': created_at,
                'user_id': user_id,
                'ai_data': project_data.get('ai_data', {})
            }
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            if 'FOREIGN KEY constraint failed' in str(e):
                raise ValueError(f"Invalid user_id: {user_id}")
            raise ValueError(f"Failed to save project: {str(e)}")
            
        finally:
            conn.close()
    
    def save_estimation(self, estimation_data: Dict) -> Dict:
        """
        Save an estimation to the database (SQLite)

        Args:
            estimation_data (dict): Dictionary containing estimation data.
                Required keys: project_name, project_description, phases, total_hours, user_id
                Optional keys: id (auto-generated if not provided), created_at (defaults to now)

        Returns:
            dict: The saved estimation data (as stored in the database)

        Raises:
            ValueError: If required fields are missing or saving fails.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        # ✅ Prepare estimation data
        phases_value = estimation_data['phases']
        if not isinstance(phases_value, str):
            phases_value = json.dumps(phases_value)
        try:
            # ✅ Validate required fields
            required_fields = ['project_name', 'project_description', 'phases', 'total_hours', 'user_id']
            missing_fields = [f for f in required_fields if f not in estimation_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            # ✅ Generate ID and timestamps if not provided
            estimation_id = estimation_data.get('id') or str(uuid.uuid4())
            created_at = estimation_data.get('created_at') or datetime.utcnow().isoformat()

            # ✅ Prepare estimation data
            estimation = {
                'id': estimation_id,
                'project_name': estimation_data['project_name'],
                'project_description': estimation_data['project_description'],
                'phases':  phases_value,  # Puede ser JSON string
                'total_hours': int(estimation_data['total_hours']),
                'created_at': created_at,
                'user_id': estimation_data['user_id']
            }

            # ✅ Check if estimation already exists (update if yes, insert if not)
            cursor.execute("SELECT id FROM estimations WHERE id = ?", (estimation_id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                    UPDATE estimations
                    SET project_name = ?, project_description = ?, phases = ?, 
                        total_hours = ?, created_at = ?, user_id = ?
                    WHERE id = ?
                ''', (
                    estimation['project_name'],
                    estimation['project_description'],
                    phases_value,
                    estimation['total_hours'],
                    estimation['created_at'],
                    estimation['user_id'],
                    estimation['id'],
                ))
            else:
                cursor.execute('''
                    INSERT INTO estimations (id, project_name, project_description, phases, 
                                            total_hours, created_at, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    estimation['id'],
                    estimation['project_name'],
                    estimation['project_description'],
                    phases_value,
                    estimation['total_hours'],
                    estimation['created_at'],
                    estimation['user_id']
                ))

            conn.commit()
            return estimation

        except Exception as e:
            conn.rollback()
            raise ValueError(f"Failed to save estimation: {str(e)}")

        finally:
            conn.close()
    
    def load_all_estimations(self) -> List[Dict]:
        """Load all estimations from the database (for backward compatibility)"""
        return self.load_user_estimations(None)
        
    def load_user_estimations(self, user_id: Optional[Union[str, int]]) -> List[Dict]:
        """
        Load estimations for a specific user
        
        Args:
            user_id: The user ID to filter by. If None, returns all estimations.
                   Can be string or int, will be converted to string.
            
        Returns:
            List of estimation dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT id, project_name, project_description, phases, total_hours, created_at, user_id
            FROM estimations
        '''
        params = ()
        
        if user_id is not None:
            query += ' WHERE user_id = ?'
            # Ensure user_id is a string for the database query
            params = (str(user_id),)
            
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        
        estimations = []
        columns = [desc[0] for desc in cursor.description]  # Get column names
        for row in cursor.fetchall():
            # Create a dictionary by zipping column names with row values
            estimation = dict(zip(columns, row))
            # Parse phases from JSON string if it exists
            if estimation.get('phases'):
                try:
                    estimation['phases'] = json.loads(estimation['phases'])
                except (json.JSONDecodeError, TypeError):
                    estimation['phases'] = []
            else:
                estimation['phases'] = []
            estimations.append(estimation)
            
        conn.close()
        return estimations
    
    def get_estimation_by_id(self, estimation_id: str) -> Optional[Dict]:
        """
        Get an estimation by its ID
        
        Args:
            estimation_id: The ID of the estimation to retrieve
            
        Returns:
            The estimation data as a dictionary, or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, project_description, phases, total_hours, created_at, user_id
            FROM estimations
            WHERE id = ?
        ''', (estimation_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
            
        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description]
        # Create dictionary with column names as keys
        estimation = dict(zip(columns, row))
        
        # Parse phases if it exists
        if estimation.get('phases'):
            try:
                estimation['phases'] = json.loads(estimation['phases'])
            except (json.JSONDecodeError, TypeError):
                estimation['phases'] = []
        else:
            estimation['phases'] = []
            
        return estimation
    
            
    def update_estimation(self, estimation_id: str, updated_data: Dict, user_id: Optional[str] = None) -> bool:
        """
        Update an existing estimation in the database.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Optional: verify that the estimation belongs to this user
            if user_id is not None:
                cursor.execute('SELECT id FROM estimations WHERE id = ? AND user_id = ?', 
                            (estimation_id, user_id))
                if not cursor.fetchone():
                    raise ValueError("Estimation not found or does not belong to this user")

            # Normalize updated_data values for sqlite
            keys = list(updated_data.keys())
            if not keys:
                return False

            normalized_values = []
            for k in keys:
                v = updated_data[k]
                # Ensure phases is stored as JSON text
                if k == 'phases' and not isinstance(v, str):
                    v = json.dumps(v)
                normalized_values.append(normalize_for_sqlite(v))

            # Append estimation_id as last parameter
            normalized_values.append(estimation_id)

            # Build dynamic SET clause safely
            set_clause = ", ".join([f"{key} = ?" for key in keys])
            cursor.execute(f"UPDATE estimations SET {set_clause} WHERE id = ?", tuple(normalized_values))

            if cursor.rowcount == 0:
                raise ValueError(f"Estimation with ID {estimation_id} not found")

            conn.commit()
            return True

        except sqlite3.Error as e:
            conn.rollback()
            raise ValueError(f"Failed to update estimation: {str(e)}")

        finally:
            conn.close()
    
    def delete_estimation(self, estimation_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete an estimation by ID, optionally checking user ownership
        
        Args:
            estimation_id: The ID of the estimation to delete
            user_id: Optional user ID to verify estimation ownership
            
        Returns:
            True if the estimation was deleted, False if not found or not owned by user
            
        Raises:
            ValueError: If deletion fails
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if user_id is not None:
                # Verify estimation belongs to user before deleting
                cursor.execute('SELECT id FROM estimations WHERE id = ? AND user_id = ?', 
                             (estimation_id, user_id))
                if not cursor.fetchone():
                    return False
            
            cursor.execute('DELETE FROM estimations WHERE id = ?', (estimation_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
            
        except sqlite3.Error as e:
            conn.rollback()
            raise ValueError(f"Failed to delete estimation: {str(e)}")
            
        finally:
            conn.close()
            
    def save_section_state(self, project_id: str, section_id: str, is_expanded: bool, user_id: str) -> bool:
        """
        Save the state of a collapsible section for a project

        Args:
            project_id: ID of the project
            section_id: ID of the section
            is_expanded: Whether the section is expanded
            user_id: ID of the user

        Returns:
            bool: True if save was successful
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.execute('PRAGMA foreign_keys = ON')
            cursor = conn.cursor()

            # Log the operation
            import logging
            logging.basicConfig(level=logging.DEBUG)
            logger = logging.getLogger(__name__)
            logger.debug(f"[SAVE_SECTION_STATE] Saving state - project_id: {project_id}, section_id: {section_id}, user_id: {user_id}, is_expanded: {is_expanded}")

            cursor.execute('''
                INSERT INTO section_states (id, project_id, section_id, user_id, is_expanded, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, section_id, user_id)
                DO UPDATE SET
                    is_expanded = excluded.is_expanded,
                    updated_at = excluded.updated_at
            ''', (
                str(uuid.uuid4()),
                project_id,
                section_id,
                user_id,
                1 if is_expanded else 0,  # Ensure boolean is stored as 0 or 1
                datetime.now().isoformat()
            ))

            conn.commit()
            logger.debug(f"[SAVE_SECTION_STATE] Successfully saved section state")
            return True

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"[SAVE_SECTION_STATE] Database error saving section state: {e}", exc_info=True)
            return False
        except Exception as e:
            if conn:
                conn.rollback()
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"[SAVE_SECTION_STATE] Unexpected error saving section state: {e}", exc_info=True)
            return False
        finally:
            if conn:
                conn.close()
    
    def get_section_states(self, project_id: str, user_id: str) -> Dict[str, bool]:
        """
        Get all section states for a project for a specific user

        Args:
            project_id: ID of the project
            user_id: ID of the user

        Returns:
            Dict[str, bool]: Dictionary mapping section IDs to their expanded state
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.execute('PRAGMA foreign_keys = ON')
            cursor = conn.cursor()

            # Log the operation
            import logging
            logging.basicConfig(level=logging.DEBUG)
            logger = logging.getLogger(__name__)
            logger.debug(f"[GET_SECTION_STATES] Loading states - project_id: {project_id}, user_id: {user_id}")

            cursor.execute(
                "SELECT section_id, is_expanded FROM section_states WHERE project_id = ? AND user_id = ?",
                (project_id, user_id)
            )

            results = {row[0]: bool(row[1]) for row in cursor.fetchall()}
            logger.debug(f"[GET_SECTION_STATES] Retrieved {len(results)} section states: {results}")
            return results

        except sqlite3.Error as e:
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"[GET_SECTION_STATES] Database error loading section states: {e}", exc_info=True)
            return {}
        except Exception as e:
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"[GET_SECTION_STATES] Unexpected error loading section states: {e}", exc_info=True)
            return {}
        finally:
            if conn:
                conn.close()

    def save_feature_suggestions(self, project_id: str, project_name: str, audit_text: str, suggestions) -> Dict:
        """
        Save feature suggestions to the database

        Args:
            project_id: ID of the project
            project_name: Name of the project
            audit_text: The audit text provided by the user
            suggestions: AI-generated suggestions (string, dict, or list - will be converted to string)

        Returns:
            Dict: The saved feature suggestion data including ID
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.execute('PRAGMA foreign_keys = ON')
            cursor = conn.cursor()

            # Create new feature suggestion
            suggestion_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()

            # Convert suggestions to string if it's a dict or list
            if isinstance(suggestions, (dict, list)):
                suggestions_str = json.dumps(suggestions)
            else:
                suggestions_str = str(suggestions)

            cursor.execute('''
                INSERT INTO feature_suggestions (id, project_id, project_name, audit_text, suggestions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                suggestion_id,
                project_id,
                project_name,
                audit_text,
                suggestions_str,
                created_at
            ))

            conn.commit()

            return {
                'id': suggestion_id,
                'project_id': project_id,
                'project_name': project_name,
                'audit_text': audit_text,
                'suggestions': suggestions,  # Return original format
                'created_at': created_at
            }

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"Database error saving feature suggestions: {e}", exc_info=True)
            raise ValueError(f"Failed to save feature suggestions: {str(e)}")
        finally:
            if conn:
                conn.close()

    def get_feature_suggestions_by_project(self, project_id: str) -> List[Dict]:
        """
        Get all feature suggestions for a specific project

        Args:
            project_id: ID of the project

        Returns:
            List[Dict]: List of feature suggestion dictionaries
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, project_id, project_name, audit_text, suggestions, created_at
                FROM feature_suggestions
                WHERE project_id = ?
                ORDER BY created_at DESC
            ''', (project_id,))

            suggestions = []
            for row in cursor.fetchall():
                suggestions.append(dict(row))

            return suggestions

        except sqlite3.Error as e:
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"Database error loading feature suggestions: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()

    def get_feature_suggestion_by_id(self, suggestion_id: str) -> Optional[Dict]:
        """
        Get a specific feature suggestion by ID

        Args:
            suggestion_id: ID of the feature suggestion

        Returns:
            Optional[Dict]: Feature suggestion data or None if not found
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, project_id, project_name, audit_text, suggestions, created_at
                FROM feature_suggestions
                WHERE id = ?
            ''', (suggestion_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

        except sqlite3.Error as e:
            import logging
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
            logger.error(f"Database error loading feature suggestion: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
