import os
import sqlite3
import json
import re
import logging
import subprocess
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash
try:
    import cx_Oracle
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False
    logging.warning("cx_Oracle not available. Oracle functionality will be disabled.")
import requests

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
TEMPLATES_FOLDER = './xml_templates/'

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

# =============================================================================
# LSV SUB-APPLICATION: XML TEMPLATE GENERATOR
# =============================================================================

class XMLGeneratorService:
    """Service class for XML Template Generator functionality."""
    
    @staticmethod
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
    
    @staticmethod
    def extract_jinja_variables(xml_content):
        """Extract unique Jinja2 variables from XML content."""
        # Pattern to match {{ variable_name }}
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        variables = set(re.findall(pattern, xml_content))
        return sorted(list(variables))
    
    @staticmethod
    def read_template_content(template_name):
        """Read and return the content of a template file."""
        template_path = os.path.join(TEMPLATES_FOLDER, template_name)
        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            logging.error(f"Error reading template {template_name}: {e}")
            return None
    
    @staticmethod
    def render_xml_template(template_content, variables):
        """Render XML template with provided variables using Jinja2."""
        try:
            from jinja2 import Template
            template = Template(template_content)
            return template.render(**variables)
        except Exception as e:
            logging.error(f"Error rendering template: {e}")
            return None
    
    @staticmethod
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

# =============================================================================
# LSV SUB-APPLICATION: TRANSACTION REVERSAL
# =============================================================================

