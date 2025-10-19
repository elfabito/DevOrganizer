"""
AI Service module for Dev Project Organizer
Handles AI plan generation using Groq API (Fast & Free!)
"""

import os
import json
from typing import Dict, List
from groq import Groq
from dotenv import load_dotenv
from flask import current_app

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client
# Set your API key as environment variable: GROQ_API_KEY
# Get your free API key from: https://console.groq.com/keys
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_plan(project_name: str, project_description: str) -> Dict:
    """
    Generate AI-based project plan with technical questions and task breakdown using Groq
    
    Args:
        project_name: Name of the project
        project_description: Detailed description of the project
        
    Returns:
        Dictionary containing AI-generated data:
        - questions: Categorized technical questions
        - clickup_plan: Formatted task plan
        - tech_stack_summary: Suggested technology stack
        - key_milestones: List of major milestones
    """
    
    try:
        # Create the prompt for Groq
        prompt = f"""You are a senior software architect and project planning expert. Analyze this project and provide detailed planning information.

Project Name: {project_name}
Project Description: {project_description}

Please provide a comprehensive analysis in the following JSON format:

{{
  "questions": {{
    "Authentication & Authorization": ["question 1", "question 2", ...],
    "Database & Storage": ["question 1", "question 2", ...],
    "Security & Compliance": ["question 1", "question 2", ...],
    "Architecture & Scalability": ["question 1", "question 2", ...],
    "Others": ["question 1", "question 2", ...]
  }},
  "tech_stack_summary": "Brief description of recommended technology stack",
  "key_milestones": ["milestone 1", "milestone 2", "milestone 3", "milestone 4", "milestone 5"],
  "clickup_plan": {{
    "phases": [
      {{
        "name": "Phase name with emoji",
        "tasks": [
          {{"task": "Task description", "priority": "high"}},
          {{"task": "Task description", "priority": "medium"}},
          {{"task": "Task description", "priority": "low"}}
        ]
      }}
    ]
  }}
}}

Guidelines:
1. Generate 3-5 relevant technical questions per category based on the project description
2. Recommend a modern, appropriate tech stack
3. Create 4-6 key milestones that represent major project phases
4. Create a ClickUp plan with 4-6 phases, each with 3-5 tasks
5. Use emojis for phase names (🚀, 📋, 🎨, 🔒, 🚢, 📊, etc.)
6. Set task priorities: "high", "medium", or "low"
7. Make questions and tasks specific and actionable for this particular project

Return ONLY the JSON object, no additional text or markdown formatting."""

        # Call Groq API with llama model (fast and free!)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast, powerful, and free!
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful software architecture assistant that provides structured project planning advice in JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse the response
        ai_response = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if ai_response.startswith("```json"):
            ai_response = ai_response[7:]
        if ai_response.startswith("```"):
            ai_response = ai_response[3:]
        if ai_response.endswith("```"):
            ai_response = ai_response[:-3]
        
        ai_response = ai_response.strip()
        
        # Parse JSON
        ai_data = json.loads(ai_response)
        
        return ai_data
        
    except Exception as e:
        # If Groq fails, return an error structure
        print(f"Error calling Groq API: {str(e)}")
        raise Exception(f"Failed to generate AI plan: {str(e)}. Please check your GROQ_API_KEY environment variable.")


