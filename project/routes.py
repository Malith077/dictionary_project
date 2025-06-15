# project/routes.py
from flask import Blueprint, request, jsonify
from project.services import youtube_service # Import the specific service

# Create a Blueprint for API routes
# The first argument is the Blueprint's name, the second is its import name (usually __name__)
# url_prefix can be used if all routes in this blueprint should share a common path prefix
api_bp = Blueprint('api_bp', __name__, url_prefix='/api')

@api_bp.route('/youtube-link', methods=['POST'])
def submit_youtube_link_route(): # Renamed function to avoid conflict if imported directly
    if not request.is_json:
        # Using current_app.logger for logging within application context might be better
        # For now, print is fine for mock.
        print("Malformed request: /api/youtube-link expects JSON")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    youtube_url = data.get('youtube_url')
    enhance_options = data.get('enhance_options', [])

    if not youtube_url:
        print("Malformed request: /api/youtube-link missing 'youtube_url'")
        return jsonify({"status": "error", "message": "Missing 'youtube_url' in request body"}), 400

    # Call the service function to handle the logic
    service_response_data = youtube_service.handle_youtube_link(
        youtube_url=youtube_url,
        enhance_options=enhance_options
    )

    # The service function already prepares the response dictionary
    return jsonify(service_response_data), 200

# Add other HTTP routes here in the future if needed