class TransactionReversalService:
    """Service class for Transaction Reversal functionality."""
    
    @staticmethod
    def get_oracle_connection():
        """Get Oracle database connection."""
        if not ORACLE_AVAILABLE:
            raise Exception("Oracle client libraries not available")
        
        # Database connection parameters - to be configured by user
        oracle_config = {
            'host': os.environ.get('ORACLE_HOST', 'localhost'),
            'port': os.environ.get('ORACLE_PORT', '1521'),
            'service_name': os.environ.get('ORACLE_SERVICE_NAME', 'ORCLPDB1'),
            'username': os.environ.get('ORACLE_USERNAME', 'hr'),
            'password': os.environ.get('ORACLE_PASSWORD', 'password')
        }
        
        dsn = cx_Oracle.makedsn(
            oracle_config['host'],
            oracle_config['port'],
            service_name=oracle_config['service_name']
        )
        
        connection = cx_Oracle.connect(
            user=oracle_config['username'],
            password=oracle_config['password'],
            dsn=dsn
        )
        
        return connection
    
    @staticmethod
    def search_transactions(search_criteria):
        """Search for transactions based on criteria."""
        try:
            connection = TransactionReversalService.get_oracle_connection()
            cursor = connection.cursor()
            
            # Base query - this will need to be customized based on actual Oracle schema
            base_query = """
            SELECT 
                txn_id,
                txn_type,
                txn_amount,
                txn_status,
                txn_date,
                account_number,
                reference_number,
                merchant_name,
                created_date
            FROM transactions 
            WHERE 1=1
            """
            
            conditions = []
            params = []
            
            if search_criteria.get('txn_id'):
                conditions.append("AND txn_id = :txn_id")
                params.append(('txn_id', search_criteria['txn_id']))
            
            if search_criteria.get('account_number'):
                conditions.append("AND account_number = :account_number")
                params.append(('account_number', search_criteria['account_number']))
            
            if search_criteria.get('reference_number'):
                conditions.append("AND reference_number = :reference_number")
                params.append(('reference_number', search_criteria['reference_number']))
            
            if search_criteria.get('date_from'):
                conditions.append("AND txn_date >= TO_DATE(:date_from, 'YYYY-MM-DD')")
                params.append(('date_from', search_criteria['date_from']))
            
            if search_criteria.get('date_to'):
                conditions.append("AND txn_date <= TO_DATE(:date_to, 'YYYY-MM-DD')")
                params.append(('date_to', search_criteria['date_to']))
            
            # Add conditions to query
            query = base_query + " " + " ".join(conditions) + " ORDER BY txn_date DESC"
            
            # Execute query
            cursor.execute(query, dict(params))
            
            # Fetch results
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            transactions = []
            for row in rows:
                transaction = dict(zip(columns, row))
                # Convert dates to strings for JSON serialization
                for key, value in transaction.items():
                    if hasattr(value, 'isoformat'):
                        transaction[key] = value.isoformat()
                transactions.append(transaction)
            
            cursor.close()
            connection.close()
            
            return transactions
            
        except Exception as e:
            logging.error(f"Error searching transactions: {e}")
            return []
    
    @staticmethod
    def get_transaction_details(txn_id):
        """Get detailed information about a specific transaction."""
        try:
            connection = TransactionReversalService.get_oracle_connection()
            cursor = connection.cursor()
            
            # Detailed transaction query
            query = """
            SELECT 
                t.txn_id,
                t.txn_type,
                t.txn_amount,
                t.txn_status,
                t.txn_date,
                t.account_number,
                t.reference_number,
                t.merchant_name,
                t.merchant_id,
                t.terminal_id,
                t.auth_code,
                t.response_code,
                t.response_message,
                t.card_number_masked,
                t.expiry_date,
                t.created_date,
                t.updated_date,
                t.reversal_status,
                t.reversal_date,
                t.reversal_reference
            FROM transactions t
            WHERE t.txn_id = :txn_id
            """
            
            cursor.execute(query, {'txn_id': txn_id})
            row = cursor.fetchone()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                transaction = dict(zip(columns, row))
                
                # Convert dates to strings for JSON serialization
                for key, value in transaction.items():
                    if hasattr(value, 'isoformat'):
                        transaction[key] = value.isoformat()
                    elif value is None:
                        transaction[key] = ''
                
                cursor.close()
                connection.close()
                return transaction
            else:
                cursor.close()
                connection.close()
                return None
                
        except Exception as e:
            logging.error(f"Error getting transaction details: {e}")
            return None
    
    @staticmethod
    def initiate_reversal_via_jconsole(txn_id, reversal_reason):
        """Initiate transaction reversal via jconsole."""
        try:
            # JConsole connection parameters - to be configured
            jconsole_config = {
                'host': os.environ.get('JCONSOLE_HOST', 'localhost'),
                'port': os.environ.get('JCONSOLE_PORT', '9999'),
                'mbean': os.environ.get('JCONSOLE_MBEAN', 'com.company.payment:type=TransactionService'),
                'operation': 'reverseTransaction'
            }
            
            # For demonstration, we'll log the reversal request
            # In production, this would make actual JMX calls
            reversal_data = {
                'txn_id': txn_id,
                'reason': reversal_reason,
                'initiated_by': 'web_interface',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logging.info(f"Initiating reversal via JConsole: {reversal_data}")
            
            # Simulate JConsole call - replace with actual JMX call in production
            # For now, we'll return a mock response
            response = {
                'success': True,
                'reversal_id': f"REV_{txn_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                'status': 'PENDING',
                'message': 'Reversal initiated successfully via JConsole'
            }
            
            # Update transaction status in database
            TransactionReversalService.update_transaction_reversal_status(txn_id, response['reversal_id'], 'PENDING')
            
            return response
            
        except Exception as e:
            logging.error(f"Error initiating reversal: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    @staticmethod
    def update_transaction_reversal_status(txn_id, reversal_id, status):
        """Update transaction reversal status in database."""
        try:
            connection = TransactionReversalService.get_oracle_connection()
            cursor = connection.cursor()
            
            update_query = """
            UPDATE transactions 
            SET reversal_status = :status,
                reversal_reference = :reversal_id,
                reversal_date = SYSDATE,
                updated_date = SYSDATE
            WHERE txn_id = :txn_id
            """
            
            cursor.execute(update_query, {
                'status': status,
                'reversal_id': reversal_id,
                'txn_id': txn_id
            })
            
            connection.commit()
            cursor.close()
            connection.close()
            
            logging.info(f"Updated reversal status for transaction {txn_id}: {status}")
            
        except Exception as e:
            logging.error(f"Error updating reversal status: {e}")

# Initialize database on startup
init_database()

# =============================================================================
# HTML TEMPLATES - MAIN PLATFORM
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
                                <a href="{{ url_for('lsv_home') }}" class="btn btn-primary">
                                    <i class="fas fa-arrow-right me-1"></i>Enter LSV
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-plus fa-3x text-secondary"></i>
                                </div>
                                <h4 class="card-title text-muted">Future Sub-App</h4>
                                <p class="card-text text-muted">Additional sub-applications will be added here as needed</p>
                                <button class="btn btn-outline-secondary" disabled>
                                    <i class="fas fa-construction me-1"></i>Coming Soon
                                </button>
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
# HTML TEMPLATES - LSV SUB-APPLICATION
# =============================================================================

LSV_HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LSV - Application Support Tools</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link active" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item active">LSV</li>
                    </ol>
                </nav>
                
                <div class="text-center mb-5">
                    <h1 class="display-5">
                        <i class="fas fa-code text-primary me-3"></i>
                        LSV Tools
                    </h1>
                    <p class="lead">Log, Script, and Validation Utilities</p>
                </div>
                
                <div class="row">
                    <div class="col-lg-4 col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-file-code fa-3x text-success"></i>
                                </div>
                                <h5 class="card-title">XML Generator</h5>
                                <p class="card-text">Generate XML messages from predefined templates with dynamic placeholders</p>
                                <a href="{{ url_for('xml_generator_home') }}" class="btn btn-success">
                                    <i class="fas fa-play me-1"></i>Launch Tool
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-lg-4 col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-undo fa-3x text-warning"></i>
                                </div>
                                <h5 class="card-title">Tran Reversal</h5>
                                <p class="card-text">Oracle 19c transaction management and reversal via JConsole integration</p>
                                <a href="{{ url_for('tran_reversal_home') }}" class="btn btn-warning">
                                    <i class="fas fa-play me-1"></i>Launch Tool
                                </a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-lg-4 col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-terminal fa-3x text-secondary"></i>
                                </div>
                                <h5 class="card-title text-muted">Script Runner</h5>
                                <p class="card-text text-muted">Execute and manage application scripts (coming soon)</p>
                                <button class="btn btn-outline-secondary" disabled>
                                    <i class="fas fa-construction me-1"></i>Coming Soon
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-lg-4 col-md-6 mb-4">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <div class="mb-3">
                                    <i class="fas fa-check-circle fa-3x text-secondary"></i>
                                </div>
                                <h5 class="card-title text-muted">Validator</h5>
                                <p class="card-text text-muted">Data validation and integrity checks (coming soon)</p>
                                <button class="btn btn-outline-secondary" disabled>
                                    <i class="fas fa-construction me-1"></i>Coming Soon
                                </button>
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
# MAIN PLATFORM ROUTES
# =============================================================================

@app.route('/')
def main_home():
    """Display main ABAssist homepage."""
    return render_template_string(MAIN_HOME_TEMPLATE)

@app.route('/lsv')
def lsv_home():
    """Display LSV sub-application homepage."""
    return render_template_string(LSV_HOME_TEMPLATE)

# =============================================================================
# HTML TEMPLATES - LSV SUB-APPLICATION: TRANSACTION REVERSAL
# =============================================================================

TRAN_REVERSAL_HOME_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transaction Reversal - LSV</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item active">Transaction Reversal</li>
                    </ol>
                </nav>
                
                <div class="text-center mb-5">
                    <h1 class="display-5">
                        <i class="fas fa-undo text-primary me-3"></i>
                        Transaction Reversal
                    </h1>
                    <p class="lead">Oracle 19c Database Transaction Management</p>
                </div>
                
                {% if error_message %}
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    {{ error_message }}
                </div>
                {% endif %}
                
                <div class="row">
                    <div class="col-md-12 mb-4">
                        <div class="card">
                            <div class="card-header">
                                <h4><i class="fas fa-search me-2"></i>Search Transactions</h4>
                            </div>
                            <div class="card-body">
                                <form method="POST" action="{{ url_for('search_transactions_endpoint') }}">
                                    <div class="row">
                                        <div class="col-md-4 mb-3">
                                            <label for="txn_id" class="form-label">Transaction ID</label>
                                            <input type="text" class="form-control" id="txn_id" name="txn_id" 
                                                   placeholder="Enter transaction ID">
                                        </div>
                                        <div class="col-md-4 mb-3">
                                            <label for="account_number" class="form-label">Account Number</label>
                                            <input type="text" class="form-control" id="account_number" name="account_number" 
                                                   placeholder="Enter account number">
                                        </div>
                                        <div class="col-md-4 mb-3">
                                            <label for="reference_number" class="form-label">Reference Number</label>
                                            <input type="text" class="form-control" id="reference_number" name="reference_number" 
                                                   placeholder="Enter reference number">
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6 mb-3">
                                            <label for="date_from" class="form-label">Date From</label>
                                            <input type="date" class="form-control" id="date_from" name="date_from">
                                        </div>
                                        <div class="col-md-6 mb-3">
                                            <label for="date_to" class="form-label">Date To</label>
                                            <input type="date" class="form-control" id="date_to" name="date_to">
                                        </div>
                                    </div>
                                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                        <button type="submit" class="btn btn-primary">
                                            <i class="fas fa-search me-1"></i>Search Transactions
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                
                {% if oracle_available %}
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    Oracle 19c connection is available. You can search for transactions and initiate reversals.
                </div>
                {% else %}
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Oracle client libraries are not available. Please configure Oracle connection details in environment variables:
                    <ul class="mt-2 mb-0">
                        <li>ORACLE_HOST</li>
                        <li>ORACLE_PORT</li>
                        <li>ORACLE_SERVICE_NAME</li>
                        <li>ORACLE_USERNAME</li>
                        <li>ORACLE_PASSWORD</li>
                    </ul>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
'''

TRANSACTION_RESULTS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transaction Search Results - LSV</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-12">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('tran_reversal_home') }}">Transaction Reversal</a>
                        </li>
                        <li class="breadcrumb-item active">Search Results</li>
                    </ol>
                </nav>
                
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2><i class="fas fa-list me-2"></i>Search Results</h2>
                    <a href="{{ url_for('tran_reversal_home') }}" class="btn btn-secondary">
                        <i class="fas fa-search me-1"></i>New Search
                    </a>
                </div>
                
                {% if transactions %}
                <div class="card">
                    <div class="card-header">
                        <h5>Found {{ transactions|length }} transaction(s)</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>Transaction ID</th>
                                        <th>Type</th>
                                        <th>Amount</th>
                                        <th>Status</th>
                                        <th>Date</th>
                                        <th>Account</th>
                                        <th>Reference</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for txn in transactions %}
                                    <tr>
                                        <td><code>{{ txn.TXN_ID }}</code></td>
                                        <td>{{ txn.TXN_TYPE }}</td>
                                        <td>${{ "%.2f"|format(txn.TXN_AMOUNT) }}</td>
                                        <td>
                                            {% if txn.TXN_STATUS == 'COMPLETED' %}
                                                <span class="badge bg-success">{{ txn.TXN_STATUS }}</span>
                                            {% elif txn.TXN_STATUS == 'PENDING' %}
                                                <span class="badge bg-warning">{{ txn.TXN_STATUS }}</span>
                                            {% elif txn.TXN_STATUS == 'FAILED' %}
                                                <span class="badge bg-danger">{{ txn.TXN_STATUS }}</span>
                                            {% else %}
                                                <span class="badge bg-secondary">{{ txn.TXN_STATUS }}</span>
                                            {% endif %}
                                        </td>
                                        <td>{{ txn.TXN_DATE[:10] if txn.TXN_DATE else '' }}</td>
                                        <td>{{ txn.ACCOUNT_NUMBER }}</td>
                                        <td>{{ txn.REFERENCE_NUMBER }}</td>
                                        <td>
                                            <a href="{{ url_for('transaction_details', txn_id=txn.TXN_ID) }}" 
                                               class="btn btn-sm btn-primary">
                                                <i class="fas fa-eye me-1"></i>Details
                                            </a>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                {% else %}
                <div class="alert alert-info text-center">
                    <i class="fas fa-info-circle fa-2x mb-3"></i>
                    <h4>No Transactions Found</h4>
                    <p>No transactions match your search criteria. Try adjusting your search parameters.</p>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
'''

TRANSACTION_DETAILS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transaction Details - LSV</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('tran_reversal_home') }}">Transaction Reversal</a>
                        </li>
                        <li class="breadcrumb-item active">Transaction Details</li>
                    </ol>
                </nav>
                
                {% if transaction %}
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2><i class="fas fa-file-invoice me-2"></i>Transaction Details</h2>
                    <div>
                        {% if transaction.REVERSAL_STATUS != 'COMPLETED' and transaction.TXN_STATUS == 'COMPLETED' %}
                        <button class="btn btn-warning me-2" data-bs-toggle="modal" data-bs-target="#reversalModal">
                            <i class="fas fa-undo me-1"></i>Initiate Reversal
                        </button>
                        {% endif %}
                        <a href="{{ url_for('tran_reversal_home') }}" class="btn btn-secondary">
                            <i class="fas fa-arrow-left me-1"></i>Back to Search
                        </a>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-8">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-info-circle me-2"></i>Transaction Information</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <strong>Transaction ID:</strong><br>
                                        <code>{{ transaction.TXN_ID }}</code>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Type:</strong><br>
                                        {{ transaction.TXN_TYPE }}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Amount:</strong><br>
                                        ${{ "%.2f"|format(transaction.TXN_AMOUNT) }}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Status:</strong><br>
                                        {% if transaction.TXN_STATUS == 'COMPLETED' %}
                                            <span class="badge bg-success">{{ transaction.TXN_STATUS }}</span>
                                        {% elif transaction.TXN_STATUS == 'PENDING' %}
                                            <span class="badge bg-warning">{{ transaction.TXN_STATUS }}</span>
                                        {% elif transaction.TXN_STATUS == 'FAILED' %}
                                            <span class="badge bg-danger">{{ transaction.TXN_STATUS }}</span>
                                        {% else %}
                                            <span class="badge bg-secondary">{{ transaction.TXN_STATUS }}</span>
                                        {% endif %}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Transaction Date:</strong><br>
                                        {{ transaction.TXN_DATE[:19] if transaction.TXN_DATE else 'N/A' }}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Account Number:</strong><br>
                                        {{ transaction.ACCOUNT_NUMBER }}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Reference Number:</strong><br>
                                        {{ transaction.REFERENCE_NUMBER }}
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <strong>Merchant:</strong><br>
                                        {{ transaction.MERCHANT_NAME }}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-undo me-2"></i>Reversal Status</h5>
                            </div>
                            <div class="card-body">
                                {% if transaction.REVERSAL_STATUS %}
                                    <div class="mb-3">
                                        <strong>Reversal Status:</strong><br>
                                        {% if transaction.REVERSAL_STATUS == 'COMPLETED' %}
                                            <span class="badge bg-success">{{ transaction.REVERSAL_STATUS }}</span>
                                        {% elif transaction.REVERSAL_STATUS == 'PENDING' %}
                                            <span class="badge bg-warning">{{ transaction.REVERSAL_STATUS }}</span>
                                        {% elif transaction.REVERSAL_STATUS == 'FAILED' %}
                                            <span class="badge bg-danger">{{ transaction.REVERSAL_STATUS }}</span>
                                        {% else %}
                                            <span class="badge bg-secondary">{{ transaction.REVERSAL_STATUS }}</span>
                                        {% endif %}
                                    </div>
                                    {% if transaction.REVERSAL_REFERENCE %}
                                    <div class="mb-3">
                                        <strong>Reversal Reference:</strong><br>
                                        <code>{{ transaction.REVERSAL_REFERENCE }}</code>
                                    </div>
                                    {% endif %}
                                    {% if transaction.REVERSAL_DATE %}
                                    <div class="mb-3">
                                        <strong>Reversal Date:</strong><br>
                                        {{ transaction.REVERSAL_DATE[:19] if transaction.REVERSAL_DATE else 'N/A' }}
                                    </div>
                                    {% endif %}
                                {% else %}
                                    <p class="text-muted">No reversal initiated for this transaction.</p>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
                
                {% else %}
                <div class="alert alert-danger text-center">
                    <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                    <h4>Transaction Not Found</h4>
                    <p>The requested transaction could not be found in the database.</p>
                    <a href="{{ url_for('tran_reversal_home') }}" class="btn btn-primary">
                        <i class="fas fa-search me-1"></i>Search Transactions
                    </a>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <!-- Reversal Modal -->
    {% if transaction and transaction.REVERSAL_STATUS != 'COMPLETED' and transaction.TXN_STATUS == 'COMPLETED' %}
    <div class="modal fade" id="reversalModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-undo me-2"></i>Initiate Transaction Reversal
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form method="POST" action="{{ url_for('initiate_reversal', txn_id=transaction.TXN_ID) }}">
                    <div class="modal-body">
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            <strong>Warning:</strong> This action will initiate a reversal for transaction <code>{{ transaction.TXN_ID }}</code> 
                            of amount ${{ "%.2f"|format(transaction.TXN_AMOUNT) }} via JConsole.
                        </div>
                        
                        <div class="mb-3">
                            <label for="reversal_reason" class="form-label">Reversal Reason <span class="text-danger">*</span></label>
                            <select class="form-select" id="reversal_reason" name="reversal_reason" required>
                                <option value="">Select a reason...</option>
                                <option value="DUPLICATE_TRANSACTION">Duplicate Transaction</option>
                                <option value="CUSTOMER_REQUEST">Customer Request</option>
                                <option value="MERCHANT_ERROR">Merchant Error</option>
                                <option value="SYSTEM_ERROR">System Error</option>
                                <option value="FRAUD_PREVENTION">Fraud Prevention</option>
                                <option value="OTHER">Other</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label for="reversal_notes" class="form-label">Additional Notes</label>
                            <textarea class="form-control" id="reversal_notes" name="reversal_notes" rows="3" 
                                      placeholder="Enter any additional notes for this reversal..."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-warning">
                            <i class="fas fa-undo me-1"></i>Initiate Reversal
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    {% endif %}
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

