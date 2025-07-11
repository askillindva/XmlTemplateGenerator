# XML Template Generator

A Flask web application that generates XML messages from predefined templates with dynamic form creation and SQLite logging.

## Features

- **Template Scanning**: Automatically scans `./xml_templates/` folder for XML template files
- **Dynamic Form Generation**: Creates web forms based on Jinja2 placeholders found in XML templates
- **XML Generation**: Renders XML templates with user-provided data
- **Database Logging**: Logs all generation activities to SQLite database with timestamps
- **Copy to Clipboard**: Easy copying of generated XML content
- **Clean UI**: Bootstrap-based responsive design suitable for engineering workflows

## Directory Structure

