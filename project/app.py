from flask import Flask
from flask_graphql import GraphQLView
from .schema import schema
from .db import get_db # Import get_db

def create_app():
    app = Flask(__name__)

    # Explicitly initialize DB connection on app creation
    try:
        db_instance = get_db()
        # Optional: Could add a specific ping here if get_db() doesn't do it robustly enough for startup.
        # For now, get_db() prints connection status or raises an error.
        print(f"MongoDB connection initialized for Flask app, database: {db_instance.name}")
    except Exception as e:
        # This block will be hit if get_db() raises an exception (e.g., MongoDB is down)
        print(f"CRITICAL: Failed to connect to MongoDB during Flask app initialization: {e}")
        # Re-raise the exception to prevent the app from starting if DB is essential
        raise

    app.add_url_rule(
        '/graphql',
        view_func=GraphQLView.as_view(
            'graphql',
            schema=schema,
            graphiql=True
        )
    )
    return app