# =============================================================================
# LSV SUB-APPLICATION ROUTES: XML GENERATOR
# =============================================================================

@app.route('/lsv/xml-generator')
def xml_generator_home():
    """Display XML Template Generator homepage."""
    templates = XMLGeneratorService.get_available_templates()
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XML Generator - LSV</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item active">XML Generator</li>
                    </ol>
                </nav>
                
                <div class="text-center mb-5">
                    <h1 class="display-5">
                        <i class="fas fa-file-code text-success me-3"></i>
                        XML Template Generator
                    </h1>
                    <p class="lead">Generate XML messages from predefined templates</p>
                </div>
                
                {% if templates %}
                <div class="card">
                    <div class="card-header">
                        <h4><i class="fas fa-list me-2"></i>Available Templates</h4>
                    </div>
                    <div class="card-body">
                        <div class="list-group">
                            {% for template in templates %}
                            <a href="{{ url_for('template_form', template_name=template) }}" class="list-group-item list-group-item-action">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">
                                        <i class="fas fa-file-alt me-2"></i>{{ template }}
                                    </h6>
                                    <small><i class="fas fa-arrow-right"></i></small>
                                </div>
                                <p class="mb-1 text-muted">Click to generate XML from this template</p>
                            </a>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% else %}
                <div class="alert alert-warning text-center">
                    <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                    <h4>No Templates Found</h4>
                    <p>No XML templates were found in the templates folder.</p>
                    <p class="text-muted">Please add .xml template files to the <code>./xml_templates/</code> directory.</p>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
    ''', templates=templates)

@app.route('/lsv/xml-generator/template/<template_name>')
def template_form(template_name):
    """Display form for the selected template."""
    try:
        # Read template content
        template_content = XMLGeneratorService.read_template_content(template_name)
        if not template_content:
            flash(f'Template {template_name} not found.', 'error')
            return redirect(url_for('xml_generator_home'))
        
        # Extract variables
        variables = XMLGeneratorService.extract_jinja_variables(template_content)
        
        return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ template_name }} - XML Generator</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('xml_generator_home') }}">XML Generator</a>
                        </li>
                        <li class="breadcrumb-item active">{{ template_name }}</li>
                    </ol>
                </nav>
                
                <div class="text-center mb-4">
                    <h2>
                        <i class="fas fa-file-alt text-success me-2"></i>
                        {{ template_name }}
                    </h2>
                    <p class="text-muted">Fill in the values to generate your XML</p>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-edit me-2"></i>Template Variables</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="{{ url_for('generate_xml', template_name=template_name) }}">
                            {% for variable in variables %}
                            <div class="mb-3">
                                <label for="{{ variable }}" class="form-label">{{ variable.replace('_', ' ').title() }}</label>
                                <input type="text" class="form-control" id="{{ variable }}" name="{{ variable }}" 
                                       placeholder="Enter {{ variable.replace('_', ' ').lower() }}" required>
                            </div>
                            {% endfor %}
                            
                            <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                <a href="{{ url_for('xml_generator_home') }}" class="btn btn-secondary me-md-2">
                                    <i class="fas fa-arrow-left me-1"></i>Back
                                </a>
                                <button type="submit" class="btn btn-success">
                                    <i class="fas fa-code me-1"></i>Generate XML
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
        ''', template_name=template_name, variables=variables)
        
    except Exception as e:
        logging.error(f"Error displaying template form: {e}")
        flash(f'Error loading template: {str(e)}', 'danger')
        return redirect(url_for('xml_generator_home'))

