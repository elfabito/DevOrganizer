"""
Weekly Summary Storage Extension for Dev Project Organizer
Handles weekly summary CRUD operations separately from main storage
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import uuid


class WeeklySummaryStorage:
    """Manages weekly summary data persistence"""
    
    def __init__(self, db_file: str = "projects.db"):
        """
        Initialize storage with a SQLite database
        
        Args:
            db_file: Path to the SQLite database file
        """
        self.db_file = db_file
        self._init_database()
    
    def _init_database(self):
        """Create weekly summaries table if it doesn't exist"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
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
        
        # Create indexes for faster searches
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
    
    def create_weekly_summary(self, project_name: str) -> Dict:
        """
        Create a new weekly summary entry for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            The created weekly summary dictionary
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create new weekly summary object with empty notes
        new_summary = {
            "id": str(uuid.uuid4()),
            "project_name": project_name,
            "created_at": datetime.now().isoformat(),
            "week_notes": {
                "Monday": "",
                "Tuesday": "",
                "Wednesday": "",
                "Thursday": "",
                "Friday": ""
            },
            "ai_summary": None
        }
        
        # Insert into database
        cursor.execute('''
            INSERT INTO weekly_summaries (id, project_name, created_at, week_notes, ai_summary)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            new_summary['id'],
            new_summary['project_name'],
            new_summary['created_at'],
            json.dumps(new_summary['week_notes']),
            new_summary['ai_summary']
        ))
        
        conn.commit()
        conn.close()
        
        return new_summary
    
    def get_weekly_summary_by_id(self, summary_id: str) -> Optional[Dict]:
        """
        Get a specific weekly summary by its ID
        
        Args:
            summary_id: UUID of the weekly summary
            
        Returns:
            Weekly summary dictionary or None if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, created_at, week_notes, ai_summary 
            FROM weekly_summaries 
            WHERE id = ?
        ''', (summary_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'project_name': row[1],
                'created_at': row[2],
                'week_notes': json.loads(row[3]),
                'ai_summary': row[4]
            }
        
        return None
    
    def get_all_weekly_summaries(self) -> List[Dict]:
        """
        Get all weekly summaries from database
        
        Returns:
            List of weekly summary dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, created_at, week_notes, ai_summary 
            FROM weekly_summaries 
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        summaries = []
        for row in rows:
            summaries.append({
                'id': row[0],
                'project_name': row[1],
                'created_at': row[2],
                'week_notes': json.loads(row[3]),
                'ai_summary': row[4]
            })
        
        return summaries
    
    def get_weekly_summaries_by_project(self, project_name: str) -> List[Dict]:
        """
        Get all weekly summaries for a specific project
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of weekly summary dictionaries for the project
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_name, created_at, week_notes, ai_summary 
            FROM weekly_summaries 
            WHERE project_name = ?
            ORDER BY created_at DESC
        ''', (project_name,))
        
        rows = cursor.fetchall()
        conn.close()
        
        summaries = []
        for row in rows:
            summaries.append({
                'id': row[0],
                'project_name': row[1],
                'created_at': row[2],
                'week_notes': json.loads(row[3]),
                'ai_summary': row[4]
            })
        
        return summaries
    
    def update_weekly_summary(self, summary_id: str, week_notes: Dict = None, ai_summary: str = None) -> bool:
        """
        Update a weekly summary's notes or AI-generated summary
        
        Args:
            summary_id: UUID of the weekly summary
            week_notes: Dictionary of daily notes (optional)
            ai_summary: AI-generated summary text (optional)
            
        Returns:
            True if updated, False if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Build update query dynamically
        updates = []
        params = []
        
        if week_notes is not None:
            updates.append('week_notes = ?')
            params.append(json.dumps(week_notes))
        
        if ai_summary is not None:
            updates.append('ai_summary = ?')
            params.append(ai_summary)
        
        if not updates:
            conn.close()
            return False
        
        params.append(summary_id)
        query = f"UPDATE weekly_summaries SET {', '.join(updates)} WHERE id = ?"
        
        cursor.execute(query, params)
        updated = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return updated
    
    def delete_weekly_summary(self, summary_id: str) -> bool:
        """
        Delete a weekly summary by ID
        
        Args:
            summary_id: UUID of the weekly summary to delete
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM weekly_summaries WHERE id = ?', (summary_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
