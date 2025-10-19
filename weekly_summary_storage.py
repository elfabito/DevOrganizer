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
                project_id TEXT NOT NULL,
                week_start_date TEXT NOT NULL,
                week_notes TEXT NOT NULL,
                ai_summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for faster searches
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_created 
            ON weekly_summaries(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week 
            ON weekly_summaries(week_start_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_project 
            ON weekly_summaries(project_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def create_weekly_summary(self, project_id: str) -> Dict:
        """
        Create a new weekly summary entry for a project
        
        Args:
            project_id: ID of the project
            
        Returns:
            The created weekly summary dictionary
        """
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Get current timestamp
        now = datetime.now().isoformat()
        week_start = datetime.now().date().strftime('%Y-%m-%d')
        
        # Create new weekly summary object with empty notes
        new_summary = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "week_start_date": week_start,
            "created_at": now,
            "updated_at": now,
            "week_notes": {
                "Monday": "",
                "Tuesday": "",
                "Wednesday": "",
                "Thursday": "",
                "Friday": ""
            },
            "ai_summary": None,
        }
        
        # Insert into database
        cursor.execute('''
            INSERT INTO weekly_summaries 
            (id, project_id, week_start_date, created_at, updated_at, week_notes, ai_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_summary['id'],
            new_summary['project_id'],
            new_summary['week_start_date'],
            new_summary['created_at'],
            new_summary['updated_at'],
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
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_id, week_start_date, created_at, updated_at, week_notes, ai_summary 
            FROM weekly_summaries 
            WHERE id = ?
        ''', (summary_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            summary = dict(row)
            summary['week_notes'] = json.loads(summary['week_notes'])
            return summary
        return None
    
    def get_all_weekly_summaries(self) -> List[Dict]:
        """
        Get all weekly summaries from database
        
        Returns:
            List of weekly summary dictionaries
        """
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_id, week_start_date, created_at, updated_at, week_notes, ai_summary 
            FROM weekly_summaries 
            ORDER BY week_start_date DESC, created_at DESC
        ''')
        
        summaries = []
        for row in cursor.fetchall():
            summary = dict(row)
            summary['week_notes'] = json.loads(summary['week_notes'])
            summaries.append(summary)
            
        conn.close()
        return summaries
    
    def get_weekly_summaries_by_project(self, project_id: str) -> List[Dict]:
        """
        Get all weekly summaries for a specific project
        
        Args:
            project_id: ID of the project
            
        Returns:
            List of weekly summary dictionaries for the project
        """
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, project_id, week_start_date, created_at, updated_at, week_notes, ai_summary 
            FROM weekly_summaries 
            WHERE project_id = ? 
            ORDER BY week_start_date DESC
        ''', (project_id,))
        
        summaries = []
        for row in cursor.fetchall():
            summary = dict(row)
            summary['week_notes'] = json.loads(summary['week_notes'])
            summaries.append(summary)
            
        conn.close()
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
        if week_notes is None and ai_summary is None:
            return False
            
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        updates = ["updated_at = ?"]
        params = [datetime.now().isoformat()]
        
        if week_notes is not None:
            updates.append("week_notes = ?")
            params.append(json.dumps(week_notes))
            
        if ai_summary is not None:
            updates.append("ai_summary = ?")
            params.append(ai_summary)
            
        if len(updates) == 1:  # Only updated_at was added
            return False
            
        params.append(summary_id)
        
        query = f"""
            UPDATE weekly_summaries 
            SET {', '.join(updates)}
            WHERE id = ?
        """
        
        cursor.execute(query, tuple(params))
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
