import os
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

# Default values if environment variables are not set
MONGODB_URI_DEFAULT = "mongodb://localhost:27017/"
DATABASE_NAME_DEFAULT = "graphql_phasethree_db"

# Get MongoDB URI and Database Name from environment variables or use defaults
MONGODB_URI = os.environ.get("MONGODB_URI", MONGODB_URI_DEFAULT)
DATABASE_NAME = os.environ.get("DATABASE_NAME", DATABASE_NAME_DEFAULT)

# Global MongoClient instance
# MongoClient is thread-safe and designed to be instantiated once per process
_client = None

def get_db() -> Database:
    """
    Returns the MongoDB database instance.
    Initializes the MongoClient if it hasn't been already.
    """
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGODB_URI)
            # Optional: Ping the server to confirm connection.
            # _client.admin.command('ping')
            print(f"Successfully connected to MongoDB at {MONGODB_URI}, database: {DATABASE_NAME}")
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            # Depending on the application's needs, you might raise the error
            # or handle it by returning None or a mock DB for resilience.
            raise

    return _client[DATABASE_NAME]

def get_collection(collection_name: str) -> Collection:
    """
    Returns a specific collection from the database.
    """
    db = get_db()
    return db[collection_name]

# Example of how to use it (optional, for direct testing of this file)
if __name__ == "__main__":
    try:
        print(f"Attempting to connect to MongoDB: {MONGODB_URI}, DB: {DATABASE_NAME}")
        db_instance = get_db()
        print(f"Database instance obtained: {db_instance}")
        print(f"Database name: {db_instance.name}")

        # Example: Get a 'test_connection_collection'
        test_collection = get_collection("test_connection_collection")
        print(f"Test collection object: {test_collection}")

        # Example: Insert a document (requires MongoDB server to be running)
        print("Attempting to insert a test document...")
        insert_result = test_collection.insert_one({"name": "Test Connection Document", "value": 12345})
        print(f"Inserted a test document with id: {insert_result.inserted_id}")

        # Example: Find a document
        print(f"Attempting to find the test document with id: {insert_result.inserted_id}")
        doc = test_collection.find_one({"_id": insert_result.inserted_id})
        print(f"Found document: {doc}")

        # Example: Delete the test document
        print(f"Attempting to delete the test document with id: {insert_result.inserted_id}")
        delete_result = test_collection.delete_one({"_id": insert_result.inserted_id})
        print(f"Deleted {delete_result.deleted_count} document(s).")

    except Exception as e:
        print(f"An error occurred during db.py standalone test: {e}")
        print("Please ensure MongoDB is running and accessible at the configured MONGODB_URI.")
