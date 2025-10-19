"""
Database migration script for DevOrganizer
Run this script to update the database schema
"""
import sqlite3
import os
import sys

def migrate_database(db_path='projects.db'):
    """Apply database migrations
    
    Args:
        db_path (str): Path to the SQLite database file
    """
    db_file = db_path
    backup_file = f"{db_path}.backup"
    
    # Create backup of existing database
    if os.path.exists(db_file):
        import shutil
        import time
        
        # Create a timestamped backup filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database_backups')
        backup_filename = f"{os.path.basename(db_file)}.{timestamp}.backup"
        backup_file = os.path.join(backup_dir, backup_filename)
        
        # Ensure backup directory exists
        os.makedirs(backup_dir, exist_ok=True)
        
        print(f"Creating database backup at: {backup_file}")
        
        try:
            # Try to copy the file with retries for Windows file locking
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.copy2(db_file, backup_file)
                    print("Backup created successfully.")
                    break
                except (PermissionError, OSError) as e:
                    if attempt == max_retries - 1:  # Last attempt
                        print(f"Warning: Failed to create backup after {max_retries} attempts: {e}")
                        # Try one last time with a different location
                        temp_backup = os.path.join(os.environ.get('TEMP', '.'), backup_filename)
                        try:
                            shutil.copy2(db_file, temp_backup)
                            print(f"Backup created at temporary location: {temp_backup}")
                            break
                        except Exception as temp_err:
                            print(f"Critical: Could not create backup at any location: {temp_err}")
                            raise
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(1)  # Wait a bit before retrying
        except Exception as e:
            print(f"Error creating backup: {e}")
            print("WARNING: Proceeding without backup. This is not recommended for production.")
            if input("Continue without backup? (y/n): ").lower() != 'y':
                sys.exit(1)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_file)) or '.', exist_ok=True)
    
    # Connect to the database (this will create a new one if it doesn't exist)
    conn = sqlite3.connect(db_file)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()
    
    try:
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
        
        # Create estimations table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estimations (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                project_description TEXT NOT NULL,
                phases TEXT NOT NULL,
                total_hours INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Create index on created_at for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_created_at 
            ON estimations(created_at)
        ''')
        
        # Create index on user_id for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estimations_user_id 
            ON estimations(user_id)
        ''')
        
        # Check if updated_at column exists, if not add it
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'updated_at' not in columns:
            print("Adding updated_at column to users table...")
            cursor.execute('''
                ALTER TABLE users 
                ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            ''')
        
        # Create new projects table with user_id
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
        
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON projects(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_projects_user_id 
            ON projects(user_id)
        ''')
        
        # Create section_states table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_states (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    is_expanded BOOLEAN DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, section_id, user_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        
        # Create indexes for faster lookups
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
        
        # Create ClickUp integration tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clickup_integrations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                api_token TEXT NOT NULL,
                team_id TEXT,
                default_workspace_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clickup_mappings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                clickup_space_id TEXT,
                clickup_folder_id TEXT,
                clickup_list_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Create technical questions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS technical_questions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                is_answered BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Add indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_clickup_user 
            ON clickup_integrations(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_clickup_mapping_project 
            ON clickup_mappings(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_questions_project 
            ON technical_questions(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_questions_answered 
            ON technical_questions(is_answered)
        ''')
        
        # Create weekly_summaries table
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
        
        # Create feature_suggestions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_suggestions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 3,  -- 1: High, 2: Medium, 3: Low
                status TEXT DEFAULT 'pending',  -- pending, approved, rejected, completed
                ai_generated BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        
        # Add indexes for better performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_project 
            ON weekly_summaries(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week 
            ON weekly_summaries(week_start_date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_feature_suggestions_project 
            ON feature_suggestions(project_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_feature_suggestions_priority 
            ON feature_suggestions(priority)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_feature_suggestions_status 
            ON feature_suggestions(status)
        ''')
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        print("Restoring from backup...")
        conn.rollback()
        if os.path.exists(backup_file):
            if os.path.exists(db_file):
                os.remove(db_file)
            os.rename(backup_file, db_file)
        print("Database restored from backup.")
        return False
    finally:
        conn.close()
    
    return True

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'projects.db'
    print(f"Starting database migration for {db_path}...")
    try:
        if migrate_database(db_path):
            print("Migration completed successfully!")
        else:
            print("Migration failed.")
            exit(1)
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        exit(1)
