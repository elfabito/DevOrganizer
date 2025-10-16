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
  "clickup_plan": "Detailed task plan with phases using emojis like 🚀, 📋, 🎨, 🔒, 🚢, 📊"
}}

Guidelines:
1. Generate 3-5 relevant technical questions per category based on the project description
2. Recommend a modern, appropriate tech stack
3. Create 4-6 key milestones that represent major project phases
4. Format the ClickUp plan with emojis, phases, and specific tasks
5. Make questions specific and actionable for this particular project

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
