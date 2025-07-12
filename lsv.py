import os
import sqlite3
import json
import re
import logging
import subprocess
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
try:
    import cx_Oracle
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False
    logging.warning("cx_Oracle not available. Oracle functionality will be disabled.")

# =============================================================================
# LSV BLUEPRINT CONFIGURATION
# =============================================================================

lsv_bp = Blueprint('lsv', __name__, url_prefix='/lsv')

# Database configuration
DATABASE_PATH = 'actions.db'
TEMPLATES_FOLDER = './xml_templates/'

# =============================================================================
# LSV SUB-APPLICATION: XML TEMPLATE GENERATOR SERVICE
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
# LSV SUB-APPLICATION: TRANSACTION REVERSAL SERVICE
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



# =============================================================================
# LSV BLUEPRINT ROUTES
# =============================================================================

@lsv_bp.route('/')
def home():
    """Display LSV sub-application homepage."""
    return render_template('lsv/home.html')

# XML Generator Routes
@lsv_bp.route('/xml-generator')
def xml_generator_home():
    """Display XML Template Generator homepage."""
    templates = XMLGeneratorService.get_available_templates()
    return render_template('lsv/xml_generator_home.html', templates=templates)

@lsv_bp.route('/xml-generator/template/<template_name>')
def template_form(template_name):
    """Display form for the selected template."""
    try:
        # Read template content
        template_content = XMLGeneratorService.read_template_content(template_name)
        if not template_content:
            flash(f'Template {template_name} not found.', 'error')
            return redirect(url_for('lsv.xml_generator_home'))
        
        # Extract variables
        variables = XMLGeneratorService.extract_jinja_variables(template_content)
        
        return render_template('lsv/template_form.html', 
                               template_name=template_name, 
                               variables=variables)
        
    except Exception as e:
        logging.error(f"Error displaying template form: {e}")
        flash(f'Error loading template: {str(e)}', 'danger')
        return redirect(url_for('lsv.xml_generator_home'))

@lsv_bp.route('/xml-generator/generate/<template_name>', methods=['POST'])
def generate_xml(template_name):
    """Generate XML from template and form data."""
    try:
        # Read template content
        template_content = XMLGeneratorService.read_template_content(template_name)
        if not template_content:
            flash(f'Template {template_name} not found.', 'error')
            return redirect(url_for('lsv.xml_generator_home'))
        
        # Get form data
        form_data = dict(request.form)
        
        # Generate XML
        generated_xml = XMLGeneratorService.render_xml_template(template_content, form_data)
        if not generated_xml:
            flash('Error generating XML. Please check your input.', 'error')
            return redirect(url_for('lsv.template_form', template_name=template_name))
        
        # Log generation
        XMLGeneratorService.log_generation(template_name, form_data, generated_xml)
        
        return render_template('lsv/xml_generated.html', 
                               template_name=template_name, 
                               generated_xml=generated_xml)
        
    except Exception as e:
        logging.error(f"Error generating XML: {e}")
        flash(f'Error generating XML: {str(e)}', 'danger')
        return redirect(url_for('lsv.template_form', template_name=template_name))

# Transaction Reversal Routes
@lsv_bp.route('/tran-reversal')
def tran_reversal_home():
    """Display Transaction Reversal homepage."""
    return render_template('lsv/tran_reversal_home.html', 
                           oracle_available=ORACLE_AVAILABLE)

@lsv_bp.route('/tran-reversal/search', methods=['POST'])
def search_transactions():
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
            return redirect(url_for('lsv.tran_reversal_home'))
        
        # Search transactions
        transactions = TransactionReversalService.search_transactions(search_criteria)
        
        # For now, returning simplified template - full template would be implemented
        return f"<h2>Found {len(transactions)} transactions</h2><p><a href='{url_for('lsv.tran_reversal_home')}'>Back to Search</a></p>"
        
    except Exception as e:
        logging.error(f"Error in transaction search: {e}")
        flash(f'Error searching transactions: {str(e)}', 'danger')
        return redirect(url_for('lsv.tran_reversal_home'))

@lsv_bp.route('/tran-reversal/transaction/<txn_id>')
def transaction_details(txn_id):
    """Display detailed information about a specific transaction."""
    try:
        transaction = TransactionReversalService.get_transaction_details(txn_id)
        
        if not transaction:
            flash(f'Transaction {txn_id} not found.', 'error')
            return redirect(url_for('lsv.tran_reversal_home'))
        
        # For now, returning simplified template - full template would be implemented
        return f"<h2>Transaction Details: {txn_id}</h2><p><a href='{url_for('lsv.tran_reversal_home')}'>Back to Search</a></p>"
        
    except Exception as e:
        logging.error(f"Error getting transaction details: {e}")
        flash(f'Error retrieving transaction details: {str(e)}', 'danger')
        return redirect(url_for('lsv.tran_reversal_home'))

@lsv_bp.route('/tran-reversal/initiate-reversal/<txn_id>', methods=['POST'])
def initiate_reversal(txn_id):
    """Initiate transaction reversal via jconsole."""
    try:
        reversal_reason = request.form.get('reversal_reason')
        reversal_notes = request.form.get('reversal_notes', '')
        
        if not reversal_reason:
            flash('Reversal reason is required.', 'danger')
            return redirect(url_for('lsv.transaction_details', txn_id=txn_id))
        
        # Check if transaction exists and is eligible for reversal
        transaction = TransactionReversalService.get_transaction_details(txn_id)
        if not transaction:
            flash(f'Transaction {txn_id} not found.', 'error')
            return redirect(url_for('lsv.tran_reversal_home'))
        
        if transaction.get('REVERSAL_STATUS') == 'COMPLETED':
            flash('Transaction has already been reversed.', 'warning')
            return redirect(url_for('lsv.transaction_details', txn_id=txn_id))
        
        if transaction.get('TXN_STATUS') != 'COMPLETED':
            flash('Only completed transactions can be reversed.', 'warning')
            return redirect(url_for('lsv.transaction_details', txn_id=txn_id))
        
        # Initiate reversal
        full_reason = f"{reversal_reason}"
        if reversal_notes:
            full_reason += f" - {reversal_notes}"
        
        result = TransactionReversalService.initiate_reversal_via_jconsole(txn_id, full_reason)
        
        if result.get('success'):
            flash(f'Reversal initiated successfully. Reversal ID: {result.get("reversal_id")}', 'success')
        else:
            flash(f'Error initiating reversal: {result.get("message")}', 'danger')
        
        return redirect(url_for('lsv.transaction_details', txn_id=txn_id))
        
    except Exception as e:
        logging.error(f"Error initiating reversal: {e}")
        flash(f'Error initiating reversal: {str(e)}', 'danger')
        return redirect(url_for('lsv.transaction_details', txn_id=txn_id))

# Legacy route for backward compatibility
@lsv_bp.route('/home')
def legacy_home():
    """Legacy route - redirect to XML generator."""
    return redirect(url_for('lsv.xml_generator_home'))