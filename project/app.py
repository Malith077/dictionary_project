from flask import Flask, request, jsonify # Ensure request and jsonify are imported
from flask_graphql import GraphQLView
from .schema import schema
from .db import get_db

def create_app():
    app = Flask(__name__)

    try:
        db_instance = get_db()
        print(f"MongoDB connection initialized for Flask app, database: {db_instance.name}")
    except Exception as e:
        print(f"CRITICAL: Failed to connect to MongoDB during Flask app initialization: {e}")
        raise

    app.add_url_rule(
        '/graphql',
        view_func=GraphQLView.as_view(
            'graphql',
            schema=schema,
            graphiql=True
        )
    )

    # New YouTube Link Endpoint
    @app.route('/api/youtube-link', methods=['POST'])
    def submit_youtube_link():
        if not request.is_json:
            # Use app.logger for logging in Flask context if preferred
            print("Malformed request: /api/youtube-link expects JSON")
            return jsonify({"status": "error", "message": "Request must be JSON"}), 400

        data = request.get_json()
        youtube_url = data.get('youtube_url')
        enhance_options = data.get('enhance_options', [])

        if not youtube_url:
            print("Malformed request: /api/youtube-link missing 'youtube_url'")
            return jsonify({"status": "error", "message": "Missing 'youtube_url' in request body"}), 400

        print(f"Received YouTube link: {youtube_url}")
        if enhance_options:
            print(f"Enhance options: {enhance_options}")

        return jsonify({
            "status": "success",
            "message": "YouTube link received",
            "submitted_url": youtube_url,
            "processed_options": enhance_options
        }), 200

    return app
