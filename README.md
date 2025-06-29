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

<!-- PHASE2_NLP_DOC_V1 -->

## Phase 2: NLP & Keyword Processing

This phase enhances the application by adding Natural Language Processing (NLP) capabilities to transcribed sessions. It involves extracting keywords, generating sentence/chunk embeddings, and storing these in a vector database (ChromaDB) for future semantic search. This processing is handled asynchronously via Celery tasks.

### New Dependencies (Phase 2)

The following Python packages are introduced for NLP functionalities:
-   `keybert`: For keyword extraction using BERT embeddings.
-   `sentence-transformers`: For generating dense vector embeddings for text (used by KeyBERT and for transcript chunks).
-   `chromadb`: Vector database for storing and searching text embeddings. The project uses a persistent client, storing data locally.
-   `nltk`: Natural Language Toolkit, used for tasks like sentence tokenization if Whisper's output segments need further breakdown (though Whisper segments are often used directly as chunks).

Ensure these are installed (they are listed in `requirements.txt`). Note that `sentence-transformers` and `keybert` may download pre-trained models on first use, requiring internet access for the Celery workers.

### ChromaDB Setup

-   **Storage**: ChromaDB is configured to use a persistent local directory for storing embeddings. By default, this is `./chroma_db_store` in the project root. This path can be configured via the `CHROMA_DB_PATH` environment variable.
-   **Collection**: Embeddings for transcript chunks are stored in a ChromaDB collection, by default named `transcript_embeddings`. This is configurable via `CHROMA_COLLECTION_NAME`.

### Celery NLP Task (`process_nlp_for_session_task`)

A new Celery task, `process_nlp_for_session_task`, is responsible for the NLP pipeline for a given session after transcription is complete. Its workflow:
1.  Retrieves the session and its transcript chunks from MongoDB.
2.  Updates the session's `nlp_status` to "nlp_processing".
3.  For each transcript chunk:
    a.  Generates a vector embedding for the chunk's content using `sentence-transformers` (model: `all-MiniLM-L6-v2`).
    b.  Stores this embedding in ChromaDB, along with metadata like `session_id` and `chunk_id`.
    c.  Extracts keywords from the chunk's content using KeyBERT.
    d.  Upserts these keywords into the MongoDB `keywords` collection. Each keyword document stores the term, a slug, the `session_id`, and a list of `contexts` where it appears. Each context links to the specific `transcript_chunk_id` and includes a preview of the text.
4.  Updates the session's `nlp_status` to "nlp_completed" (or "nlp_failed" if errors occur).

This task is typically chained to run after the `transcribe_youtube_audio_task` completes for a session.

### Updated MongoDB Schemas (Pydantic - `project/mongodb_schemas.py`)

Key changes for NLP processing:
-   **`TranscriptChunkSchema`**: Added `start_time` and `end_time` (float, optional) for transcript segments.
-   **`KeywordContextSchema` (New)**: Defines the structure for linking a keyword to its specific occurrence in a transcript chunk (`transcript_chunk_id`, `context_preview`).
-   **`KeywordSchema`**:
    -   Added `contexts: List[KeywordContextSchema]` to store multiple occurrences.
    -   Added `created_at` and `updated_at` timestamps.
    -   Ensured `session_id` links the keyword to its parent session.
    -   Includes an auto-generating `slug` field.
-   **`SessionSchema`**: Added `nlp_status: Optional[str]` to track the NLP processing state.

### Updated GraphQL Schema (`project/schema.py`)

The GraphQL API now exposes these new NLP-related fields:
-   **`TranscriptChunk` Type**:
    -   `startTime: Float`
    -   `endTime: Float`
-   **`KeywordContext` Type (New)**:
    -   `transcriptChunkId: ID!`
    -   `contextPreview: String!`
    -   `transcriptChunk: TranscriptChunk` (resolver to fetch the actual chunk)
-   **`Keyword` Type**:
    -   `contexts: [KeywordContext!]`
    -   `sessionId: ID!` (via resolver for `session` field)
    -   `createdAt: DateTime`
    -   `updatedAt: DateTime`
-   **`Session` Type**:
    -   `nlpStatus: String`

**Example Query for NLP Data:**
```graphql
query GetSessionWithNlpData($id: ID!) {
  session(id: $id) {
    id
    title
    nlpStatus
    transcriptionStatus
    transcript { # List of TranscriptChunks
      id
      content
      startTime
      endTime
    }
    keywords { # List of Keywords for the session
      id
      term
      slug
      contexts {
        transcriptChunkId
        contextPreview
        transcriptChunk { # Access the full chunk data from a keyword context
          id
          content
          startTime
        }
      }
      createdAt
      updatedAt
    }
  }
}
```

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