def generate_weekly_summary(project_name: str, week_notes: Dict) -> str:
    """
    Generate AI-based weekly summary from daily notes using Groq
    
    Args:
        project_name: Name of the project
        week_notes: Dictionary with daily notes (Monday-Friday)
        
    Returns:
        AI-generated summary text
    """
    
    try:
        # Format the week notes for the prompt
        notes_text = ""
        for day, note in week_notes.items():
            if note and note.strip():
                notes_text += f"\n**{day}:**\n{note}\n"
        
        if not notes_text.strip():
            return "No notes were provided for this week."
        
        # Create the prompt for Groq
        prompt = f"""You are a professional project manager creating a weekly summary report.

Project: {project_name}

Weekly Notes:
{notes_text}

Please create a concise, professional weekly summary that:
1. Highlights the main accomplishments and progress made during the week
2. Identifies any blockers or challenges encountered
3. Mentions key technical decisions or implementations
4. Suggests next steps or priorities for the following week

Keep the summary clear, actionable, and focused on the most important points. Write in a professional tone suitable for a project status report.

Return only the summary text, no additional formatting or headers."""

        # Call Groq API with llama model
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful project management assistant that creates clear, concise weekly summaries from daily work notes."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        # Get the summary from response
        summary = response.choices[0].message.content.strip()
        
        return summary
        
    except Exception as e:
        print(f"Error calling Groq API for weekly summary: {str(e)}")
        raise Exception(f"Failed to generate weekly summary: {str(e)}. Please check your GROQ_API_KEY environment variable.")


def generate_estimation(project_name: str, project_description: str) -> Dict:
    """
    Generate AI-based project estimation with phases and hours using Groq
    
    Args:
        project_name: Name of the project
        project_description: Detailed description of the project
        
    Returns:
        Dictionary containing:
        - phases: List of project phases with tasks and hours
        - total_hours: Total estimated hours
        - error: Optional error message if something went wrong
    """
    
    # Define default error response
    error_response = {
        "phases": [],
        "total_hours": 0,
        "error": ""
    }
    
    try:
        # Validate input
        if not project_description or not project_description.strip():
            error_response["error"] = "Please provide a project description"
            return error_response
        
        # Create the prompt for Groq
        prompt = f"""You are a senior project manager and software estimation expert. Analyze this project and provide a detailed time estimation.

Project Name: {project_name}

Project Description:
{project_description}

IMPORTANT: You MUST respond with a valid JSON object containing the following structure:
{{
  "phases": [
    {{
      "name": "Phase name with emoji (e.g., 🎨 Design & Planning)",
      "tasks": [
        {{"task": "Task description", "hours": 8}},
        {{"task": "Task description", "hours": 16}},
        {{"task": "Task description", "hours": 12}}
      ],
      "total_hours": 36
    }}
  ],
  "total_hours": 36
}}

Your response must be a valid JSON object that can be parsed with json.loads(). Do not include any other text, explanations, or markdown formatting outside of the JSON object.

Guidelines:
1. Create 4-7 realistic phases based on the project scope
2. Each phase should have 3-6 specific, actionable tasks
3. Estimate hours realistically (consider complexity, testing, debugging)
4. Include phases like: Planning/Design, Development, Testing, Deployment, Documentation
5. Use emojis for phase names (🎨, 💻, 🧪, 🚀, 📚, 🔒, etc.)
6. total_hours in each phase should equal the sum of task hours
7. Overall total_hours should equal the sum of all phase hours
8. Be specific about what each task involves
9. Consider the full software development lifecycle

Remember: Your response must be a valid JSON object and nothing else!"""

        # Call Groq API with llama model
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful project estimation assistant that provides accurate time estimates in JSON format. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
        except Exception as api_error:
            current_app.logger.error(f"Groq API error: {str(api_error)}")
            error_response["error"] = "Failed to connect to AI service. Please try again later."
            return error_response
        
        # Parse the response
        ai_response = response.choices[0].message.content.strip()
        
        # Add debug logging for the raw AI response
        current_app.logger.debug(f"Raw AI response: {ai_response}")
        
        try:
            # Clean the response to extract JSON
            json_str = ai_response
            
            # Remove markdown code blocks if present
            if '```json' in json_str:
                json_str = json_str.split('```json')[1]
                if '```' in json_str:
                    json_str = json_str.split('```')[0]
            elif '```' in json_str:
                parts = json_str.split('```')
                # Find the part that looks like JSON (starts with { and ends with })
                for part in parts:
                    part = part.strip()
                    if part.startswith('{') and part.endswith('}'):
                        json_str = part
                        break
            
            # Clean up any remaining whitespace
            json_str = json_str.strip()
            
            # Ensure the response is valid JSON
            estimation_data = json.loads(json_str)
            
            # Log the parsed data
            current_app.logger.debug(f"Parsed estimation data: {json.dumps(estimation_data, indent=2)}")
            
            # Ensure we have a dictionary
            if not isinstance(estimation_data, dict):
                raise ValueError(f"Expected dictionary, got {type(estimation_data).__name__}")
            
            # Validate and clean the response structure
            result = {
                "phases": [],
                "total_hours": 0,
                "error": ""
            }
            
            # Validate phases
            if "phases" not in estimation_data or not isinstance(estimation_data["phases"], list):
                raise ValueError("Missing or invalid 'phases' in response")
            
            # Process each phase
            for phase in estimation_data["phases"]:
                if not isinstance(phase, dict):
                    continue
                    
                # Ensure phase has required fields
                clean_phase = {
                    "name": str(phase.get("name", "Unnamed Phase")),
                    "tasks": [],
                    "total_hours": 0
                }
                
                # Process tasks
                if isinstance(phase.get("tasks"), list):
                    for task in phase["tasks"]:
                        if not isinstance(task, dict):
                            continue
                            
                        clean_task = {
                            "task": str(task.get("task", "Unnamed task")),
                            "hours": max(0, int(float(str(task.get("hours", 0)) or 0)))
                        }
                        clean_phase["tasks"].append(clean_task)
                
                # Calculate phase total hours if not provided
                if "total_hours" in phase and isinstance(phase["total_hours"], (int, float)):
                    clean_phase["total_hours"] = max(0, int(phase["total_hours"]))
                else:
                    clean_phase["total_hours"] = sum(task.get("hours", 0) for task in clean_phase["tasks"])
                
                result["phases"].append(clean_phase)
            
            # Calculate total hours if not provided
            if "total_hours" in estimation_data and isinstance(estimation_data["total_hours"], (int, float)):
                result["total_hours"] = max(0, int(estimation_data["total_hours"]))
            else:
                result["total_hours"] = sum(phase["total_hours"] for phase in result["phases"])
            
            # Ensure we have at least one phase
            if not result["phases"]:
                raise ValueError("No valid phases found in the response")
                
            return result
            
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response: {str(e)}"
            current_app.logger.error(f"{error_msg}\nResponse was: {ai_response}")
            error_response["error"] = "Failed to process AI response. The response was not valid JSON."
            return error_response
            
        except Exception as e:
            error_msg = f"Error processing estimation data: {str(e)}"
            current_app.logger.error(f"{error_msg}\nResponse was: {ai_response}")
            error_response["error"] = f"Error processing estimation: {str(e)}"
            return error_response
        
    except Exception as e:
        error_msg = f"Error in generate_estimation: {str(e)}"
        current_app.logger.error(error_msg, exc_info=True)
        error_response["error"] = f"Failed to generate estimation: {str(e)}"
        return error_response


