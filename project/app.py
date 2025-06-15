from flask import Flask, request, jsonify # Keep jsonify if other parts of app.py might use it, or remove if not.
                                        # For now, routes.py uses it.
from flask_graphql import GraphQLView
from .schema import schema
from .db import get_db
from .routes import api_bp # Import the Blueprint

def create_app():
    app = Flask(__name__)

    try:
        db_instance = get_db()
        print(f"MongoDB connection initialized for Flask app, database: {db_instance.name}")
    except Exception as e:
        print(f"CRITICAL: Failed to connect to MongoDB during Flask app initialization: {e}")
        raise

    # Register GraphQL endpoint
    app.add_url_rule(
        '/graphql',
        view_func=GraphQLView.as_view(
            'graphql',
            schema=schema,
            graphiql=True
        )
    )

    # Register the Blueprint for other API routes (e.g., /api/youtube-link)
    app.register_blueprint(api_bp)

    # The old @app.route('/api/youtube-link'...) definition that was here
    # has been removed as it's now in routes.py under the api_bp Blueprint.

    return app
