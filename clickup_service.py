"""
ClickUp API Integration Service
Handles all interactions with the ClickUp API for workspace, project, and task management
"""

import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ClickUp API Configuration
CLICKUP_API_BASE = "https://api.clickup.com/api/v2"
CLICKUP_API_TOKEN = os.getenv('CLICKUP_API_TOKEN', '')


class ClickUpService:
    """Service class for ClickUp API operations"""
    
    def __init__(self, api_token=None):
        """
        Initialize ClickUp service
        
        Args:
            api_token: Optional API token. If not provided, uses environment variable
        """
        self.api_token = api_token or CLICKUP_API_TOKEN
        self.headers = {
            'Authorization': self.api_token,
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, method, endpoint, data=None):
        """
        Make a request to the ClickUp API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: Optional request body data
            
        Returns:
            Response JSON or error dictionary
        """
        url = f"{CLICKUP_API_BASE}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            else:
                return {'error': f'Unsupported HTTP method: {method}'}
            
            # Check for HTTP errors
            if response.status_code == 401:
                return {'error': 'Invalid ClickUp API token. Please check your configuration.'}
            elif response.status_code == 404:
                return {'error': 'Resource not found in ClickUp.'}
            elif response.status_code >= 400:
                return {'error': f'ClickUp API error: {response.status_code} - {response.text}'}
            
            return response.json()
            
        except requests.exceptions.Timeout:
            return {'error': 'Request to ClickUp API timed out. Please try again.'}
        except requests.exceptions.ConnectionError:
            return {'error': 'Could not connect to ClickUp API. Please check your internet connection.'}
        except requests.exceptions.RequestException as e:
            return {'error': f'Request error: {str(e)}'}
        except Exception as e:
            return {'error': f'Unexpected error: {str(e)}'}
    
    def get_workspaces(self):
        """
        Get all workspaces (teams) for the authenticated user
        
        Returns:
            List of workspaces with id and name, or error dictionary
        """
        result = self._make_request('GET', 'team')
        
        if 'error' in result:
            return result
        
        # Extract teams from response
        teams = result.get('teams', [])
        
        # Format workspaces for frontend
        workspaces = [
            {
                'id': team['id'],
                'name': team['name']
            }
            for team in teams
        ]
        
        return {'workspaces': workspaces}
    
    def get_spaces(self, team_id):
        """
        Get all spaces (projects) within a workspace
        
        Args:
            team_id: The workspace/team ID
            
        Returns:
            List of spaces with id and name, or error dictionary
        """
        result = self._make_request('GET', f'team/{team_id}/space')
        
        if 'error' in result:
            return result
        
        # Extract spaces from response
        spaces = result.get('spaces', [])
        
        # Format spaces for frontend
        formatted_spaces = [
            {
                'id': space['id'],
                'name': space['name'],
                'private': space.get('private', False)
            }
            for space in spaces
        ]
        
        return {'spaces': formatted_spaces}
    
    def get_shared_lists(self, team_id):
        """
        Get lists shared with the user in a workspace
        This gets all spaces and their lists, filtering for shared/private ones
        
        Args:
            team_id: The workspace/team ID
            
        Returns:
            List of shared lists, or error dictionary
        """
        # First, get all spaces
        spaces_result = self._make_request('GET', f'team/{team_id}/space')
        
        if 'error' in spaces_result:
            return spaces_result
        
        spaces = spaces_result.get('spaces', [])
        all_lists = []
        
        # For each space, get its lists (only private/shared spaces)
        for space in spaces:
            space_id = space['id']
            space_name = space['name']
            is_private = space.get('private', False)
            
            # Skip if it's not a private/shared space
            # Private spaces in ClickUp are actually shared spaces
            if not is_private:
                continue
            
            # Get folderless lists
            lists_result = self._make_request('GET', f'space/{space_id}/list')
            
            if 'error' not in lists_result:
                lists = lists_result.get('lists', [])
                for lst in lists:
                    all_lists.append({
                        'id': lst['id'],
                        'name': lst['name'],
                        'space_name': space_name
                    })
            
            # Get folders and their lists
            folders_result = self._make_request('GET', f'space/{space_id}/folder')
            
            if 'error' not in folders_result:
                folders = folders_result.get('folders', [])
                for folder in folders:
                    folder_id = folder['id']
                    folder_lists_result = self._make_request('GET', f'folder/{folder_id}/list')
                    
                    if 'error' not in folder_lists_result:
                        folder_lists = folder_lists_result.get('lists', [])
                        for lst in folder_lists:
                            all_lists.append({
                                'id': lst['id'],
                                'name': lst['name'],
                                'space_name': f"{space_name} / {folder['name']}"
                            })
        
        return {'lists': all_lists}
    
    def get_folders(self, space_id):
        """
        Get all folders within a space
        
        Args:
            space_id: The space ID
            
        Returns:
            List of folders with id and name, or error dictionary
        """
        result = self._make_request('GET', f'space/{space_id}/folder')
        
        if 'error' in result:
            return result
        
        # Extract folders from response
        folders = result.get('folders', [])
        
        # Format folders for frontend
        formatted_folders = [
            {
                'id': folder['id'],
                'name': folder['name']
            }
            for folder in folders
        ]
        
        return {'folders': formatted_folders}
    
    def get_lists(self, space_id, folder_id=None):
        """
        Get all lists within a space or folder
        
        Args:
            space_id: The space ID
            folder_id: Optional folder ID
            
        Returns:
            List of lists with id and name, or error dictionary
        """
        if folder_id:
            # Get lists from folder
            result = self._make_request('GET', f'folder/{folder_id}/list')
        else:
            # Get lists directly from space (folderless lists)
            result = self._make_request('GET', f'space/{space_id}/list')
        
        if 'error' in result:
            return result
        
        # Extract lists from response
        lists = result.get('lists', [])
        
        # Format lists for frontend
        formatted_lists = [
            {
                'id': lst['id'],
                'name': lst['name']
            }
            for lst in lists
        ]
        
        return {'lists': formatted_lists}
    
    def create_list(self, space_id, list_name, folder_id=None):
        """
        Create a new list in a ClickUp space or folder
        
        Args:
            space_id: The space ID where the list will be created
            list_name: Name for the new list
            folder_id: Optional folder ID if creating in a folder
            
        Returns:
            Created list data or error dictionary
        """
        # Prepare list payload
        payload = {
            'name': list_name,
            'content': f'Tasks for {list_name} project',
            'due_date_enabled': True,
            'priority_enabled': True,
            'assignee_enabled': True,
            'tag_enabled': True,
            'status_enabled': True,
            'time_tracking_enabled': True
        }
        
        # Determine endpoint based on whether it's in a folder or space
        if folder_id:
            endpoint = f'folder/{folder_id}/list'
        else:
            endpoint = f'space/{space_id}/list'
        
        result = self._make_request('POST', endpoint, payload)
        
        if 'error' in result:
            return result
        
        return {
            'success': True,
            'id': result.get('id'),
            'name': result.get('name'),
            'url': result.get('url')
        }
    
    def create_task(self, list_id, task_data):
        """
        Create a single task in a ClickUp list
        
        Args:
            list_id: The list ID where the task will be created
            task_data: Dictionary with task information (name, description, priority, etc.)
            
        Returns:
            Created task data or error dictionary
        """
        # Prepare task payload
        payload = {
            'name': task_data.get('name', 'Untitled Task'),
            'description': task_data.get('description', ''),
        }
        
        # Add priority if specified (1=urgent, 2=high, 3=normal, 4=low)
        priority_map = {
            'high': 2,
            'medium': 3,
            'low': 4
        }
        
        if 'priority' in task_data:
            priority = task_data['priority'].lower()
            if priority in priority_map:
                payload['priority'] = priority_map[priority]
        
        # Add status if specified
        if 'status' in task_data:
            payload['status'] = task_data['status']
        
        # Add tags if specified
        if 'tags' in task_data and task_data['tags']:
            payload['tags'] = task_data['tags']
        
        result = self._make_request('POST', f'list/{list_id}/task', payload)
        
        if 'error' in result:
            return result
        
        return {
            'success': True,
            'task_id': result.get('id'),
            'task_name': result.get('name'),
            'url': result.get('url')
        }
    
    def create_tasks_batch(self, list_id, tasks):
        """
        Create multiple tasks in a ClickUp list
        
        Args:
            list_id: The list ID where tasks will be created
            tasks: List of task dictionaries
            
        Returns:
            Summary of created tasks or error dictionary
        """
        created_tasks = []
        failed_tasks = []
        
        for task in tasks:
            result = self.create_task(list_id, task)
            
            if 'error' in result:
                failed_tasks.append({
                    'task_name': task.get('name', 'Unknown'),
                    'error': result['error']
                })
            else:
                created_tasks.append(result)
        
        return {
            'success': len(failed_tasks) == 0,
            'created_count': len(created_tasks),
            'failed_count': len(failed_tasks),
            'created_tasks': created_tasks,
            'failed_tasks': failed_tasks
        }
    
    def create_tasks_from_phases(self, list_id, phases):
        """
        Create tasks from phase structure (as generated by AI)
        Creates ONE task per phase with subtasks in the description
        
        Args:
            list_id: The list ID where tasks will be created
            phases: List of phase dictionaries with tasks
            
        Returns:
            Summary of created tasks
        """
        phase_tasks = []
        
        # Create one task per phase
        for phase in phases:
            phase_name = phase.get('name', 'Unknown Phase')
            tasks = phase.get('tasks', [])
            
            # Build description with all subtasks
            description_parts = []
            
            # Add phase overview if available
            if phase.get('description'):
                description_parts.append(phase['description'])
                description_parts.append('\n\n---\n\n')
            
            # Add subtasks section
            description_parts.append('## 📋 Subtasks:\n\n')
            
            for idx, task in enumerate(tasks, 1):
                # AI generates tasks with 'task' key, not 'name'
                task_name = task.get('task') or task.get('name', 'Untitled Subtask')
                task_desc = task.get('description', '')
                task_priority = task.get('priority', 'medium')
                
                description_parts.append(f'### {idx}. {task_name}\n')
                if task_desc:
                    description_parts.append(f'{task_desc}\n')
                description_parts.append(f'**Priority:** {task_priority.capitalize()}\n\n')
            
            # Get highest priority from subtasks for the main task
            priorities = [task.get('priority', 'medium') for task in tasks]
            priority_order = {'high': 1, 'medium': 2, 'low': 3}
            main_priority = min(priorities, key=lambda p: priority_order.get(p.lower(), 2))
            
            # Create task data for this phase
            task_data = {
                'name': phase_name,
                'description': ''.join(description_parts),
                'priority': main_priority,
                'tags': [phase_name.lower().replace(' ', '-')]
            }
            phase_tasks.append(task_data)
        
        # Create all phase tasks
        return self.create_tasks_batch(list_id, phase_tasks)


# Singleton instance
_clickup_service = None


def get_clickup_service(api_token=None):
    """
    Get or create ClickUp service instance
    
    Args:
        api_token: Optional API token to use
        
    Returns:
        ClickUpService instance
    """
    global _clickup_service
    
    if api_token:
        # Create new instance with provided token
        return ClickUpService(api_token)
    
    if _clickup_service is None:
        _clickup_service = ClickUpService()
    
    return _clickup_service
