# XML Template Generator

## Overview

This is a Flask web application that generates XML messages from predefined templates using dynamic form creation and SQLite logging. The application scans XML template files containing Jinja2 placeholders, creates forms for user input, and generates populated XML messages while logging all activities to a database.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a simple monolithic architecture with the following layers:

### Frontend Architecture
- **Technology**: Server-side rendered HTML using Flask's render_template_string
- **Styling**: Bootstrap-based responsive design for clean UI
- **User Flow**: 
  1. Homepage displays available XML templates
  2. Template selection leads to dynamic form generation
  3. Form submission generates XML output with copy-to-clipboard functionality

### Backend Architecture
- **Framework**: Flask (Python micro-framework)
- **Structure**: Single-file application (app.py) containing all logic
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
├── app.py                 # Main application file
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