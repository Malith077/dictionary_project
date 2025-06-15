import pytest
import os
from pymongo import MongoClient
from datetime import datetime
from project.app import create_app

# Use a different database for testing
TEST_DATABASE_NAME = "graphql_phasethree_test_db"
os.environ["DATABASE_NAME"] = TEST_DATABASE_NAME

# Sample data for testing
SESSIONS_TEST_DATA = {
    "s1": {"id": "s1", "title": "Test Session 1", "source": "youtube", "createdAt": datetime.utcnow(), "transcript_ids": ["t1_s1", "t2_s1"], "keyword_ids": ["k1_s1"], "summary": "Summary for S1."},
    "s2": {"id": "s2", "title": "Test Session 2", "source": "mic", "createdAt": datetime.utcnow(), "transcript_ids": ["t1_s2"], "keyword_ids": ["k1_s2", "k2_s2"], "summary": "Summary for S2."}
}

TRANSCRIPT_CHUNKS_TEST_DATA = {
    "t1_s1": {"id": "t1_s1", "session_id": "s1", "content": "First chunk of S1.", "keywordSpans": [{"id": "ks1_t1_s1", "keyword_id": "k1_s1", "startIndex": 0, "endIndex": 5}]},
    "t2_s1": {"id": "t2_s1", "session_id": "s1", "content": "Second chunk of S1.", "keywordSpans": []},
    "t1_s2": {"id": "t1_s2", "session_id": "s2", "content": "First chunk of S2.", "keywordSpans": [{"id": "ks1_t1_s2", "keyword_id": "k1_s2", "startIndex": 10, "endIndex": 15}]}
}

KEYWORDS_TEST_DATA = {
    "k1_s1": {"id": "k1_s1", "slug": "keyword-one-s1", "term": "Keyword One S1", "session_id": "s1", "definition_ids": ["d1_k1_s1"]},
    "k1_s2": {"id": "k1_s2", "slug": "keyword-one-s2", "term": "Keyword One S2", "session_id": "s2", "definition_ids": []},
    "k2_s2": {"id": "k2_s2", "slug": "keyword-two-s2", "term": "Keyword Two S2", "session_id": "s2", "definition_ids": ["d1_k2_s2"]}
}

DEFINITIONS_TEST_DATA = {
    "d1_k1_s1": {"id": "d1_k1_s1", "keyword_id": "k1_s1", "contextSummary": "Context S1K1", "definitionText": "Def for K1S1.", "createdAt": datetime.utcnow(), "modelUsed": "test-model"},
    "d1_k2_s2": {"id": "d1_k2_s2", "keyword_id": "k2_s2", "contextSummary": "Context S2K2", "definitionText": "Def for K2S2.", "createdAt": datetime.utcnow(), "modelUsed": "test-model"}
}

@pytest.fixture(scope="session")
def db_connection_string():
    return os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")

@pytest.fixture(scope="session")
def mongo_client_session(db_connection_string): # Renamed to avoid conflict if 'mongo_client' is used elsewhere
    client = MongoClient(db_connection_string)
    try:
        client.admin.command('ping')
        print(f"Successfully connected to MongoDB for test session: {db_connection_string}")
    except Exception as e:
        print(f"Failed to connect to MongoDB for test session: {e}")
        pytest.exit(f"MongoDB connection failed: {e}", 1)
    yield client
    # Clean up the test database after the session
    print(f"Dropping test database: {TEST_DATABASE_NAME}")
    client.drop_database(TEST_DATABASE_NAME)
    client.close()
    print("MongoDB test session client closed and database dropped.")

@pytest.fixture(scope="function")
def db(mongo_client_session): # Depends on the session-scoped client
    db_instance = mongo_client_session[TEST_DATABASE_NAME]

    collections_data = {
        "sessions": SESSIONS_TEST_DATA,
        "transcriptChunks": TRANSCRIPT_CHUNKS_TEST_DATA,
        "keywords": KEYWORDS_TEST_DATA,
        "definitions": DEFINITIONS_TEST_DATA,
    }

    for name, data_map in collections_data.items():
        collection = db_instance[name]
        collection.delete_many({}) # Clear collection before inserting new data for the test
        if data_map:
            documents = list(data_map.values())
            if documents:
                collection.insert_many(documents)

    yield db_instance

@pytest.fixture
def client(db): # client fixture depends on db fixture
    # Ensures os.environ["DATABASE_NAME"] is set by conftest.py before create_app()
    app = create_app()
    if not app.config.get('TESTING'):
        app.config['TESTING'] = True

    with app.test_client() as flask_test_client:
        yield flask_test_client
