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

### GraphQL Word Search Endpoint

To search for keywords, you can use the existing GraphQL endpoint (`/graphql`) with the `searchKeyword` query.

**Query:** `searchKeyword(term: String!)`
-   `term`: The string you want to search for. The search is case-insensitive and matches partial terms.

**Example Usage:**

Send a `POST` request to `/graphql` with a JSON body like the following:

```json
{
  "query": "query SearchKeywords($term: String!) { searchKeyword(term: $term) { id slug term session { id title } } }",
  "variables": {
    "term": "your search term"
  }
}
```

**Example with cURL:**

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{ "query": "query SearchKeywords($term: String!) { searchKeyword(term: $term) { id slug term session { id title } } }", "variables": { "term": "example" } }' \
     http://localhost:3002/graphql
```
*(Note: Replace `http://localhost:3002` with your actual server address if different.)*

**Example Response:**

The response will be a JSON object containing the search results:

```json
{
  "data": {
    "searchKeyword": [
      {
        "id": "k1_s1",
        "slug": "keyword-one-s1",
        "term": "Keyword One S1",
        "session": {
          "id": "s1",
          "title": "Test Session 1"
        }
      }
      // ... other matching keywords
    ]
  }
}
```
This query will return a list of `Keyword` objects that match the search term, including their `id`, `slug`, `term`, and associated `session` details.

<!-- NEW_ENDPOINTS_DOC_V1 -->
## API Endpoints

### Submit YouTube Link

-   **URL**: `/api/youtube-link`
-   **Method**: `POST`
-   **Content-Type**: `application/json`
-   **Request Body Example**:
    ```json
    {
      "youtube_url": "https://www.youtube.com/watch?v=your_video_id",
      "enhance_options": ["transcript", "summary"]
    }
    ```
    -   `youtube_url` (string, required): The URL of the YouTube video.
    -   `enhance_options` (array of strings, optional): Future options for processing (e.g., "transcript", "summary").
-   **Success Response (200 OK)**:
    ```json
    {
      "status": "success",
      "message": "YouTube link received",
      "submitted_url": "https://www.youtube.com/watch?v=your_video_id",
      "processed_options": ["transcript", "summary"]
    }
    ```
-   **Error Responses**:
    -   `400 Bad Request`: If the request is not JSON or if `youtube_url` is missing.
      ```json
      {
        "status": "error",
        "message": "Request must be JSON"
      }
      ```
      ```json
      {
        "status": "error",
        "message": "Missing 'youtube_url' in request body"
      }
      ```

### Microphone Data Stream (WebSocket)

-   **URL**: `ws://<your_server_address>/api/mic-stream`
    -   *(Example: `ws://localhost:3002/api/mic-stream` when running locally)*
-   **Protocol**: WebSocket
-   **Functionality**: Allows streaming of audio data from a client (e.g., microphone input from a frontend) to the server.
-   **Client to Server Messages**:
    -   The client should send audio data as binary messages.
-   **Server to Client Messages**:
    -   The server does not send acknowledgments for each received audio chunk.
    -   The server will only send a message if an error occurs during processing on the server side (this error handling is minimal in the current mock implementation).
-   **Behavior**:
    -   The server logs when a client connects and disconnects.
    -   The server logs the size of each received audio chunk.
    -   This is currently a mock endpoint; it logs received data but does not perform any actual audio processing or storage.
