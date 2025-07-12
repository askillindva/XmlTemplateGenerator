from flask import Blueprint, render_template

# =============================================================================
# FUTURE SUB-APPLICATION BLUEPRINT
# =============================================================================

future_app_bp = Blueprint('future_app', __name__, url_prefix='/future-app')



# =============================================================================
# FUTURE SUB-APPLICATION ROUTES
# =============================================================================

@future_app_bp.route('/')
def home():
    """Display Future App homepage."""
    return render_template('future_app/home.html')

# Additional routes for future functionality can be added here
# Example:
# @future_app_bp.route('/tool1')
# def tool1():
#     """Future tool 1."""
#     pass