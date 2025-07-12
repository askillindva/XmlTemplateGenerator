import os
import sqlite3
import logging
from flask import Flask, render_template, render_template_string
from dotenv import load_dotenv
from lsv import lsv_bp
from future_app import future_app_bp

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Load configuration from environment variables
app.config['FLASK_ENV'] = os.environ.get('FLASK_ENV', 'development')
app.config['FLASK_DEBUG'] = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

# Database configuration
DATABASE_PATH = os.environ.get('DATABASE_URL', 'sqlite:///actions.db').replace('sqlite:///', '')

# =============================================================================
# SHARED UTILITIES & DATABASE FUNCTIONS
# =============================================================================

def init_database():
    """Initialize SQLite database and create logs table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                template_name TEXT NOT NULL,
                submitted_data TEXT NOT NULL,
                generated_xml TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

# Initialize database on startup
init_database()

# =============================================================================
# REGISTER SUB-APPLICATION BLUEPRINTS
# =============================================================================

app.register_blueprint(lsv_bp)
app.register_blueprint(future_app_bp)



# =============================================================================
# MAIN HOMEPAGE ROUTES
# =============================================================================

@app.route('/')
def main_home():
    """Display main ABAssist homepage."""
    return render_template('main_home.html')

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found - ABAssist</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6 text-center">
                <i class="fas fa-exclamation-triangle fa-5x text-warning mb-4"></i>
                <h1 class="display-4">404</h1>
                <h2>Page Not Found</h2>
                <p class="lead">The page you're looking for doesn't exist.</p>
                <a href="{{ url_for('main_home') }}" class="btn btn-primary">
                    <i class="fas fa-home me-1"></i>Go Home
                </a>
            </div>
        </div>
    </div>
</body>
</html>
    '''), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error - ABAssist</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6 text-center">
                <i class="fas fa-server fa-5x text-danger mb-4"></i>
                <h1 class="display-4">500</h1>
                <h2>Internal Server Error</h2>
                <p class="lead">Something went wrong on our end.</p>
                <a href="{{ url_for('main_home') }}" class="btn btn-primary">
                    <i class="fas fa-home me-1"></i>Go Home
                </a>
            </div>
        </div>
    </div>
</body>
</html>
    '''), 500

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)