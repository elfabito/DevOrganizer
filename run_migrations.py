"""Run database migrations"""
import os
import sys
from flask_migrate import Migrate, upgrade
from app import app
from app import db

def run_migrations():
    """Run all pending database migrations"""
    with app.app_context():
        # Create the migrations directory if it doesn't exist
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        if not os.path.exists(migrations_dir):
            os.makedirs(migrations_dir, exist_ok=True)
            
        # Initialize Flask-Migrate
        migrate = Migrate(app, db)
        
        # Run migrations
        print("Running database migrations...")
        upgrade(directory=migrations_dir)
        print("Migrations completed successfully!")

if __name__ == '__main__':
    run_migrations()
