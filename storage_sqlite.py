"""
Storage module for Dev Project Organizer using SQLite
Handles saving and loading projects from SQLite database
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import uuid


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
        cursor = conn.cursor()
        
        # Create projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                brief TEXT NOT NULL,
                ai_data TEXT NOT NULL
            )
        ''')
        
        # Create weekly summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_summaries (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                week_notes TEXT NOT NULL,
                ai_summary TEXT
            )
        ''')
        
        # Create section states table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_states (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                is_expanded BOOLEAN NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, section_id)
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
                created_at TEXT NOT NULL
            )
        ''')
        
        # Create index for faster searches
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON projects(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_summaries_created_at 
            ON weekly_summaries(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_summaries_project 
            ON weekly_summaries(project_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_suggestions_project 
            ON feature_suggestions(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_created_at 
            ON estimations(created_at DESC)
        ''')
        
        # Add index for section_states queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_section_states_project 
            ON section_states(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_section_states_updated 
            ON section_states(updated_at DESC)
        ''')
        
        conn.commit()
        conn.close()
    
    def load_all_projects(self) -> List[Dict]:
        """
        Load all projects from database
        
        Returns:
            List of project dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, created_at, brief, ai_data 
            FROM projects 
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        projects = []
        for row in rows:
            projects.append({
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'brief': row[3],
                'ai_data': json.loads(row[4])
            })
        
        return projects
    
    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """
        Get a specific project by its ID
        
        Args:
            project_id: UUID of the project
            
        Returns:
            Project dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, created_at, brief, ai_data 
            FROM projects 
            WHERE id = ?
        ''', (project_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'brief': row[3],
                'ai_data': json.loads(row[4])
            }
        
        return None
    
    def save_project(self, name: str, brief: str, ai_data: Dict) -> Dict:
        """
        Save a new project to database
        
        Args:
            name: Project name
            brief: Project description
            ai_data: AI-generated data (questions, plan, etc.)
            
        Returns:
            The saved project dictionary
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create new project object
        new_project = {
            "id": str(uuid.uuid4()),
            "name": name,
            "created_at": datetime.now().isoformat(),
            "brief": brief,
            "ai_data": ai_data
        }
        
        # Insert into database
        cursor.execute('''
            INSERT INTO projects (id, name, created_at, brief, ai_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            new_project['id'],
            new_project['name'],
            new_project['created_at'],
            new_project['brief'],
            json.dumps(new_project['ai_data'])
        ))
        
        conn.commit()
        conn.close()
        
        return new_project
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project by ID
        
        Args:
            project_id: UUID of the project to delete
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def update_project(self, project_id: str, name: str = None, brief: str = None, ai_data: Dict = None) -> bool:
        """
        Update an existing project (BONUS: no disponible en JSON storage)
        
        Args:
            project_id: UUID of the project
            name: New project name (optional)
            brief: New project description (optional)
            ai_data: New AI data (optional)
            
        Returns:
            True if updated, False if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Build update query dynamically
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        
        if brief is not None:
            updates.append('brief = ?')
            params.append(brief)
        
        if ai_data is not None:
            updates.append('ai_data = ?')
            params.append(json.dumps(ai_data))
        
        if not updates:
            conn.close()
            return False
        
        params.append(project_id)
        query = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
        
        cursor.execute(query, params)
        updated = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return updated
    
    def search_projects(self, query: str) -> List[Dict]:
        """
        Search projects by name or brief (BONUS: no disponible en JSON storage)
        
        Args:
            query: Search query string
            
        Returns:
            List of matching project dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        search_pattern = f'%{query}%'
        cursor.execute('''
            SELECT id, name, created_at, brief, ai_data 
            FROM projects 
            WHERE name LIKE ? OR brief LIKE ?
            ORDER BY created_at DESC
        ''', (search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        conn.close()
        
        projects = []
        for row in rows:
            projects.append({
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'brief': row[3],
                'ai_data': json.loads(row[4])
            })
        
        return projects
    
    def get_project_count(self) -> int:
        """
        Get total number of projects (BONUS)
        
        Returns:
            Number of projects in database
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM projects')
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def save_feature_suggestions(self, project_id: str, project_name: str, audit_text: str, suggestions: List[str]) -> Dict:
        """
        Save feature suggestions for a project
        
        Args:
            project_id: UUID of the project
            project_name: Name of the project
            audit_text: User's project audit/status text
            suggestions: List of AI-generated feature suggestions
            
        Returns:
            The saved feature suggestion dictionary
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create new feature suggestion object
        new_suggestion = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "project_name": project_name,
            "audit_text": audit_text,
            "suggestions": suggestions,
            "created_at": datetime.now().isoformat()
        }
        
        # Insert into database
        cursor.execute('''
            INSERT INTO feature_suggestions (id, project_id, project_name, audit_text, suggestions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            new_suggestion['id'],
            new_suggestion['project_id'],
            new_suggestion['project_name'],
            new_suggestion['audit_text'],
            json.dumps(new_suggestion['suggestions']),
            new_suggestion['created_at']
        ))
        
        conn.commit()
        conn.close()
        
        return new_suggestion
    
    def get_feature_suggestions_by_project(self, project_id: str) -> List[Dict]:
        """
        Get all feature suggestions for a specific project
        
        Args:
            project_id: UUID of the project
            
        Returns:
            List of feature suggestion dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_id, project_name, audit_text, suggestions, created_at
            FROM feature_suggestions
            WHERE project_id = ?
            ORDER BY created_at DESC
        ''', (project_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        suggestions_list = []
        for row in rows:
            suggestions_list.append({
                'id': row[0],
                'project_id': row[1],
                'project_name': row[2],
                'audit_text': row[3],
                'suggestions': json.loads(row[4]),
                'created_at': row[5]
            })
        
        return suggestions_list
    
    def get_latest_feature_suggestion(self, project_id: str) -> Optional[Dict]:
        """
        Get the most recent feature suggestion for a project
        
        Args:
            project_id: UUID of the project
            
        Returns:
            Feature suggestion dictionary or None if not found
        """
        suggestions = self.get_feature_suggestions_by_project(project_id)
        return suggestions[0] if suggestions else None
    
    def save_section_state(self, project_id: str, section_id: str, is_expanded: bool) -> bool:
        """
        Save the state of a collapsible section for a project
        
        Args:
            project_id: ID of the project
            section_id: ID of the section
            is_expanded: Whether the section is expanded
            
        Returns:
            True if successful, False otherwise
        """
        print(f"[DEBUG] save_section_state called with - project_id: {project_id}, section_id: {section_id}, is_expanded: {is_expanded}")
        
        if not project_id or not section_id:
            print("[ERROR] Missing project_id or section_id")
            return False
            
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='section_states'")
            if not cursor.fetchone():
                print("[ERROR] section_states table does not exist")
                return False
                
            # Log current state before update
            cursor.execute('''
                SELECT is_expanded FROM section_states 
                WHERE project_id = ? AND section_id = ?
            ''', (project_id, section_id))
            
            existing = cursor.fetchone()
            if existing:
                print(f"[DEBUG] Current state in DB - is_expanded: {bool(existing[0])}")
            else:
                print("[DEBUG] No existing state found in DB")
            
            # Insert or update the state
            updated_at = datetime.utcnow().isoformat()
            params = (
                str(uuid.uuid4()),
                project_id,
                section_id,
                1 if is_expanded else 0,
                updated_at
            )
            
            print(f"[DEBUG] Executing query with params: {params}")
            
            cursor.execute('''
                INSERT INTO section_states (id, project_id, section_id, is_expanded, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, section_id) 
                DO UPDATE SET 
                    is_expanded = excluded.is_expanded, 
                    updated_at = excluded.updated_at
            ''', params)
            
            conn.commit()
            print("[DEBUG] Section state saved successfully")
            return True
            
        except sqlite3.Error as e:
            print(f"[ERROR] SQLite error in save_section_state: {e}")
            if conn:
                conn.rollback()
            return False
            
        except Exception as e:
            print(f"[ERROR] Unexpected error in save_section_state: {e}")
            if conn:
                conn.rollback()
            return False
            
        finally:
            if conn:
                conn.close()
    
    def get_section_states(self, project_id: str) -> Dict[str, bool]:
        """
        Get all section states for a project
        
        Args:
            project_id: ID of the project
            
        Returns:
            Dictionary mapping section IDs to their expanded state
        """
        print(f"[DEBUG] get_section_states called for project_id: {project_id}")
        
        if not project_id:
            print("[ERROR] Missing project_id in get_section_states")
            return {}
            
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='section_states'")
            if not cursor.fetchone():
                print("[WARNING] section_states table does not exist")
                return {}
            
            # Get all section states for the project
            cursor.execute('''
                SELECT section_id, is_expanded 
                FROM section_states 
                WHERE project_id = ?
            ''', (project_id,))
            
            result = {row[0]: bool(row[1]) for row in cursor.fetchall()}
            print(f"[DEBUG] Retrieved {len(result)} section states from DB")
            
            return result
            
        except sqlite3.Error as e:
            print(f"[ERROR] SQLite error in get_section_states: {e}")
            return {}
            
        except Exception as e:
            print(f"[ERROR] Unexpected error in get_section_states: {e}")
            return {}
            
        finally:
            if conn:
                conn.close()
    
    def save_estimation(self, project_name: str, project_description: str, phases: List[Dict], total_hours: int) -> Dict:
        """
        Save a new project estimation
        
        Args:
            project_name: Name of the project
            project_description: Description of the project
            phases: List of phase dictionaries
            total_hours: Total estimated hours
            
        Returns:
            The saved estimation dictionary
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create new estimation object
        new_estimation = {
            "id": str(uuid.uuid4()),
            "project_name": project_name,
            "project_description": project_description,
            "phases": phases,
            "total_hours": total_hours,
            "created_at": datetime.now().isoformat()
        }
        
        # Insert into database
        cursor.execute('''
            INSERT INTO estimations (id, project_name, project_description, phases, total_hours, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            new_estimation['id'],
            new_estimation['project_name'],
            new_estimation['project_description'],
            json.dumps(new_estimation['phases']),
            new_estimation['total_hours'],
            new_estimation['created_at']
        ))
        
        conn.commit()
        conn.close()
        
        return new_estimation
    
    def load_all_estimations(self) -> List[Dict]:
        """
        Load all estimations from database
        
        Returns:
            List of estimation dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, project_description, phases, total_hours, created_at
            FROM estimations
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        estimations = []
        for row in rows:
            estimations.append({
                'id': row[0],
                'project_name': row[1],
                'project_description': row[2],
                'phases': json.loads(row[3]),
                'total_hours': row[4],
                'created_at': row[5]
            })
        
        return estimations
    
    def get_estimation_by_id(self, estimation_id: str) -> Optional[Dict]:
        """
        Get a specific estimation by its ID
        
        Args:
            estimation_id: UUID of the estimation
            
        Returns:
            Estimation dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, project_description, phases, total_hours, created_at
            FROM estimations
            WHERE id = ?
        ''', (estimation_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'project_name': row[1],
                'project_description': row[2],
                'phases': json.loads(row[3]),
                'total_hours': row[4],
                'created_at': row[5]
            }
        
        return None
    
    def delete_estimation(self, estimation_id: str) -> bool:
        """
        Delete an estimation by ID
        
        Args:
            estimation_id: ID of the estimation to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM estimations WHERE id = ?", (estimation_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error deleting estimation: {e}")
            return False
        finally:
            conn.close()
            
    def save_section_state(self, project_id: str, section_id: str, is_expanded: bool) -> bool:
        """
        Save the state of a collapsible section for a project
        
        Args:
            project_id: ID of the project
            section_id: ID of the section
            is_expanded: Whether the section is expanded
            
        Returns:
            bool: True if save was successful
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO section_states (id, project_id, section_id, is_expanded, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, section_id) 
                DO UPDATE SET is_expanded = excluded.is_expanded, updated_at = excluded.updated_at
            ''', (str(uuid.uuid4()), project_id, section_id, is_expanded, datetime.now().isoformat()))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error saving section state: {e}")
            return False
        finally:
            conn.close()
    
    def get_section_states(self, project_id: str) -> Dict[str, bool]:
        """
        Get all section states for a project
        
        Args:
            project_id: ID of the project
            
        Returns:
            Dict[str, bool]: Dictionary mapping section IDs to their expanded state
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT section_id, is_expanded FROM section_states WHERE project_id = ?", 
                (project_id,)
            )
            
            return {row[0]: bool(row[1]) for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"Error loading section states: {e}")
            return {}
        finally:
            conn.close()
