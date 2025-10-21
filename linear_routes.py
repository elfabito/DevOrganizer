"""
Linear API Routes for app.py
Add these routes to app.py after the ClickUp routes (after line ~2022)

Instructions:
1. Add this import at the top of app.py:
   from linear_service import LinearService, validate_linear_token

2. Copy all routes below and paste them after the ClickUp routes section
"""

# ============================================================================
# LINEAR API ROUTES
# ============================================================================

# -----------------
# Token Management
# -----------------

@app.route('/api/user/linear-token', methods=['POST'])
@login_required
def save_linear_token():
    """Save Linear API token for current user"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()

        if not token:
            return jsonify({'success': False, 'error': 'Token is required'}), 400

        # Validate token format
        if not token.startswith('lin_api_'):
            return jsonify({'success': False, 'error': 'Invalid Linear token format. Token should start with "lin_api_"'}), 400

        # Validate token by making a test API call
        if not validate_linear_token(token):
            return jsonify({'success': False, 'error': 'Invalid Linear API token. Please check your token and try again.'}), 401

        # Save token to database
        user_id = session.get('user_id')
        success = user_storage.save_user_linear_token(user_id, token)

        if success:
            return jsonify({'success': True, 'message': 'Linear token saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save token'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/linear-token/check', methods=['GET'])
@login_required
def check_linear_token():
    """Check if current user has Linear token configured"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        return jsonify({
            'configured': bool(token)
        })

    except Exception as e:
        return jsonify({'configured': False, 'error': str(e)}), 500


@app.route('/api/user/linear-token', methods=['DELETE'])
@login_required
def delete_linear_token():
    """Delete Linear API token for current user"""
    try:
        user_id = session.get('user_id')
        success = user_storage.delete_user_linear_token(user_id)

        if success:
            return jsonify({'success': True, 'message': 'Linear token deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete token'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# -----------------
# Linear API Endpoints (Pro Plan Required)
# -----------------

@app.route('/linear/check-config', methods=['GET'])
@login_required
@require_plan('pro')
def check_linear_config():
    """Check if Linear is configured for current user"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        return jsonify({
            'configured': bool(token)
        })

    except Exception as e:
        return jsonify({'configured': False, 'error': str(e)}), 500


@app.route('/linear/teams', methods=['GET'])
@login_required
@require_plan('pro')
def get_linear_teams():
    """Get all Linear teams for authenticated user"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        linear = LinearService(token)
        teams = linear.get_teams()

        return jsonify({'teams': teams})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/linear/projects/<team_id>', methods=['GET'])
@login_required
@require_plan('pro')
def get_linear_projects(team_id):
    """Get all projects in a Linear team"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        linear = LinearService(token)
        projects = linear.get_projects(team_id)

        return jsonify({'projects': projects})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/linear/create-issues', methods=['POST'])
@login_required
@require_plan('pro')
def create_linear_issues():
    """Create issues in Linear from project phases"""
    try:
        user_id = session.get('user_id')
        token = user_storage.get_user_linear_token(user_id)

        if not token:
            return jsonify({'error': 'Linear token not configured'}), 401

        data = request.get_json()
        team_id = data.get('team_id')
        project_id = data.get('project_id')  # Optional
        phases = data.get('phases', [])

        if not team_id:
            return jsonify({'error': 'Team ID is required'}), 400

        if not phases:
            return jsonify({'error': 'No phases provided'}), 400

        linear = LinearService(token)
        result = linear.create_issues_from_phases(
            team_id=team_id,
            phases=phases,
            project_id=project_id if project_id else None
        )

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'created_count': 0,
            'failed_count': 0
        }), 500


# ============================================================================
# END OF LINEAR API ROUTES
# ============================================================================
