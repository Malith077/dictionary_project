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

<!-- WHISPER_CELERY_DOC_V1 -->

## Transcription Service (YouTube & Whisper)

This project uses OpenAI's Whisper model (via the `openai-whisper` package) to transcribe audio from YouTube videos. This process is handled asynchronously using Celery with Redis as a message broker.

### New Dependencies

The following Python packages have been added for this functionality:
-   `openai-whisper`: For audio transcription.
-   `yt-dlp`: For downloading audio/video from YouTube.
-   `pydub`: For audio file manipulation (if needed).
-   `celery`: For distributed task queuing.
-   `redis`: Python client for Redis, used as the Celery broker.

Ensure these are installed (they are listed in `requirements.txt`).

### Prerequisites

1.  **Redis Server**:
    -   A Redis server must be running and accessible. By default, the application and Celery expect Redis at `redis://localhost:6379/0`.
    -   You can configure the Redis URL via the `CELERY_BROKER_URL` environment variable.

2.  **FFmpeg**:
    -   `yt-dlp` requires FFmpeg to be installed on the system for audio extraction and conversion (e.g., to MP3). Make sure `ffmpeg` is in your system's PATH.

3.  **Whisper Model Download**:
    -   The first time a Celery worker starts a transcription task, the `openai-whisper` library will download the specified model files (currently configured for the "base" model). This may take some time and requires internet access for the worker.

### Running Celery Workers

To process transcription tasks, you need to run one or more Celery workers. Start a worker from the project root directory using:

```bash
celery -A celery_app.app worker -l info
# For environments where gevent is used (like our Flask dev server for WebSockets):
# celery -A celery_app.app worker -l info -P gevent
```
*(Adjust `-P gevent` based on your Celery worker's concurrency needs and environment. For CPU-bound tasks like Whisper, the default prefork pool (`-P prefork`, which is the default) is often suitable.)*

### Updated GraphQL `Session` Type

The `Session` type in GraphQL now includes the following additional fields related to YouTube transcription:

-   `youtubeUrl: String`: The URL of the YouTube video associated with the session.
-   `transcriptionStatus: String`: The current status of the transcription job (e.g., "pending", "processing", "completed", "failed").
-   `fullTranscriptText: String`: The full transcribed text of the video audio, available once the status is "completed".

**Example Query:**
```graphql
query GetSessionWithTranscription($id: ID!) {
  session(id: $id) {
    id
    title
    youtubeUrl
    transcriptionStatus
    fullTranscriptText
    createdAt
    source
  }
}
```
