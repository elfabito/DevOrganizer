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
