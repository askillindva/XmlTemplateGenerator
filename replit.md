# ABAssist - Application Support Platform

## Overview

ABAssist is a Flask web application platform that serves as a comprehensive toolkit for Application Support and Reliability Engineers. The platform includes sub-applications organized by functionality, with LSV (Log, Script & Validation) as the primary sub-application containing the XML Template Generator and other support tools.

## User Preferences

Preferred communication style: Simple, everyday language.
Code organization: Very organized code structure with independent sub-applications for future scalability. Each sub-application should be in separate files (lsv.py, future_app.py) for easy management.
HTML organization: Well-organized HTML templates for easy navigation and management.

## System Architecture

The application follows a modular monolithic architecture with a main platform and organized sub-applications:

### Main Platform Architecture
- **ABAssist Homepage**: Main entry point displaying available sub-applications
- **Navigation Structure**: Hierarchical navigation with breadcrumbs
  - ABAssist (Main) → LSV (Sub-app) → XML Generator (Tool)
- **Sub-Application Framework**: Modular design allowing future expansion

### LSV Sub-Application Architecture
- **LSV Dashboard**: Tool selection interface for log/script/validation utilities
- **XML Template Generator**: Core functionality for XML message generation
- **Transaction Reversal**: Oracle 19c database integration for transaction management and reversal via JConsole
- **Future Tools**: Placeholders for Script Runner and Validator

### Frontend Architecture
- **Technology**: Server-side rendered HTML using Flask's render_template_string
- **Styling**: Bootstrap-based responsive design with consistent navigation
- **User Flow**: 
  1. ABAssist homepage displays sub-applications
  2. LSV homepage shows available tools
  3. XML Generator displays available templates
  4. Template selection leads to dynamic form generation
  5. Form submission generates XML output with copy-to-clipboard functionality

### Backend Architecture
- **Framework**: Flask (Python micro-framework) with Blueprint pattern
- **Structure**: Modular architecture with separate files for each sub-application
  - `app.py`: Main application and homepage routes only
  - `lsv.py`: Complete LSV sub-application (XML Generator and Transaction Reversal)
  - `future_app.py`: Template for future sub-applications
- **Code Organization**: Service classes within each sub-application file for better maintainability
- **Blueprint Registration**: Each sub-application registered as Flask Blueprint for independent management
- **Route Structure**: Hierarchical URLs matching navigation structure:
  - `/` - ABAssist main homepage
  - `/lsv` - LSV sub-application homepage  
  - `/lsv/xml-generator` - XML Template Generator tool
  - `/lsv/xml-generator/template/<name>` - Template form pages
  - `/lsv/xml-generator/generate/<name>` - XML generation endpoints
  - `/lsv/tran-reversal` - Transaction Reversal tool
  - `/lsv/tran-reversal/search` - Transaction search endpoint
  - `/lsv/tran-reversal/transaction/<id>` - Transaction details pages
  - `/lsv/tran-reversal/initiate-reversal/<id>` - Reversal initiation endpoint
- **Template Processing**: Jinja2 template engine for XML generation
- **Pattern Matching**: Regular expressions to extract placeholders from XML templates

### Data Storage
- **Database**: SQLite (file-based, no external dependencies)
- **Schema**: Single `logs` table tracking generation activities
- **File Storage**: XML templates stored in `./xml_templates/` directory

## Key Components

### Template Scanner
- Scans `./xml_templates/` folder for .xml files
- Returns list of available templates for homepage display

### Dynamic Form Generator
- Parses XML templates to extract Jinja2 placeholders ({{ variable_name }} pattern)
- Creates HTML forms with text inputs for each unique placeholder
- Uses placeholder names as form field labels

### XML Generator
- Renders XML templates using Jinja2 with user-submitted data
- Displays generated XML with copy-to-clipboard functionality

### Database Logger
- Logs every successful XML generation with:
  - Timestamp (UTC)
  - Template name
  - User input data (JSON format)
  - Generated XML content

## Data Flow

1. **Template Discovery**: Application scans templates folder on startup
2. **User Selection**: User chooses template from homepage list
3. **Form Generation**: System extracts placeholders and creates input form
4. **Data Submission**: User fills form and submits data
5. **XML Generation**: Template rendered with user data using Jinja2
6. **Database Logging**: Activity logged to SQLite database
7. **Result Display**: Generated XML shown with copy functionality

## External Dependencies

### Required Python Packages
- **Flask**: Web framework for routing and templating
- **sqlite3**: Built-in Python module for database operations
- **cx_Oracle**: Oracle database connectivity for transaction management
- **requests**: HTTP library for external service calls
- **subprocess**: For JConsole integration
- **jinja2**: Template engine for XML generation
- **os, json, re, logging, datetime**: Standard library modules

### Template Requirements
- XML files must contain Jinja2-style placeholders: `{{ variable_name }}`
- Templates stored in `./xml_templates/` directory
- Files must have .xml extension

## Deployment Strategy

### Development Setup
- Single-file application structure for simplicity
- Built-in Flask development server
- SQLite database auto-creation on first run
- Environment variable support for session secret

### Database Schema
```sql
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    template_name TEXT NOT NULL,
    submitted_data TEXT NOT NULL,
    generated_xml TEXT NOT NULL
)
```

### File Structure
```
.
├── app.py                 # Main application and homepage only
├── lsv.py                # LSV sub-application (XML Generator & Transaction Reversal)
├── future_app.py         # Template for future sub-applications
├── actions.db            # SQLite database (auto-created)
└── xml_templates/        # Template directory
    ├── template1.xml
    └── template2.xml
```

### Security Considerations
- Session secret key configurable via environment variable
- No user authentication implemented (suitable for internal/engineering use)
- Basic input validation through form processing

This architecture prioritizes simplicity and ease of deployment while providing all required functionality for XML template generation and activity logging.