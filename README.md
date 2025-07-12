# ABAssist - Application Support Platform

A comprehensive Flask web application platform for Application Support and Reliability Engineers, featuring XML template generation, Oracle database transaction management, and modular sub-applications.

## Features

- **XML Template Generator**: Generate XML messages from predefined templates with dynamic placeholders
- **Transaction Reversal**: Oracle 19c database integration for transaction management and reversal via JConsole
- **Modular Architecture**: Organized sub-applications for future scalability
- **Bootstrap UI**: Professional responsive design with jumbotron styling
- **Activity Logging**: SQLite database logging for all XML generations

## Installation

### Prerequisites

- Python 3.8+
- Oracle Instant Client (for Oracle database functionality)
- Access to Oracle 19c database (for Transaction Reversal features)

### Setup

1. **Clone the repository and navigate to the project directory**

2. **Install dependencies**:
   ```bash
   pip install -r dependencies.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your actual configuration values:
   - `SESSION_SECRET`: Flask session secret key
   - `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME`: Oracle database connection details
   - `ORACLE_USERNAME`, `ORACLE_PASSWORD`: Oracle database credentials
   - `JCONSOLE_HOST`, `JCONSOLE_PORT`: JConsole connection details for transaction reversal

4. **Create XML templates directory**:
   ```bash
   mkdir xml_templates
   ```
   Add your XML template files (with .xml extension) to this directory.

5. **Run the application**:
   ```bash
   python main.py
   ```
   Or use the production server:
   ```bash
   gunicorn --bind 0.0.0.0:5000 --reload main:app
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSION_SECRET` | Flask session secret key | `dev-secret-key-change-in-production` |
| `FLASK_ENV` | Flask environment | `development` |
| `FLASK_DEBUG` | Flask debug mode | `True` |
| `DATABASE_URL` | SQLite database path | `sqlite:///actions.db` |
| `ORACLE_HOST` | Oracle database host | `localhost` |
| `ORACLE_PORT` | Oracle database port | `1521` |
| `ORACLE_SERVICE_NAME` | Oracle service name | `ORCLPDB1` |
| `ORACLE_USERNAME` | Oracle database username | `hr` |
| `ORACLE_PASSWORD` | Oracle database password | `password` |
| `XML_TEMPLATES_PATH` | XML templates directory | `./xml_templates` |
| `LOG_LEVEL` | Application log level | `INFO` |

### XML Templates

1. Create XML template files in the `xml_templates` directory
2. Use Jinja2 template syntax for dynamic placeholders: `{{ variable_name }}`
3. The application will automatically scan and list available templates

Example XML template:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<message>
    <header>
        <messageId>{{ message_id }}</messageId>
        <timestamp>{{ timestamp }}</timestamp>
    </header>
    <body>
        <customerName>{{ customer_name }}</customerName>
        <amount>{{ amount }}</amount>
    </body>
</message>
```

## Usage

### XML Template Generator

1. Navigate to **LSV Tools** → **XML Generator**
2. Select a template from the available list
3. Fill in the required variables in the form
4. Click "Generate XML" to create the XML message
5. Copy the generated XML using the "Copy" button

### Transaction Reversal

1. Navigate to **LSV Tools** → **Transaction Reversal**
2. Enter search criteria (Transaction ID, Account Number, etc.)
3. Search for transactions in the Oracle database
4. Select a transaction to view details
5. Initiate reversal through JConsole integration

## Architecture

### Project Structure

```
.
├── app.py                 # Main application and homepage
├── lsv.py                # LSV sub-application (XML Generator & Transaction Reversal)
├── future_app.py         # Template for future sub-applications
├── main.py               # Application entry point
├── .env                  # Environment configuration
├── dependencies.txt      # Python dependencies
├── actions.db            # SQLite database (auto-created)
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── main_home.html    # Main homepage
│   ├── lsv/              # LSV sub-application templates
│   └── future_app/       # Future sub-application templates
└── xml_templates/        # XML template files
```

### Sub-Applications

- **LSV (Log, Script, Validation)**: XML generation and transaction reversal tools
- **Future App**: Placeholder for additional sub-applications

## Development

### Adding New Sub-Applications

1. Create a new Python file (e.g., `new_app.py`)
2. Define a Blueprint following the pattern in `lsv.py`
3. Register the blueprint in `app.py`
4. Create templates in `templates/new_app/`
5. Update navigation in `base.html`

### Adding New XML Templates

1. Create XML files in `xml_templates/` directory
2. Use Jinja2 syntax for dynamic variables: `{{ variable_name }}`
3. Templates are automatically discovered and listed

## Security

- Configure `SESSION_SECRET` for production deployment
- Use environment variables for sensitive credentials
- Oracle credentials are loaded from environment variables
- No authentication is implemented (suitable for internal/engineering use)

## Logging

- All XML generations are logged to SQLite database
- Application logs are configured at DEBUG level
- Database operations are logged for troubleshooting

## Production Deployment

1. Set `FLASK_ENV=production` in `.env`
2. Configure a strong `SESSION_SECRET`
3. Use a production WSGI server like Gunicorn
4. Configure proper Oracle database connections
5. Set up proper logging and monitoring

## License

This project is for internal use by Application Support and Reliability Engineering teams.