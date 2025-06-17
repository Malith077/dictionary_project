# project/services/youtube_service.py
import uuid
from datetime import datetime
from project.db import get_collection
# Attempt to import the Celery task. This will only work if project.tasks can be loaded.
# Guarding with try-except in case Celery/its dependencies are not installed during development.
try:
    from project.tasks import transcribe_youtube_audio_task
    CELERY_AVAILABLE = True
except ImportError:
    print("WARNING: Celery task 'transcribe_youtube_audio_task' could not be imported. YouTube processing will be simulated.")
    CELERY_AVAILABLE = False
    # Define a dummy task for environments where Celery is not set up/installed
    class DummyTask:
        def __init__(self, task_id):
            self.id = task_id
    class DummyCeleryTask:
        def delay(self, *args, **kwargs):
            print(f"Celery not available. Simulating task submission for transcribe_youtube_audio_task with args: {args}, kwargs: {kwargs}")
            return DummyTask(str(uuid.uuid4())) # Return a dummy task object with an id
    transcribe_youtube_audio_task = DummyCeleryTask()


def handle_youtube_link(youtube_url: str, enhance_options: list):
    """
    Handles the logic for a submitted YouTube link:
    1. Creates a new Session document in MongoDB.
    2. Enqueues a Celery task for transcription.
    3. Returns an immediate response.
    """
    sessions_collection = get_collection("sessions")

    # 1. Create a new Session document
    new_session_id = str(uuid.uuid4()) # Generate a unique ID for the session
    session_document = {
        "id": new_session_id,
        "youtube_url": youtube_url,
        "title": None, # Title could be fetched later by yt-dlp if needed
        "source": "youtube_service", # Indicate the origin
        "createdAt": datetime.utcnow(),
        "transcription_status": "pending",
        "full_transcript_text": None,
        "summary": None,
        "transcript_ids": [], # Initialize as empty
        "keyword_ids": []     # Initialize as empty
        # enhance_options could be stored too if they influence processing
    }

    try:
        sessions_collection.insert_one(session_document)
        print(f"[Service: YouTube] Created new Session document with id: {new_session_id} for URL: {youtube_url}")
    except Exception as e:
        print(f"[Service: YouTube] Error creating Session document in MongoDB: {e}")
        # Depending on error handling strategy, could return an error response here.
        return {
            "status": "error",
            "message": "Failed to create session in database.",
            "error_details": str(e)
        }, 500 # Internal Server Error status code for the HTTP response

    # 2. Enqueue Celery task
    try:
        task = transcribe_youtube_audio_task.delay(
            session_id=new_session_id,
            youtube_url=youtube_url
        )
        task_id = task.id
        print(f"[Service: YouTube] Enqueued transcription task {task_id} for session {new_session_id}")
    except Exception as e:
        # This might happen if the Celery broker is down, or task isn't registered
        # or if CELERY_AVAILABLE is False and dummy task somehow fails (though unlikely)
        print(f"[Service: YouTube] Error enqueuing Celery task: {e}")
        # Update session status to 'failed' or 'queue_failed'
        sessions_collection.update_one(
            {"id": new_session_id},
            {"$set": {"transcription_status": "queue_failed", "full_transcript_text": f"Error enqueuing task: {str(e)}"}}
        )
        return {
            "status": "error",
            "message": "Failed to enqueue transcription task.",
            "session_id": new_session_id, # Still return session_id as it was created
            "error_details": str(e)
        }, 500


    # 3. Return immediate response
    response_data = {
        "status": "success",
        "message": "YouTube transcription job submitted",
        "session_id": new_session_id,
        "job_id": str(task_id) # Ensure task_id is string for JSON
    }
    return response_data, 202 # 202 Accepted status code is appropriate for async job submission
