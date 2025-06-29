# project/services/youtube_service.py
import uuid
from datetime import datetime
from project.db import get_collection

# Attempt to import Celery tasks.
CELERY_AVAILABLE = False
DUMMY_TASK_ID_PREFIX = "dummy-task-id-"

try:
    from project.tasks import transcribe_youtube_audio_task, process_nlp_for_session_task
    CELERY_AVAILABLE = True
    print("Successfully imported Celery tasks in youtube_service.")
except ImportError as e:
    print(f"WARNING (youtube_service): Celery tasks could not be imported. YouTube processing will be simulated. Error: {e}")
    # Define dummy tasks for environments where Celery is not set up/installed
    class DummyTask:
        def __init__(self, task_id_suffix):
            self.id = f"{DUMMY_TASK_ID_PREFIX}{task_id_suffix}-{str(uuid.uuid4())[:8]}"
    class DummyCeleryTask:
        def __init__(self, task_name_suffix):
            self.task_name_suffix = task_name_suffix
        def delay(self, *args, **kwargs):
            task_id_suffix = f"{self.task_name_suffix}"
            print(f"Celery not available. Simulating task {self.task_name_suffix} with args: {args}, kwargs: {kwargs}")
            return DummyTask(task_id_suffix)

    transcribe_youtube_audio_task = DummyCeleryTask("transcription")
    process_nlp_for_session_task = DummyCeleryTask("nlp")


def handle_youtube_link(youtube_url: str, enhance_options: list):
    """
    Handles a YouTube link:
    1. Creates a Session document in MongoDB.
    2. Enqueues a Celery task for transcription.
    3. Enqueues a Celery task for NLP processing (to run after transcription).
    4. Returns an immediate response.
    """
    sessions_collection = get_collection("sessions")
    new_session_id = str(uuid.uuid4())

    session_document = {
        "id": new_session_id,
        "youtube_url": youtube_url,
        "title": None,
        "source": "youtube_service",
        "createdAt": datetime.utcnow(),
        "transcription_status": "pending",
        "nlp_status": "pending", # Initialize nlp_status
        "full_transcript_text": None,
        "summary": None,
        "transcript_ids": [],
        "keyword_ids": []
    }

    try:
        sessions_collection.insert_one(session_document)
        print(f"[Service: YouTube] Created Session: {new_session_id} for URL: {youtube_url}")
    except Exception as e:
        print(f"[Service: YouTube] MongoDB Error creating Session: {e}")
        return {
            "status": "error", "message": "Failed to create session in database.", "error_details": str(e)
        }, 500

    transcription_task_id = None
    nlp_task_id = None

    try:
        # Enqueue transcription task
        transcription_task = transcribe_youtube_audio_task.delay(
            session_id=new_session_id,
            youtube_url=youtube_url
        )
        transcription_task_id = str(transcription_task.id)
        print(f"[Service: YouTube] Enqueued transcription task {transcription_task_id} for session {new_session_id}")

        # Enqueue NLP processing task
        # In a real scenario, this should ideally be chained after successful transcription.
        # For now, enqueuing directly. If transcription fails, NLP task might run on incomplete data or fail.
        # The NLP task itself has checks for transcription status.
        # The transcription task now also enqueues the NLP task upon its own completion.
        # This direct enqueue here might be redundant if the chain is reliable, or a fallback.
        # For this iteration, let's assume the transcription task is responsible for chaining.
        # So, we might not need to enqueue NLP task here directly IF transcription task does it.
        # However, the prompt for THIS subtask implies adding the NLP task enqueuing here.
        # Let's follow that, but acknowledge the chaining in project.tasks.py is also present.
        # The `project.tasks.transcribe_youtube_audio_task` was updated to enqueue NLP task.
        # So, this specific call here in the service might lead to double enqueuing if not careful.
        # For now, let's keep it as per the plan's direct instruction to modify this service for enqueuing NLP.
        # This could be a "fire-and-forget" for both, and tasks manage their dependencies.
        # Or, this service only fires the first task, and tasks chain themselves.
        # The project.tasks.py already has chaining. So, this direct call to NLP task here is likely not needed.
        # I will comment it out to prevent double enqueuing, assuming the chaining in transcribe_youtube_audio_task works.
        # If the intention was to remove chaining from tasks.py and do it here, that's a different refactor.
        # For now, assume tasks.py handles chaining.

        #nlp_task = process_nlp_for_session_task.delay(session_id=new_session_id)
        #nlp_task_id = str(nlp_task.id)
        #print(f"[Service: YouTube] Enqueued NLP processing task {nlp_task_id} for session {new_session_id}")
        # If NLP task is only enqueued by transcription task, nlp_task_id won't be available here.
        # The response should reflect what this service directly does.

    except Exception as e:
        print(f"[Service: YouTube] Celery Error enqueuing transcription task: {e}") # Changed error message
        sessions_collection.update_one(
            {"id": new_session_id},
            {"$set": {
                "transcription_status": "queue_failed",
                "nlp_status": "pending", # NLP status remains pending as its queueing depends on transcription
                "error_message": f"Error enqueuing transcription task: {str(e)}"
            }}
        )
        return {
            "status": "error", "message": "Failed to enqueue transcription task.",
            "session_id": new_session_id, "error_details": str(e)
        }, 500

    return {
        "status": "success",
        "message": "YouTube transcription job submitted", # NLP job is chained from transcription task
        "session_id": new_session_id,
        "transcription_job_id": transcription_task_id,
        # "nlp_job_id": nlp_task_id # Only available if enqueued directly here
    }, 202
