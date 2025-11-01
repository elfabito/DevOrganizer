"""Storage layer for daily notes with SQLite backend."""
import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid


class DailyNotesStorage:
    """Handles all database operations for daily notes and note images."""

    def __init__(self, db_path: str = 'projects.db'):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database tables for daily notes and images."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create daily_notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_notes (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                note_date TEXT NOT NULL,
                note_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')

        # Create note_images table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_images (
                id TEXT PRIMARY KEY,
                note_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                uploaded_at TEXT NOT NULL,
                cloudinary_public_id TEXT,
                cloudinary_url TEXT,
                width INTEGER,
                height INTEGER,
                FOREIGN KEY (note_id) REFERENCES daily_notes(id) ON DELETE CASCADE
            )
        ''')

        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_notes_project
            ON daily_notes(project_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_notes_date
            ON daily_notes(note_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_daily_notes_created
            ON daily_notes(created_at DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_note_images_note
            ON note_images(note_id)
        ''')

        conn.commit()
        conn.close()

    def create_note(self, project_id: str, user_id: str, title: str,
                   content: str, note_date: str, note_time: str) -> Dict[str, Any]:
        """Create a new daily note."""
        note_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO daily_notes
            (id, project_id, user_id, title, content, note_date, note_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (note_id, project_id, user_id, title, content, note_date, note_time, now, now))

        conn.commit()
        conn.close()

        return {
            'id': note_id,
            'project_id': project_id,
            'user_id': user_id,
            'title': title,
            'content': content,
            'note_date': note_date,
            'note_time': note_time,
            'created_at': now,
            'updated_at': now
        }

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific note by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, project_id, user_id, title, content, note_date,
                   note_time, created_at, updated_at
            FROM daily_notes
            WHERE id = ?
        ''', (note_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        note = {
            'id': row[0],
            'project_id': row[1],
            'user_id': row[2],
            'title': row[3],
            'content': row[4],
            'note_date': row[5],
            'note_time': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        }

        # Get associated images
        note['images'] = self.get_note_images(note_id)

        return note

    def update_note(self, note_id: str, title: str = None, content: str = None,
                   note_date: str = None, note_time: str = None) -> bool:
        """Update an existing note."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build dynamic update query
        updates = []
        params = []

        if title is not None:
            updates.append('title = ?')
            params.append(title)

        if content is not None:
            updates.append('content = ?')
            params.append(content)

        if note_date is not None:
            updates.append('note_date = ?')
            params.append(note_date)

        if note_time is not None:
            updates.append('note_time = ?')
            params.append(note_time)

        if not updates:
            conn.close()
            return False

        # Always update updated_at
        updates.append('updated_at = ?')
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(note_id)

        query = f'UPDATE daily_notes SET {", ".join(updates)} WHERE id = ?'
        cursor.execute(query, params)

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return success

    def delete_note(self, note_id: str) -> bool:
        """Delete a note and all associated images."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get images to delete files
        images = self.get_note_images(note_id)

        # Delete note (cascade will delete image records)
        cursor.execute('DELETE FROM daily_notes WHERE id = ?', (note_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        # Delete physical image files
        if success:
            for img in images:
                try:
                    if os.path.exists(img['file_path']):
                        os.remove(img['file_path'])
                except Exception as e:
                    print(f"Error deleting image file {img['file_path']}: {e}")

        return success

    def get_notes_by_date(self, project_id: str, note_date: str) -> List[Dict[str, Any]]:
        """Get all notes for a specific project and date, sorted by time (newest first)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, project_id, user_id, title, content, note_date,
                   note_time, created_at, updated_at
            FROM daily_notes
            WHERE project_id = ? AND note_date = ?
            ORDER BY note_time DESC, created_at DESC
        ''', (project_id, note_date))

        rows = cursor.fetchall()
        conn.close()

        notes = []
        for row in rows:
            note = {
                'id': row[0],
                'project_id': row[1],
                'user_id': row[2],
                'title': row[3],
                'content': row[4],
                'note_date': row[5],
                'note_time': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
            note['images'] = self.get_note_images(note['id'])
            notes.append(note)

        return notes

    def get_notes_by_project(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent notes for a project."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, project_id, user_id, title, content, note_date,
                   note_time, created_at, updated_at
            FROM daily_notes
            WHERE project_id = ?
            ORDER BY note_date DESC, note_time DESC, created_at DESC
            LIMIT ?
        ''', (project_id, limit))

        rows = cursor.fetchall()
        conn.close()

        notes = []
        for row in rows:
            note = {
                'id': row[0],
                'project_id': row[1],
                'user_id': row[2],
                'title': row[3],
                'content': row[4],
                'note_date': row[5],
                'note_time': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
            note['images'] = self.get_note_images(note['id'])
            notes.append(note)

        return notes

    def get_notes_by_date_range(self, project_id: str, start_date: str,
                                end_date: str) -> List[Dict[str, Any]]:
        """Get all notes for a project within a date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, project_id, user_id, title, content, note_date,
                   note_time, created_at, updated_at
            FROM daily_notes
            WHERE project_id = ? AND note_date >= ? AND note_date <= ?
            ORDER BY note_date, note_time DESC
        ''', (project_id, start_date, end_date))

        rows = cursor.fetchall()
        conn.close()

        notes = []
        for row in rows:
            note = {
                'id': row[0],
                'project_id': row[1],
                'user_id': row[2],
                'title': row[3],
                'content': row[4],
                'note_date': row[5],
                'note_time': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
            note['images'] = self.get_note_images(note['id'])
            notes.append(note)

        return notes

    def get_note_dates_for_month(self, project_id: str, year: int, month: int) -> List[str]:
        """Get all dates that have notes for a specific month."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Format: YYYY-MM for comparison
        month_str = f"{year:04d}-{month:02d}"

        cursor.execute('''
            SELECT DISTINCT note_date
            FROM daily_notes
            WHERE project_id = ? AND note_date LIKE ?
            ORDER BY note_date
        ''', (project_id, f"{month_str}%"))

        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows]

    def add_image_to_note(self, note_id: str, filename: str, original_filename: str,
                         file_path: str, file_size: int, mime_type: str,
                         cloudinary_public_id: str = None, cloudinary_url: str = None,
                         width: int = None, height: int = None) -> Dict[str, Any]:
        """Add an image to a note (supports both local and Cloudinary storage)."""
        image_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO note_images
            (id, note_id, filename, original_filename, file_path, file_size, mime_type, 
             uploaded_at, cloudinary_public_id, cloudinary_url, width, height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (image_id, note_id, filename, original_filename, file_path, file_size, mime_type, 
              now, cloudinary_public_id, cloudinary_url, width, height))

        conn.commit()
        conn.close()

        return {
            'id': image_id,
            'note_id': note_id,
            'filename': filename,
            'original_filename': original_filename,
            'file_path': file_path,
            'file_size': file_size,
            'mime_type': mime_type,
            'uploaded_at': now,
            'cloudinary_public_id': cloudinary_public_id,
            'cloudinary_url': cloudinary_url,
            'width': width,
            'height': height
        }

    def get_note_images(self, note_id: str) -> List[Dict[str, Any]]:
        """Get all images for a note."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, note_id, filename, original_filename, file_path,
                   file_size, mime_type, uploaded_at, cloudinary_public_id, 
                   cloudinary_url, width, height
            FROM note_images
            WHERE note_id = ?
            ORDER BY uploaded_at
        ''', (note_id,))

        rows = cursor.fetchall()
        conn.close()

        images = []
        for row in rows:
            images.append({
                'id': row[0],
                'note_id': row[1],
                'filename': row[2],
                'original_filename': row[3],
                'file_path': row[4],
                'file_size': row[5],
                'mime_type': row[6],
                'uploaded_at': row[7],
                'cloudinary_public_id': row[8],
                'cloudinary_url': row[9],
                'width': row[10],
                'height': row[11]
            })

        return images

    def get_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific image by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, note_id, filename, original_filename, file_path,
                   file_size, mime_type, uploaded_at, cloudinary_public_id,
                   cloudinary_url, width, height
            FROM note_images
            WHERE id = ?
        ''', (image_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'note_id': row[1],
            'filename': row[2],
            'original_filename': row[3],
            'file_path': row[4],
            'file_size': row[5],
            'mime_type': row[6],
            'uploaded_at': row[7],
            'cloudinary_public_id': row[8],
            'cloudinary_url': row[9],
            'width': row[10],
            'height': row[11]
        }

    def delete_note_image(self, image_id: str, delete_from_cloudinary: bool = True) -> bool:
        """Delete an image from a note (and optionally from Cloudinary)."""
        # Get image info to delete file
        image = self.get_image(image_id)
        if not image:
            return False

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM note_images WHERE id = ?', (image_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()

        # Delete physical file or Cloudinary image
        if success:
            # If it's a Cloudinary image, return the public_id so it can be deleted
            # Otherwise, delete the local file
            if image.get('cloudinary_public_id') and delete_from_cloudinary:
                # Deletion will be handled by the caller using cloudinary_service
                pass
            else:
                # Delete local file if it exists
                try:
                    if image.get('file_path') and os.path.exists(image['file_path']):
                        os.remove(image['file_path'])
                except Exception as e:
                    print(f"Error deleting image file {image['file_path']}: {e}")

        return success

    def get_image_count_for_note(self, note_id: str) -> int:
        """Get the number of images attached to a note."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM note_images WHERE note_id = ?', (note_id,))
        count = cursor.fetchone()[0]

        conn.close()
        return count