def generate_estimation_refinement(project_name: str, project_description: str, current_estimation: Dict, feedback: str) -> Dict:
    """
    Refine an existing estimation based on user feedback using Groq
    
    Args:
        project_name: Name of the project
        project_description: Original project description
        current_estimation: The current estimation to refine
        feedback: User's feedback or adjustments
        
    Returns:
        Refined estimation with updated phases and hours
    """
    try:
        # Create the prompt for Groq
        prompt = f"""You are a senior software project estimator. You need to refine an existing project estimation 
based on the user's feedback. Here's the current estimation and the user's feedback:

PROJECT: {project_name}
DESCRIPTION: {project_description}

CURRENT ESTIMATION:
{json.dumps(current_estimation, indent=2)}

USER FEEDBACK:
{feedback}

Please provide a refined estimation based on this feedback. Consider:
1. Adjusting phase durations if the user mentioned specific phases being too long/short
2. Adding/removing phases if the user suggested changes to the project scope
3. Modifying tasks within phases as needed
4. Ensuring the total hours are updated accordingly

Return the response in the following JSON format:
{{
    "project_name": "Project Name",
    "project_description": "Project description",
    "total_hours": 120,
    "phases": [
        {{
            "name": "Phase 1: Planning",
            "total_hours": 20,
            "tasks": [
                {{"task": "Task 1 description", "hours": 5}},
                {{"task": "Task 2 description", "hours": 15}}
            ]
        }},
        ...
    ]
}}

Return ONLY the JSON object, no additional text or markdown formatting."""

        # Call Groq API
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful project estimation assistant that refines existing estimates based on user feedback."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse the response
        ai_response = response.choices[0].message.content.strip()
        
        # Clean up the response (remove markdown code blocks if present)
        if '```json' in ai_response:
            ai_response = ai_response.split('```json')[1].split('```')[0].strip()
        elif '```' in ai_response:
            ai_response = ai_response.split('```')[1].split('```')[0].strip()
            
        # Parse the JSON response
        refined_estimation = json.loads(ai_response)
        
        # Ensure all required fields are present
        required_fields = ['project_name', 'project_description', 'total_hours', 'phases']
        if not all(field in refined_estimation for field in required_fields):
            raise ValueError("Invalid response format from AI: Missing required fields")
            
        return refined_estimation
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to refine estimation: {str(e)}")


