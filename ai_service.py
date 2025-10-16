"""
AI Service module for Dev Project Organizer
Handles AI plan generation using Groq API (Fast & Free!)
"""

import os
import json
from typing import Dict
from groq import Groq
from dotenv import load_dotenv

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
