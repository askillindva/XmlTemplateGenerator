import os
import sqlite3
import json
import re
import logging
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Database configuration
DATABASE_PATH = 'actions.db'
TEMPLATES_FOLDER = './xml_templates/'

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

def get_available_templates():
    """Scan the templates folder and return list of XML template files."""
    templates = []
    try:
        if os.path.exists(TEMPLATES_FOLDER):
            for filename in os.listdir(TEMPLATES_FOLDER):
                if filename.endswith('.xml'):
                    templates.append(filename)
        logging.info(f"Found templates: {templates}")
    except Exception as e:
        logging.error(f"Error scanning templates folder: {e}")
    
    return sorted(templates)

def extract_jinja_variables(xml_content):
    """Extract unique Jinja2 variables from XML content."""
    # Pattern to match {{ variable_name }}
    pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
    variables = set(re.findall(pattern, xml_content))
    return sorted(list(variables))

def read_template_content(template_name):
    """Read and return the content of a template file."""
    try:
        template_path = os.path.join(TEMPLATES_FOLDER, template_name)
        with open(template_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logging.error(f"Error reading template {template_name}: {e}")
        return None

def render_xml_template(template_content, variables):
    """Render XML template with provided variables using Jinja2."""
    try:
        from jinja2 import Template
        template = Template(template_content)
        return template.render(**variables)
    except Exception as e:
        logging.error(f"Error rendering template: {e}")
        return None

def log_generation(template_name, submitted_data, generated_xml):
    """Log the XML generation to database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.utcnow().isoformat()
        submitted_data_json = json.dumps(submitted_data)
        
        cursor.execute('''
            INSERT INTO logs (timestamp, template_name, submitted_data, generated_xml)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, template_name, submitted_data_json, generated_xml))
        
        conn.commit()
        conn.close()
        logging.info(f"Logged generation for template: {template_name}")
    except Exception as e:
        logging.error(f"Error logging to database: {e}")

# HTML Templates
HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XML Template Generator</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center mb-5">
                    <h1 class="display-4">
                        <i class="fas fa-code text-primary me-3"></i>
                        XML Template Generator
                    </h1>
                    <p class="lead">Generate XML messages from predefined templates</p>
                </div>
                
                {% if templates %}
                    <div class="card">
                        <div class="card-header">
                            <h3><i class="fas fa-file-code me-2"></i>Available Templates</h3>
                        </div>
                        <div class="card-body">
                            <div class="list-group">
                                {% for template in templates %}
                                <a href="{{ url_for('template_form', template_name=template) }}" 
                                   class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                                    <div>
                                        <i class="fas fa-file-alt me-2"></i>
                                        <strong>{{ template }}</strong>
                                    </div>
                                    <i class="fas fa-chevron-right"></i>
                                </a>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                {% else %}
                    <div class="alert alert-warning text-center">
                        <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                        <h4>No Templates Found</h4>
                        <p>No XML templates were found in the <code>./xml_templates/</code> folder.</p>
                        <p>Please add some .xml template files to get started.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
'''

FORM_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generate XML - {{ template_name }}</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('home') }}">
                                <i class="fas fa-home me-1"></i>Home
                            </a>
                        </li>
                        <li class="breadcrumb-item active">{{ template_name }}</li>
                    </ol>
                </nav>
                
                <div class="card">
                    <div class="card-header">
                        <h3>
                            <i class="fas fa-edit me-2"></i>
                            Generate XML from {{ template_name }}
                        </h3>
                    </div>
                    <div class="card-body">
                        {% if variables %}
                            <form method="POST" action="{{ url_for('generate_xml', template_name=template_name) }}">
                                <div class="row">
                                    {% for variable in variables %}
                                    <div class="col-md-6 mb-3">
                                        <label for="{{ variable }}" class="form-label">
                                            <i class="fas fa-tag me-1"></i>
                                            {{ variable }}
                                        </label>
                                        <input type="text" 
                                               class="form-control" 
                                               id="{{ variable }}" 
                                               name="{{ variable }}" 
                                               placeholder="Enter {{ variable }}"
                                               required>
                                    </div>
                                    {% endfor %}
                                </div>
                                
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end mt-4">
                                    <a href="{{ url_for('home') }}" class="btn btn-secondary me-md-2">
                                        <i class="fas fa-arrow-left me-1"></i>Back
                                    </a>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-cogs me-1"></i>Generate XML
                                    </button>
                                </div>
                            </form>
                        {% else %}
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                This template doesn't contain any variables to fill.
                            </div>
                            <form method="POST" action="{{ url_for('generate_xml', template_name=template_name) }}">
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                    <a href="{{ url_for('home') }}" class="btn btn-secondary me-md-2">
                                        <i class="fas fa-arrow-left me-1"></i>Back
                                    </a>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-cogs me-1"></i>Generate XML
                                    </button>
                                </div>
                            </form>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

RESULT_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated XML - {{ template_name }}</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .xml-content {
            font-family: 'Courier New', monospace;
            background-color: var(--bs-dark);
            border: 1px solid var(--bs-border-color);
            border-radius: 0.375rem;
            padding: 1rem;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 500px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('home') }}">
                                <i class="fas fa-home me-1"></i>Home
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('template_form', template_name=template_name) }}">
                                {{ template_name }}
                            </a>
                        </li>
                        <li class="breadcrumb-item active">Generated XML</li>
                    </ol>
                </nav>
                
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h3>
                            <i class="fas fa-check-circle text-success me-2"></i>
                            Generated XML
                        </h3>
                        <button class="btn btn-outline-primary" onclick="copyToClipboard()">
                            <i class="fas fa-copy me-1"></i>Copy to Clipboard
                        </button>
                    </div>
                    <div class="card-body">
                        <div id="xml-content" class="xml-content">{{ generated_xml }}</div>
                        
                        <div class="mt-4 d-grid gap-2 d-md-flex justify-content-md-end">
                            <a href="{{ url_for('template_form', template_name=template_name) }}" 
                               class="btn btn-secondary me-md-2">
                                <i class="fas fa-edit me-1"></i>Generate Another
                            </a>
                            <a href="{{ url_for('home') }}" class="btn btn-primary">
                                <i class="fas fa-home me-1"></i>Back to Templates
                            </a>
                        </div>
                    </div>
                </div>
                
                {% if submitted_data %}
                <div class="card mt-4">
                    <div class="card-header">
                        <h5><i class="fas fa-info-circle me-2"></i>Submitted Data</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            {% for key, value in submitted_data.items() %}
                            <div class="col-md-6 mb-2">
                                <strong>{{ key }}:</strong> {{ value }}
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function copyToClipboard() {
            const xmlContent = document.getElementById('xml-content').textContent;
            navigator.clipboard.writeText(xmlContent).then(function() {
                // Show success feedback
                const button = document.querySelector('button[onclick="copyToClipboard()"]');
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                button.classList.remove('btn-outline-primary');
                button.classList.add('btn-success');
                
                setTimeout(function() {
                    button.innerHTML = originalText;
                    button.classList.remove('btn-success');
                    button.classList.add('btn-outline-primary');
                }, 2000);
            }).catch(function(err) {
                console.error('Could not copy text: ', err);
                alert('Failed to copy to clipboard. Please select and copy manually.');
            });
        }
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
def home():
    """Display homepage with available templates."""
    templates = get_available_templates()
    return render_template_string(HOME_TEMPLATE, templates=templates)

@app.route('/template/<template_name>')
def template_form(template_name):
    """Display form for the selected template."""
    # Validate template exists
    if template_name not in get_available_templates():
        flash(f'Template "{template_name}" not found.', 'error')
        return redirect(url_for('home'))
    
    # Read template content and extract variables
    content = read_template_content(template_name)
    if content is None:
        flash(f'Error reading template "{template_name}".', 'error')
        return redirect(url_for('home'))
    
    variables = extract_jinja_variables(content)
    
    return render_template_string(FORM_TEMPLATE, 
                                  template_name=template_name, 
                                  variables=variables)

@app.route('/generate/<template_name>', methods=['POST'])
def generate_xml(template_name):
    """Generate XML from template and form data."""
    # Validate template exists
    if template_name not in get_available_templates():
        flash(f'Template "{template_name}" not found.', 'error')
        return redirect(url_for('home'))
    
    # Read template content
    content = read_template_content(template_name)
    if content is None:
        flash(f'Error reading template "{template_name}".', 'error')
        return redirect(url_for('home'))
    
    # Get form data
    form_data = dict(request.form)
    
    # Generate XML
    generated_xml = render_xml_template(content, form_data)
    if generated_xml is None:
        flash('Error generating XML. Please check your input.', 'error')
        return redirect(url_for('template_form', template_name=template_name))
    
    # Log to database
    log_generation(template_name, form_data, generated_xml)
    
    return render_template_string(RESULT_TEMPLATE,
                                  template_name=template_name,
                                  generated_xml=generated_xml,
                                  submitted_data=form_data)

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template_string('''
    <div class="container mt-5 text-center">
        <h1>404 - Page Not Found</h1>
        <p><a href="{{ url_for('home') }}" class="btn btn-primary">Go Home</a></p>
    </div>
    '''), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template_string('''
    <div class="container mt-5 text-center">
        <h1>500 - Internal Server Error</h1>
        <p>Something went wrong. Please try again.</p>
        <p><a href="{{ url_for('home') }}" class="btn btn-primary">Go Home</a></p>
    </div>
    '''), 500

if __name__ == '__main__':
    # Create templates folder if it doesn't exist
    os.makedirs(TEMPLATES_FOLDER, exist_ok=True)
    
    # Initialize database
    init_database()
    
    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=True)