def generate_feature_suggestions(project_name: str, audit_text: str) -> List[Dict]:
    """
    Generate AI-based feature suggestions from project audit using Groq
    
    Args:
        project_name: Name of the project
        audit_text: User's detailed project audit or current status
        
    Returns:
        List of AI-generated feature suggestions
    """
    
    try:
        # Validate input
        if not audit_text or not audit_text.strip():
            return ["Please provide a project audit or current status to generate suggestions."]
        
        # Create the prompt for Groq
        prompt = f"""You are a senior product manager and software architect analyzing a project to suggest new features and improvements.

Project Name: {project_name}

Current Project Audit/Status:
{audit_text}

Based on the project audit above, please suggest 5-8 specific, actionable new features or improvements that would add value to this project. Consider:

1. User experience enhancements
2. Technical improvements and optimizations
3. New functionality that complements existing features
4. Security and performance improvements
5. Integration opportunities
6. Analytics and monitoring capabilities
7. Accessibility and usability improvements

Provide your suggestions as a JSON array of strings. Each suggestion should be:
- Specific and actionable
- Clearly described in 1-2 sentences
- Relevant to the project's current state
- Prioritized by potential impact

Return ONLY a JSON array in this exact format:
[
  "Feature suggestion 1 with clear description",
  "Feature suggestion 2 with clear description",
  "Feature suggestion 3 with clear description"
]

No additional text, just the JSON array."""

        # Call Groq API with llama model
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful product management assistant that provides actionable feature suggestions based on project analysis. Always respond with valid JSON arrays."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,
            max_tokens=1200
        )
        
        # Parse the response
        ai_response = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if ai_response.startswith("```json"):
            ai_response = ai_response[7:]
        if ai_response.startswith("```"):
            ai_response = ai_response[3:]
        if ai_response.endswith("```"):
            ai_response = ai_response[:-3]
        
        ai_response = ai_response.strip()
        
        # Parse JSON array
        suggestions = json.loads(ai_response)
        
        # Validate that we got a list
        if not isinstance(suggestions, list):
            raise ValueError("AI response was not a list")
        
        # Ensure we have at least some suggestions
        if len(suggestions) == 0:
            return ["No specific suggestions could be generated. Please provide more details about your project."]
        
        return suggestions
        
    except json.JSONDecodeError as e:
        print(f"Error parsing Groq API response: {str(e)}")
        # Return a fallback suggestion
        return [
            "Add comprehensive logging and monitoring to track application performance",
            "Implement user authentication and authorization system",
            "Create an admin dashboard for system management",
            "Add automated testing suite for critical features",
            "Implement API rate limiting and security measures"
        ]
    except Exception as e:
        print(f"Error calling Groq API for feature suggestions: {str(e)}")
        raise Exception(f"Failed to generate feature suggestions: {str(e)}. Please check your GROQ_API_KEY environment variable.")
