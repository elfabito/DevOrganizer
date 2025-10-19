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
    
    def save_project(self, project_data: Dict) -> str:
        """
        Save a project to storage
        
        Args:
            project_data: Dictionary containing project data
                Required keys: name, brief, ai_data
                Optional keys: id (auto-generated if not provided), created_at (defaults to now)
                
        Returns:
            The ID of the saved project
            
        Raises:
            ValueError: If required fields are missing or saving fails
        """
        # Validate required fields
        if not all(key in project_data for key in ['name', 'brief', 'ai_data']):
            raise ValueError("Missing required project fields")
            
        # Generate ID and timestamps if not provided
        project_id = project_data.get('id') or str(uuid.uuid4())
        created_at = project_data.get('created_at') or datetime.utcnow().isoformat()
        
        # Create project dictionary
        project = {
            'id': project_id,
            'name': project_data['name'],
            'brief': project_data['brief'],
            'ai_data': project_data['ai_data'],
            'created_at': created_at
        }
        
        # Load existing projects
        projects = self.load_all_projects()
        
        # Update existing project or add new one
        existing_index = next((i for i, p in enumerate(projects) if p['id'] == project_id), None)
        if existing_index is not None:
            projects[existing_index] = project
        else:
            projects.append(project)
            
        # Save back to file
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(projects, f, indent=2)
            return project_id
            
        except Exception as e:
            raise ValueError(f"Failed to save project: {str(e)}")
            
    def get_estimation(self, estimation_id: str) -> Optional[Dict]:
        """
        Get an estimation by its ID
        
        Args:
            estimation_id: The ID of the estimation to retrieve
            
        Returns:
            The estimation dictionary if found, None otherwise
        """
        try:
            with open('estimations.json', 'r') as f:
                estimations = json.load(f)
            return next((e for e in estimations if e.get('id') == estimation_id), None)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
            
    def update_estimation(self, estimation_id: str, updated_data: Dict) -> bool:
        """
        Update an existing estimation
        
        Args:
            estimation_id: The ID of the estimation to update
            updated_data: Dictionary containing the updated estimation data
            
        Returns:
            bool: True if update was successful, False otherwise
            
        Raises:
            ValueError: If the estimation doesn't exist or update fails
        """
        try:
            # Load existing estimations
            try:
                with open('estimations.json', 'r') as f:
                    estimations = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                raise ValueError("No estimations found")
                
            # Find the estimation to update
            estimation_index = next((i for i, e in enumerate(estimations) 
                                  if e.get('id') == estimation_id), None)
                                  
            if estimation_index is None:
                raise ValueError(f"Estimation with ID {estimation_id} not found")
                
            # Update the estimation
            estimations[estimation_index].update(updated_data)
            
            # Save back to file
            with open('estimations.json', 'w') as f:
                json.dump(estimations, f, indent=2)
                
            return True
            
        except Exception as e:
            raise ValueError(f"Failed to update estimation: {str(e)}")
            
    def save_estimation(self, estimation_data: Dict) -> Dict:
        """
        Save an estimation to the JSON storage
        
        Args:
            estimation_data: Dictionary containing estimation data
                Required keys: project_name, project_description, phases, total_hours, user_id
                Optional keys: id (auto-generated if not provided), created_at (defaults to now)
                
        Returns:
            Dictionary containing the saved estimation data
            
        Raises:
            ValueError: If required fields are missing or saving fails
        """
        try:
            # Validate required fields
            required_fields = ['project_name', 'project_description', 'phases', 'total_hours', 'user_id']
            if not all(field in estimation_data for field in required_fields):
                missing = [f for f in required_fields if f not in estimation_data]
                raise ValueError(f"Missing required fields: {', '.join(missing)}")
                
            # Generate ID and timestamps if not provided
            estimation_id = estimation_data.get('id') or str(uuid.uuid4())
            created_at = estimation_data.get('created_at') or datetime.utcnow().isoformat()
            
            # Prepare estimation data
            estimation = {
                'id': estimation_id,
                'project_name': estimation_data['project_name'],
                'project_description': estimation_data['project_description'],
                'phases': estimation_data['phases'],
                'total_hours': int(estimation_data['total_hours']),
                'created_at': created_at,
                'user_id': estimation_data['user_id'],
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Load existing estimations
            try:
                with open('estimations.json', 'r') as f:
                    estimations = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                estimations = []
                
            # Update existing or add new estimation
            existing_index = next((i for i, e in enumerate(estimations) 
                                 if e.get('id') == estimation_id), None)
            if existing_index is not None:
                estimations[existing_index] = estimation
            else:
                estimations.append(estimation)
                
            # Save back to file
            with open('estimations.json', 'w') as f:
                json.dump(estimations, f, indent=2)
                
            return estimation
            
        except Exception as e:
            raise ValueError(f"Failed to save estimation: {str(e)}")
            
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
