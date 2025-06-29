# project/services/youtube_service.py
import uuid
from datetime import datetime
from typing import Dict, Tuple, Any
from project.db import get_collection

# Attempt to import the Celery task
try:
    from project.tasks import transcribe_youtube_audio_task
    CELERY_AVAILABLE = True
except ImportError:
    print("WARNING: Celery task 'transcribe_youtube_audio_task' could not be imported. YouTube processing will be simulated.")
    CELERY_AVAILABLE = False
    
    class DummyTask:
        def __init__(self, task_id):
            self.id = task_id
    
    class DummyCeleryTask:
        def delay(self, *args, **kwargs):
            print(f"Celery not available. Simulating task submission for transcribe_youtube_audio_task with args: {args}, kwargs: {kwargs}")
            return DummyTask(str(uuid.uuid4()))
    
    transcribe_youtube_audio_task = DummyCeleryTask()


def validate_youtube_url(url: str) -> bool:
    """Validate if the provided URL is a valid YouTube URL."""
    youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
    return any(domain in url.lower() for domain in youtube_domains)


def handle_youtube_link(youtube_url: str, enhance_options: list = None) -> Tuple[Dict[str, Any], int]:
    """
    Handles the complete YouTube processing workflow:
    1. Validates the YouTube URL
    2. Creates a new Session document in MongoDB
    3. Enqueues a Celery task for download, transcription, and processing
    4. Returns an immediate response with session details
    
    Args:
        youtube_url (str): The YouTube video URL to process
        enhance_options (list, optional): Processing enhancement options
    
    Returns:
        Tuple[Dict[str, Any], int]: Response data and HTTP status code
    """
    if enhance_options is None:
        enhance_options = []
    
    # 1. Validate YouTube URL
    if not validate_youtube_url(youtube_url):
        return {
            "status": "error",
            "message": "Invalid YouTube URL provided",
            "error_details": "URL must be a valid YouTube video link"
        }, 400
    
    sessions_collection = get_collection("sessions")
    
    # 2. Create a new Session document
    new_session_id = str(uuid.uuid4())
    session_document = {
        "id": new_session_id,
        "youtube_url": youtube_url,
        "title": None,  # Will be extracted during processing
        "source": "youtube_service",
        "createdAt": datetime.utcnow(),
        "transcription_status": "pending",
        "full_transcript_text": None,
        "summary": None,
        "transcript_ids": [],
        "keyword_ids": [],
        "enhance_options": enhance_options,
        "processing_metadata": {
            "video_duration": None,
            "video_title": None,
            "video_description": None,
            "audio_format": None,
            "transcription_model": "base",  # Whisper model used
            "processing_started_at": None,
            "processing_completed_at": None,
            "error_log": []
        }
    }
    
    try:
        sessions_collection.insert_one(session_document)
        print(f"[Service: YouTube] Created new Session document with id: {new_session_id} for URL: {youtube_url}")
    except Exception as e:
        print(f"[Service: YouTube] Error creating Session document in MongoDB: {e}")
        return {
            "status": "error",
            "message": "Failed to create session in database",
            "error_details": str(e)
        }, 500
    
    # 3. Enqueue Celery task for complete processing
    try:
        task = transcribe_youtube_audio_task.delay(
            session_id=new_session_id,
            youtube_url=youtube_url,
            enhance_options=enhance_options
        )
        task_id = task.id
        print(f"[Service: YouTube] Enqueued transcription task {task_id} for session {new_session_id}")
        
        # Update session with task ID
        sessions_collection.update_one(
            {"id": new_session_id},
            {"$set": {"celery_task_id": str(task_id)}}
        )
        
    except Exception as e:
        print(f"[Service: YouTube] Error enqueuing Celery task: {e}")
        sessions_collection.update_one(
            {"id": new_session_id},
            {"$set": {
                "transcription_status": "queue_failed",
                "processing_metadata.error_log": [f"Error enqueuing task: {str(e)}"]
            }}
        )
        return {
            "status": "error",
            "message": "Failed to enqueue transcription task",
            "session_id": new_session_id,
            "error_details": str(e)
        }, 500
    
    # 4. Return immediate response
    response_data = {
        "status": "success",
        "message": "YouTube transcription job submitted successfully",
        "session_id": new_session_id,
        "job_id": str(task_id),
        "youtube_url": youtube_url,
        "estimated_processing_time": "2-5 minutes",  # Rough estimate
        "check_status_endpoint": f"/api/sessions/{new_session_id}/status"
    }
    return response_data, 202  # 202 Accepted


def get_session_status(session_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Get the current status of a YouTube processing session.
    
    Args:
        session_id (str): The session ID to check
    
    Returns:
        Tuple[Dict[str, Any], int]: Session status and HTTP status code
    """
    sessions_collection = get_collection("sessions")
    
    try:
        session = sessions_collection.find_one({"id": session_id})
        if not session:
            return {
                "status": "error",
                "message": "Session not found",
                "session_id": session_id
            }, 404
        
        # Remove MongoDB's _id field for clean response
        session.pop('_id', None)
        
        response_data = {
            "status": "success",
            "session": session,
            "is_completed": session.get("transcription_status") == "completed",
            "has_error": session.get("transcription_status") == "failed"
        }
        return response_data, 200
        
    except Exception as e:
        print(f"[Service: YouTube] Error fetching session status: {e}")
        return {
            "status": "error",
            "message": "Failed to fetch session status",
            "error_details": str(e)
        }, 500


def get_session_transcript(session_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Get the transcript for a completed session.
    
    Args:
        session_id (str): The session ID
    
    Returns:
        Tuple[Dict[str, Any], int]: Transcript data and HTTP status code
    """
    sessions_collection = get_collection("sessions")
    
    try:
        session = sessions_collection.find_one({"id": session_id})
        if not session:
            return {
                "status": "error",
                "message": "Session not found"
            }, 404
        
        if session.get("transcription_status") != "completed":
            return {
                "status": "error",
                "message": "Transcription not yet completed",
                "current_status": session.get("transcription_status", "unknown")
            }, 400
        
        response_data = {
            "status": "success",
            "session_id": session_id,
            "transcript": session.get("full_transcript_text", ""),
            "title": session.get("title"),
            "youtube_url": session.get("youtube_url"),
            "processing_metadata": session.get("processing_metadata", {}),
            "created_at": session.get("createdAt"),
            "word_count": len(session.get("full_transcript_text", "").split()) if session.get("full_transcript_text") else 0
        }
        return response_data, 200
        
    except Exception as e:
        print(f"[Service: YouTube] Error fetching transcript: {e}")
        return {
            "status": "error",
            "message": "Failed to fetch transcript",
            "error_details": str(e)
        }, 500