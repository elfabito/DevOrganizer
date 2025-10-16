"""
Storage module for Dev Project Organizer
Handles saving and loading projects from JSON file
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import uuid


class ProjectStorage:
    """Manages project data persistence using JSON file storage"""
    
    def __init__(self, storage_file: str = "projects.json"):
        """
        Initialize storage with a JSON file path
        
        Args:
            storage_file: Path to the JSON file for storing projects
        """
        self.storage_file = storage_file
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Create storage file if it doesn't exist"""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w') as f:
                json.dump([], f)
    
    def load_all_projects(self) -> List[Dict]:
        """
        Load all projects from storage
        
        Returns:
            List of project dictionaries
        """
        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """
        Get a specific project by its ID
        
        Args:
            project_id: UUID of the project
            
        Returns:
            Project dictionary or None if not found
        """
        projects = self.load_all_projects()
        for project in projects:
            if project.get('id') == project_id:
                return project
        return None
    
    def save_project(self, name: str, brief: str, ai_data: Dict) -> Dict:
        """
        Save a new project to storage
        
        Args:
            name: Project name
            brief: Project description
            ai_data: AI-generated data (questions, plan, etc.)
            
        Returns:
            The saved project dictionary
        """
        projects = self.load_all_projects()
        
        # Create new project object
        new_project = {
            "id": str(uuid.uuid4()),
            "name": name,
            "created_at": datetime.now().isoformat(),
            "brief": brief,
            "ai_data": ai_data
        }
        
        # Add to projects list
        projects.append(new_project)
        
        # Save to file
        with open(self.storage_file, 'w') as f:
            json.dump(projects, f, indent=2)
        
        return new_project
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project by ID
        
        Args:
            project_id: UUID of the project to delete
            
        Returns:
            True if deleted, False if not found
        """
        projects = self.load_all_projects()
        original_count = len(projects)
        
        # Filter out the project to delete
        projects = [p for p in projects if p.get('id') != project_id]
        
        if len(projects) < original_count:
            with open(self.storage_file, 'w') as f:
                json.dump(projects, f, indent=2)
            return True
        
        return False
