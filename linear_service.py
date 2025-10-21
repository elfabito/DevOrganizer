"""
Linear API Service for Dev Project Organizer
Handles Linear integration for task/issue creation
"""

import os
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Linear API configuration
LINEAR_API_URL = 'https://api.linear.app/graphql'


class LinearService:
    """Service class for Linear API integration"""

    def __init__(self, api_token: str):
        """
        Initialize Linear service with API token

        Args:
            api_token: Linear personal API token (starts with 'lin_api_')
        """
        self.api_token = api_token
        self.headers = {
            'Authorization': api_token,
            'Content-Type': 'application/json'
        }
        self.base_url = LINEAR_API_URL

    def _make_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        Make a GraphQL request to Linear API

        Args:
            query: GraphQL query or mutation string
            variables: Optional variables for the query

        Returns:
            Response data from Linear API

        Raises:
            Exception: If API request fails
        """
        try:
            payload = {'query': query}
            if variables:
                payload['variables'] = variables

            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            # Check for GraphQL errors
            if 'errors' in data:
                error_messages = [err.get('message', 'Unknown error') for err in data['errors']]
                raise Exception(f"Linear API errors: {', '.join(error_messages)}")

            return data.get('data', {})

        except requests.exceptions.RequestException as e:
            raise Exception(f"Linear API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Linear API error: {str(e)}")

    def get_viewer(self) -> Dict:
        """
        Get information about the authenticated user

        Returns:
            Dict with user info: {id, name, email}
        """
        query = """
        query {
            viewer {
                id
                name
                email
            }
        }
        """

        data = self._make_request(query)
        return data.get('viewer', {})

    def get_teams(self) -> List[Dict]:
        """
        Get all teams the user has access to

        Returns:
            List of teams: [{id, name}, ...]
        """
        query = """
        query {
            teams {
                nodes {
                    id
                    name
                    key
                }
            }
        }
        """

        data = self._make_request(query)
        teams = data.get('teams', {}).get('nodes', [])
        return teams

    def get_projects(self, team_id: str) -> List[Dict]:
        """
        Get all projects in a team

        Args:
            team_id: ID of the team

        Returns:
            List of projects: [{id, name}, ...]
        """
        query = """
        query($teamId: String!) {
            projects(filter: {team: {id: {eq: $teamId}}}) {
                nodes {
                    id
                    name
                }
            }
        }
        """

        variables = {'teamId': team_id}
        data = self._make_request(query, variables)
        projects = data.get('projects', {}).get('nodes', [])
        return projects

    def get_workflow_states(self, team_id: str) -> List[Dict]:
        """
        Get workflow states for a team

        Args:
            team_id: ID of the team

        Returns:
            List of workflow states: [{id, name, type}, ...]
        """
        query = """
        query($teamId: String!) {
            workflowStates(filter: {team: {id: {eq: $teamId}}}) {
                nodes {
                    id
                    name
                    type
                }
            }
        }
        """

        variables = {'teamId': team_id}
        data = self._make_request(query, variables)
        states = data.get('workflowStates', {}).get('nodes', [])
        return states

    def get_or_create_label(self, team_id: str, label_name: str) -> Optional[str]:
        """
        Get or create a label in a team

        Args:
            team_id: ID of the team
            label_name: Name of the label to get/create

        Returns:
            Label ID if successful, None otherwise
        """
        # First, try to get existing labels
        query_get = """
        query($teamId: String!) {
            issueLabels(filter: {team: {id: {eq: $teamId}}}) {
                nodes {
                    id
                    name
                }
            }
        }
        """

        try:
            data = self._make_request(query_get, {'teamId': team_id})
            labels = data.get('issueLabels', {}).get('nodes', [])

            # Check if label already exists
            for label in labels:
                if label.get('name') == label_name:
                    return label.get('id')

            # Create new label if it doesn't exist
            mutation_create = """
            mutation($teamId: String!, $name: String!) {
                issueLabelCreate(input: {teamId: $teamId, name: $name}) {
                    issueLabel {
                        id
                        name
                    }
                    success
                }
            }
            """

            variables = {'teamId': team_id, 'name': label_name}
            data = self._make_request(mutation_create, variables)

            result = data.get('issueLabelCreate', {})
            if result.get('success'):
                return result.get('issueLabel', {}).get('id')

            return None

        except Exception as e:
            print(f"Error getting/creating label: {str(e)}")
            return None

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: str,
        project_id: Optional[str] = None,
        priority: Optional[int] = None,
        label_ids: Optional[List[str]] = None,
        assignee_id: Optional[str] = None,
        state_id: Optional[str] = None
    ) -> Dict:
        """
        Create a single issue in Linear

        Args:
            team_id: ID of the team
            title: Issue title
            description: Issue description
            project_id: Optional project ID
            priority: Priority (0=None, 1=Urgent, 2=High, 3=Medium, 4=Low)
            label_ids: List of label IDs to apply
            assignee_id: ID of user to assign to
            state_id: ID of workflow state to set

        Returns:
            Dict with issue info: {success, issue: {id, identifier, url}}
        """
        mutation = """
        mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """

        # Build input object
        issue_input = {
            'teamId': team_id,
            'title': title,
            'description': description
        }

        if project_id:
            issue_input['projectId'] = project_id
        if priority is not None:
            issue_input['priority'] = priority
        if label_ids:
            issue_input['labelIds'] = label_ids
        if assignee_id:
            issue_input['assigneeId'] = assignee_id
        if state_id:
            issue_input['stateId'] = state_id

        variables = {'input': issue_input}

        try:
            data = self._make_request(mutation, variables)
            result = data.get('issueCreate', {})

            if result.get('success'):
                return {
                    'success': True,
                    'issue': result.get('issue', {})
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create issue'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def create_issues_from_phases(
        self,
        team_id: str,
        phases: List[Dict],
        project_id: Optional[str] = None
    ) -> Dict:
        """
        Create multiple issues from phase structure

        Args:
            team_id: ID of the team
            phases: List of phases with tasks
            project_id: Optional project ID

        Returns:
            Dict with creation summary: {
                success: bool,
                created_count: int,
                failed_count: int,
                created_issues: list,
                failed_issues: list
            }
        """
        created_issues = []
        failed_issues = []

        try:
            # Get authenticated user (for assignee)
            viewer = self.get_viewer()
            assignee_id = viewer.get('id')

            # Get backlog state for team
            workflow_states = self.get_workflow_states(team_id)
            backlog_state = None
            for state in workflow_states:
                if state.get('type') == 'backlog':
                    backlog_state = state.get('id')
                    break

            # Priority mapping: high→1, medium→2, low→3
            priority_map = {
                'high': 1,
                'medium': 2,
                'low': 3,
                'urgent': 1
            }

            # Process each phase
            for phase in phases:
                phase_name = phase.get('name', 'Unnamed Phase')
                tasks = phase.get('tasks', [])

                # Create/get label for this phase
                label_id = self.get_or_create_label(team_id, phase_name)
                label_ids = [label_id] if label_id else []

                # Create issue for each task in phase
                for task in tasks:
                    task_text = task.get('task', task.get('name', 'Untitled'))
                    task_priority_str = task.get('priority', 'medium').lower()
                    task_priority = priority_map.get(task_priority_str, 2)

                    # Build description
                    description = f"**Phase:** {phase_name}\n**Priority:** {task_priority_str}\n\n{task_text}"

                    # Create issue
                    result = self.create_issue(
                        team_id=team_id,
                        title=task_text[:255],  # Linear has 255 char limit for title
                        description=description,
                        project_id=project_id,
                        priority=task_priority,
                        label_ids=label_ids,
                        assignee_id=assignee_id,
                        state_id=backlog_state
                    )

                    if result.get('success'):
                        issue_info = result.get('issue', {})
                        created_issues.append({
                            'identifier': issue_info.get('identifier'),
                            'title': task_text[:255],
                            'url': issue_info.get('url'),
                            'phase': phase_name
                        })
                    else:
                        failed_issues.append({
                            'task': task_text,
                            'phase': phase_name,
                            'error': result.get('error', 'Unknown error')
                        })

            return {
                'success': len(failed_issues) == 0,
                'created_count': len(created_issues),
                'failed_count': len(failed_issues),
                'created_issues': created_issues,
                'failed_issues': failed_issues
            }

        except Exception as e:
            return {
                'success': False,
                'created_count': len(created_issues),
                'failed_count': len(failed_issues),
                'created_issues': created_issues,
                'failed_issues': failed_issues,
                'error': str(e)
            }


# Helper function to validate Linear API token
def validate_linear_token(token: str) -> bool:
    """
    Validate a Linear API token by making a simple API call

    Args:
        token: Linear API token to validate

    Returns:
        True if token is valid, False otherwise
    """
    try:
        service = LinearService(token)
        viewer = service.get_viewer()
        return bool(viewer.get('id'))
    except:
        return False
