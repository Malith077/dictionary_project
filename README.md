# Project README

## MongoDB Setup

This project uses MongoDB as its database.

**Configuration:**
-   **`MONGODB_URI`**: The MongoDB connection string.
    -   Defaults to: `mongodb://localhost:27017/`
-   **`DATABASE_NAME`**: The name of the database to use.
    -   Defaults to: `graphql_phasethree_db` (for application)
    -   For tests, it uses: `graphql_phasethree_test_db` (this is set via `os.environ` in `tests/conftest.py`)

Ensure your MongoDB instance is running and accessible. You can set these environment variables to point to your MongoDB instance and desired database name.

### MongoDB Document Schemas

The expected structure for documents within each MongoDB collection is defined using Pydantic models in `project/mongodb_schemas.py`. These models serve as the application-level schema and provide clarity on field names, types, and required fields.