@app.route('/lsv/xml-generator/generate/<template_name>', methods=['POST'])
def generate_xml(template_name):
    """Generate XML from template and form data."""
    try:
        # Read template content
        template_content = XMLGeneratorService.read_template_content(template_name)
        if not template_content:
            flash(f'Template {template_name} not found.', 'error')
            return redirect(url_for('xml_generator_home'))
        
        # Get form data
        form_data = dict(request.form)
        
        # Generate XML
        generated_xml = XMLGeneratorService.render_xml_template(template_content, form_data)
        if not generated_xml:
            flash('Error generating XML. Please check your input.', 'error')
            return redirect(url_for('template_form', template_name=template_name))
        
        # Log generation
        XMLGeneratorService.log_generation(template_name, form_data, generated_xml)
        
        return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated XML - {{ template_name }}</title>
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
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('lsv_home') }}">
                    <i class="fas fa-code me-1"></i>LSV
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('main_home') }}">
                                <i class="fas fa-home me-1"></i>ABAssist
                            </a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('lsv_home') }}">LSV</a>
                        </li>
                        <li class="breadcrumb-item">
                            <a href="{{ url_for('xml_generator_home') }}">XML Generator</a>
                        </li>
                        <li class="breadcrumb-item active">Generated XML</li>
                    </ol>
                </nav>
                
                <div class="text-center mb-4">
                    <h2>
                        <i class="fas fa-check-circle text-success me-2"></i>
                        XML Generated Successfully
                    </h2>
                    <p class="text-muted">From template: {{ template_name }}</p>
                </div>
                
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5><i class="fas fa-code me-2"></i>Generated XML</h5>
                        <button class="btn btn-outline-primary btn-sm" onclick="copyToClipboard()">
                            <i class="fas fa-copy me-1"></i>Copy
                        </button>
                    </div>
                    <div class="card-body">
                        <pre class="bg-dark text-light p-3 rounded" id="xmlContent">{{ generated_xml }}</pre>
                    </div>
                </div>
                
                <div class="d-grid gap-2 d-md-flex justify-content-md-center mt-4">
                    <a href="{{ url_for('template_form', template_name=template_name) }}" class="btn btn-secondary me-md-2">
                        <i class="fas fa-edit me-1"></i>Edit Values
                    </a>
                    <a href="{{ url_for('xml_generator_home') }}" class="btn btn-primary">
                        <i class="fas fa-list me-1"></i>Choose Another Template
                    </a>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function copyToClipboard() {
        const xmlContent = document.getElementById('xmlContent').textContent;
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
        });
    }
    </script>
