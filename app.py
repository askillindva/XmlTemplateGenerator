import os
import sqlite3
import logging
from flask import Flask, render_template_string
from lsv import lsv_bp
from future_app import future_app_bp

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Database configuration
DATABASE_PATH = 'actions.db'

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
# MAIN HOMEPAGE HTML TEMPLATE
# =============================================================================

MAIN_HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ABAssist - Application Support Platform</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('main_home') }}">
                <i class="fas fa-tools me-2"></i>
                ABAssist
            </a>
        </div>
    </nav>
    
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <div class="text-center mb-5">
                    <h1 class="display-4">
                        <i class="fas fa-tools text-primary me-3"></i>
                        ABAssist
                    </h1>
                    <p class="lead">Application Support and Reliability Engineering Platform</p>
                    <p class="text-muted">Tools and utilities for engineering teams</p>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-code fa-3x text-primary"></i>
                                </div>
                                <h4 class="card-title">LSV</h4>
                                <p class="card-text">Log, Script, and Validation tools for application support operations</p>
                                <a href="{{ url_for('lsv.home') }}" class="btn btn-primary">
                                    <i class="fas fa-arrow-right me-1"></i>Enter LSV
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-rocket fa-3x text-secondary"></i>
                                </div>
                                <h4 class="card-title">Future Sub-App</h4>
                                <p class="card-text">Additional sub-applications will be added here as needed</p>
                                <a href="{{ url_for('future_app.home') }}" class="btn btn-secondary">
                                    <i class="fas fa-arrow-right me-1"></i>Preview
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

# =============================================================================
# MAIN HOMEPAGE ROUTES
# =============================================================================

@app.route('/')
def main_home():
    """Display main ABAssist homepage."""
    return render_template_string(MAIN_HOME_TEMPLATE)

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