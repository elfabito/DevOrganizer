"""
Dev Project Organizer - Main Flask Application
A tool to help developers organize and plan new projects with AI assistance
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from storage import ProjectStorage
from ai_service import generate_plan, generate_weekly_summary, generate_feature_suggestions, generate_estimation
from weekly_summary_storage import WeeklySummaryStorage
import os

STORAGE_TYPE = 'sqlite'  # Opciones: 'json' o 'sqlite'

# Import storage based on configuration
if STORAGE_TYPE == 'sqlite':
    from storage_sqlite import ProjectStorageSQLite as StorageClass
    STORAGE_FILE = 'projects.db'
else:
    from storage import ProjectStorage as StorageClass
    STORAGE_FILE = 'projects.json'

from ai_service import generate_plan

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-project-organizer-secret-key-change-in-production'

# Initialize storage
storage = StorageClass(STORAGE_FILE)
weekly_storage = WeeklySummaryStorage(STORAGE_FILE)


@app.route('/')
def index():
    """
    Home page - displays list of all projects and estimations
    """
    projects = storage.load_all_projects()
    # Sort by creation date (newest first)
    projects.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Load estimations
    estimations = storage.load_all_estimations()
    
    return render_template('index.html', projects=projects, estimations=estimations)


@app.route('/create', methods=['GET'])
def create_project_form():
    """
    Display the create project form
    """
    return render_template('create.html')


@app.route('/create-estimation', methods=['GET'])
def create_estimation_form():
    """
    Display the create estimation form
    """
    return render_template('estimation_create.html')


@app.route('/generate-plan', methods=['POST'])
def generate_project_plan():
    """
    API endpoint to generate AI plan for a project
    Receives project name and description, returns AI-generated data
    """
    try:
        data = request.get_json()
        project_name = data.get('name', '').strip()
        project_description = data.get('description', '').strip()
        
        # Validate input
        if not project_name or not project_description:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400
        
        # Generate AI plan
        ai_data = generate_plan(project_name, project_description)
        
        return jsonify({
            'success': True,
            'ai_data': ai_data
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate plan: {str(e)}'
        }), 500


@app.route('/save-project', methods=['POST'])
def save_project():
    """
    Save a project with its AI-generated data
    """
    try:
        data = request.get_json()
        project_name = data.get('name', '').strip()
        project_brief = data.get('brief', '').strip()
        ai_data = data.get('ai_data', {})
        
        # Validate input
        if not project_name or not project_brief:
            return jsonify({
                'error': 'Project name and description are required'
            }), 400
        
        if not ai_data:
            return jsonify({
                'error': 'AI data is required. Please generate a plan first.'
            }), 400
        
        # Save project
        saved_project = storage.save_project(project_name, project_brief, ai_data)
        
        return jsonify({
            'success': True,
            'project_id': saved_project['id'],
            'message': 'Project saved successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to save project: {str(e)}'
        }), 500


@app.route('/project/<project_id>')
def view_project(project_id):
    """
    View detailed information about a specific project
    """
    project = storage.get_project_by_id(project_id)
    
    if not project:
        return render_template('error.html', 
                             message='Project not found',
                             back_url=url_for('index')), 404
    
    # Load weekly summaries for this project
    all_summaries = weekly_storage.get_all_weekly_summaries()
    project_summaries = [s for s in all_summaries if s['project_name'] == project['name']]
    
    # Load feature suggestions for this project
    feature_suggestions = storage.get_latest_feature_suggestion(project_id)
    
    return render_template('project_detail.html', 
                         project=project, 
                         weekly_summaries=project_summaries,
                         feature_suggestions=feature_suggestions)


@app.route('/delete-project/<project_id>', methods=['POST'])
def delete_project(project_id):
    """
    Delete a project by ID
    """
    try:
        success = storage.delete_project(project_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Project deleted successfully'
            })
        else:
            return jsonify({
                'error': 'Project not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to delete project: {str(e)}'
        }), 500


@app.route('/create-weekly-summary', methods=['POST'])
def create_weekly_summary():
    """
    Create a new weekly summary for a project
    """
    try:
        data = request.get_json()
        project_name = data.get('project_name', '').strip()
        
        if not project_name:
            return jsonify({
                'error': 'Project name is required'
            }), 400
        
        # Create new weekly summary
        summary = weekly_storage.create_weekly_summary(project_name)
        
        return jsonify({
            'success': True,
            'summary_id': summary['id'],
            'message': 'Weekly summary created successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to create weekly summary: {str(e)}'
        }), 500


@app.route('/weekly-summary/<summary_id>')
def view_weekly_summary(summary_id):
    """
    View and edit a specific weekly summary
    """
    summary = weekly_storage.get_weekly_summary_by_id(summary_id)
    
    if not summary:
        return render_template('error.html', 
                             message='Weekly summary not found',
                             back_url=url_for('index')), 404
    
    # Get list of all projects for the dropdown
    projects = storage.load_all_projects()
    project_names = [p['name'] for p in projects]
    
    # Find the project ID for the back button
    project_id = None
    for project in projects:
        if project['name'] == summary['project_name']:
            project_id = project['id']
            break
    
    return render_template('weekly_summary.html', summary=summary, project_names=project_names, project_id=project_id)


@app.route('/update-weekly-summary/<summary_id>', methods=['POST'])
def update_weekly_summary(summary_id):
    """
    Update weekly summary notes
    """
    try:
        data = request.get_json()
        week_notes = data.get('week_notes')
        
        if not week_notes:
            return jsonify({
                'error': 'Week notes are required'
            }), 400
        
        # Update the summary
        success = weekly_storage.update_weekly_summary(summary_id, week_notes=week_notes)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Weekly notes saved successfully!'
            })
        else:
            return jsonify({
                'error': 'Weekly summary not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to update weekly summary: {str(e)}'
        }), 500


@app.route('/generate-week-summary', methods=['POST'])
def generate_week_summary():
    """
    API endpoint to generate AI summary from weekly notes
    """
    try:
        data = request.get_json()
        summary_id = data.get('summary_id', '').strip()
        project_name = data.get('project_name', '').strip()
        week_notes = data.get('week_notes', {})
        
        if not project_name or not week_notes:
            return jsonify({
                'error': 'Project name and week notes are required'
            }), 400
        
        # Generate AI summary
        ai_summary = generate_weekly_summary(project_name, week_notes)
        
        # Update the summary in database if summary_id provided
        if summary_id:
            weekly_storage.update_weekly_summary(summary_id, ai_summary=ai_summary)
        
        return jsonify({
            'success': True,
            'summary': ai_summary
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate summary: {str(e)}'
        }), 500


@app.route('/delete-weekly-summary/<summary_id>', methods=['POST'])
def delete_weekly_summary(summary_id):
    """
    Delete a weekly summary by ID
    """
    try:
        success = weekly_storage.delete_weekly_summary(summary_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Weekly summary deleted successfully'
            })
        else:
            return jsonify({
                'error': 'Weekly summary not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to delete weekly summary: {str(e)}'
        }), 500


@app.route('/generate-feature-suggestions', methods=['POST'])
def generate_feature_suggestions_endpoint():
    """
    API endpoint to generate AI feature suggestions from project audit
    """
    try:
        data = request.get_json()
        project_id = data.get('project_id', '').strip()
        project_name = data.get('project_name', '').strip()
        audit_text = data.get('audit_text', '').strip()
        
        # Validate input
        if not project_id or not project_name:
            return jsonify({
                'error': 'Project ID and name are required'
            }), 400
        
        if not audit_text:
            return jsonify({
                'error': 'Project audit text is required'
            }), 400
        
        # Generate AI feature suggestions
        suggestions = generate_feature_suggestions(project_name, audit_text)
        
        # Save suggestions to database
        saved_suggestion = storage.save_feature_suggestions(
            project_id=project_id,
            project_name=project_name,
            audit_text=audit_text,
            suggestions=suggestions
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'suggestion_id': saved_suggestion['id']
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate feature suggestions: {str(e)}'
        }), 500


@app.route('/generate-estimation', methods=['POST'])
def generate_estimation_endpoint():
    """
    API endpoint to generate AI project estimation
    """
    try:
        data = request.get_json()
        project_name = data.get('project_name', '').strip()
        project_description = data.get('project_description', '').strip()
        
        # Validate input
        if not project_name:
            return jsonify({
                'error': 'Project name is required'
            }), 400
        
        if not project_description:
            return jsonify({
                'error': 'Project description is required'
            }), 400
        
        # Generate AI estimation
        estimation_data = generate_estimation(project_name, project_description)
        
        # Check for errors
        if 'error' in estimation_data:
            return jsonify({
                'error': estimation_data['error']
            }), 400
        
        # Save estimation to database
        saved_estimation = storage.save_estimation(
            project_name=project_name,
            project_description=project_description,
            phases=estimation_data['phases'],
            total_hours=estimation_data['total_hours']
        )
        
        return jsonify({
            'success': True,
            'estimation_id': saved_estimation['id'],
            'phases': estimation_data['phases'],
            'total_hours': estimation_data['total_hours']
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to generate estimation: {str(e)}'
        }), 500


@app.route('/estimation/<estimation_id>')
def view_estimation(estimation_id):
    """
    View detailed information about a specific estimation
    """
    estimation = storage.get_estimation_by_id(estimation_id)
    
    if not estimation:
        return render_template('error.html', 
                             message='Estimation not found',
                             back_url=url_for('index')), 404
    
    return render_template('estimation_detail.html', estimation=estimation)


@app.route('/delete-estimation/<estimation_id>', methods=['POST'])
def delete_estimation(estimation_id):
    """
    Delete an estimation by ID
    """
    try:
        success = storage.delete_estimation(estimation_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Estimation deleted successfully'
            })
        else:
            return jsonify({
                'error': 'Estimation not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Failed to delete estimation: {str(e)}'
        }), 500


@app.route('/health')
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'app': 'Dev Project Organizer',
        'version': '1.0.0'
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('error.html', 
                         message='Page not found',
                         back_url=url_for('index')), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('error.html', 
                         message='Internal server error',
                         back_url=url_for('index')), 500


if __name__ == '__main__':
    # Ensure templates directory exists
    os.makedirs('templates', exist_ok=True)
    
    # Run the Flask development server
    print("=" * 60)
    print("🚀 Dev Project Organizer Starting...")
    print("=" * 60)
    print("📂 Storage: projects.json")
    print("🌐 Server: http://127.0.0.1:5000")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