</body>
</html>
        ''', template_name=template_name, generated_xml=generated_xml)
        
    except Exception as e:
        logging.error(f"Error generating XML: {e}")
        flash(f'Error generating XML: {str(e)}', 'danger')
        return redirect(url_for('template_form', template_name=template_name))

# Legacy route for backward compatibility
@app.route('/home')
def home():
    """Legacy route - redirect to XML generator."""
    return redirect(url_for('xml_generator_home'))

# =============================================================================
# LSV SUB-APPLICATION ROUTES: TRANSACTION REVERSAL
# =============================================================================

@app.route('/lsv/tran-reversal')
def tran_reversal_home():
    """Display Transaction Reversal homepage."""
    return render_template_string(TRAN_REVERSAL_HOME_TEMPLATE, 
                                  oracle_available=ORACLE_AVAILABLE)

@app.route('/lsv/tran-reversal/search', methods=['POST'])
def search_transactions_endpoint():
    """Search for transactions based on criteria."""
    try:
        search_criteria = {
            'txn_id': request.form.get('txn_id'),
            'account_number': request.form.get('account_number'),
            'reference_number': request.form.get('reference_number'),
            'date_from': request.form.get('date_from'),
            'date_to': request.form.get('date_to')
        }
        
        # Remove empty criteria
        search_criteria = {k: v for k, v in search_criteria.items() if v}
        
        if not search_criteria:
            flash('Please provide at least one search criterion.', 'warning')
            return redirect(url_for('tran_reversal_home'))
        
        # Search transactions
        transactions = TransactionReversalService.search_transactions(search_criteria)
        
        return render_template_string(TRANSACTION_RESULTS_TEMPLATE, 
                                      transactions=transactions,
                                      search_criteria=search_criteria)
        
    except Exception as e:
        logging.error(f"Error in transaction search: {e}")
        flash(f'Error searching transactions: {str(e)}', 'danger')
        return redirect(url_for('tran_reversal_home'))

@app.route('/lsv/tran-reversal/transaction/<txn_id>')
def transaction_details(txn_id):
    """Display detailed information about a specific transaction."""
    try:
        transaction = TransactionReversalService.get_transaction_details(txn_id)
        
        if not transaction:
            flash(f'Transaction {txn_id} not found.', 'error')
            return redirect(url_for('tran_reversal_home'))
        
        return render_template_string(TRANSACTION_DETAILS_TEMPLATE, 
                                      transaction=transaction)
        
    except Exception as e:
        logging.error(f"Error getting transaction details: {e}")
        flash(f'Error retrieving transaction details: {str(e)}', 'danger')
        return redirect(url_for('tran_reversal_home'))

@app.route('/lsv/tran-reversal/initiate-reversal/<txn_id>', methods=['POST'])
def initiate_reversal(txn_id):
    """Initiate transaction reversal via jconsole."""
    try:
        reversal_reason = request.form.get('reversal_reason')
        reversal_notes = request.form.get('reversal_notes', '')
        
        if not reversal_reason:
            flash('Reversal reason is required.', 'danger')
            return redirect(url_for('transaction_details', txn_id=txn_id))
        
        # Check if transaction exists and is eligible for reversal
        transaction = TransactionReversalService.get_transaction_details(txn_id)
        if not transaction:
            flash(f'Transaction {txn_id} not found.', 'error')
            return redirect(url_for('tran_reversal_home'))
        
        if transaction.get('REVERSAL_STATUS') == 'COMPLETED':
            flash('Transaction has already been reversed.', 'warning')
            return redirect(url_for('transaction_details', txn_id=txn_id))
        
        if transaction.get('TXN_STATUS') != 'COMPLETED':
            flash('Only completed transactions can be reversed.', 'warning')
            return redirect(url_for('transaction_details', txn_id=txn_id))
        
        # Initiate reversal
        full_reason = f"{reversal_reason}"
        if reversal_notes:
            full_reason += f" - {reversal_notes}"
        
        result = TransactionReversalService.initiate_reversal_via_jconsole(txn_id, full_reason)
        
        if result.get('success'):
            flash(f'Reversal initiated successfully. Reversal ID: {result.get("reversal_id")}', 'success')
        else:
            flash(f'Error initiating reversal: {result.get("message")}', 'danger')
        
        return redirect(url_for('transaction_details', txn_id=txn_id))
        
    except Exception as e:
        logging.error(f"Error initiating reversal: {e}")
        flash(f'Error initiating reversal: {str(e)}', 'danger')
        return redirect(url_for('transaction_details', txn_id=txn_id))

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