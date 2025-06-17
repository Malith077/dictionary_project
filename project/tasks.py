import os
import tempfile
from celery_app import app as celery_app # Import the Celery app instance from celery_app.py
from project.db import get_collection

# Attempt to import necessary libraries for the task.
# These will only be successful if the environment has them installed.
try:
    import whisper # from openai-whisper
    import yt_dlp
    from pydub import AudioSegment
except ImportError as e:
    print(f"Warning: One or more required packages (whisper, yt_dlp, pydub) are not installed. Transcription task will fail if run. Error: {e}")
    # Define dummy/placeholder functions or classes if needed to allow module to load for Celery worker discovery
    # For now, we'll let it raise ImportError if a worker tries to load this without dependencies.
    # Or, Celery might fail to register the task if the module can't be imported.
    # A common pattern is to guard the task definition or its core logic.
    # However, for now, let's assume the environment where the worker runs will have these.
    pass

# Global variable for the Whisper model to load it only once per worker process (if possible)
# This is a common optimization.
whisper_model = None
WHISPER_MODEL_NAME = "base" # As per user confirmation

def load_whisper_model():
    global whisper_model
    if whisper_model is None:
        try:
            print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
            whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
            print("Whisper model loaded successfully.")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            # Depending on retry strategy, could raise an exception here to make task retry.
            raise # Re-raise to make Celery task fail and potentially retry
    return whisper_model

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60) # Example retry parameters
def transcribe_youtube_audio_task(self, session_id: str, youtube_url: str):
    """
    Celery task to download audio from a YouTube URL, transcribe it,
    and update the Session document in MongoDB.
    """
    sessions_collection = get_collection("sessions")

    try:
        print(f"Task transcribe_youtube_audio_task started for session_id: {session_id}, youtube_url: {youtube_url}")

        # 1. Update Session status to "processing"
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {"transcription_status": "processing"}}
        )
        print(f"Updated session {session_id} status to 'processing'")

        # 2. Download Audio using yt-dlp
        # Create a temporary directory to store downloaded audio
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_filename_template = os.path.join(tmpdir, 'audio_%(id)s.%(ext)s')

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': audio_filename_template,
                'noplaylist': True,
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio', # Requires ffmpeg to be installed in the environment
                    'preferredcodec': 'mp3',     # Output format
                    'preferredquality': '192',   # Bitrate
                }],
                # Consider adding user agent if downloads are blocked
                # 'http_headers': {'User-Agent': 'Mozilla/5.0 ...'}
            }

            downloaded_audio_path = None
            print(f"Starting audio download for {youtube_url}...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=True)
                # yt-dlp modifies outtmpl to the actual path after download and postprocessing
                # The actual path is usually in info_dict['requested_downloads'][0]['filepath']
                # or we can list files in tmpdir if only one is expected.

                # A more robust way to get the downloaded file path:
                # Check info_dict['requested_downloads'] for the filepath
                # For simplicity, assume one file is downloaded and postprocessed to mp3
                # This part might need adjustment based on exact yt-dlp output structure
                # and if the 'outtmpl' directly gives the final path after postprocessing.
                # Often, ydl.prepare_filename(info_dict) gives the template before postprocessing.
                # After postprocessing, the filename changes.

                # Let's find the mp3 file in the temp directory.
                # This is a bit of a hack; yt-dlp's info_dict should ideally provide the final path.
                # If 'outtmpl' is a template like `%(title)s.%(ext)s`, then `ydl.prepare_filename(info_dict)`
                # would give the path *before* postprocessing. After FFmpegExtractAudio, ext changes.

                # A common way is to rely on the `info_dict['filepath']` if using `download=False` then `ydl.download([url])`
                # or check `info_dict['requested_downloads'][0]['filepath']`

                # Given the template, the ID is part of the filename.
                # Example: audio_VIDEOID.mp3
                # Let's assume the postprocessor correctly names it.
                # We can list files in tmpdir and find the .mp3 file.

                # Simplified approach: find the first .mp3 file in tmpdir
                for f_name in os.listdir(tmpdir):
                    if f_name.endswith(".mp3"):
                        downloaded_audio_path = os.path.join(tmpdir, f_name)
                        break

                if not downloaded_audio_path:
                    raise Exception("Downloaded audio file (mp3) not found after yt-dlp processing.")

            print(f"Audio downloaded successfully: {downloaded_audio_path}")

            # (Optional) Convert to WAV using pydub if Whisper prefers WAV or for consistency
            # This step might be redundant if Whisper handles MP3 well.
            # For now, assuming Whisper handles MP3 from yt-dlp. If not:
            # wav_path = os.path.join(tmpdir, "audio.wav")
            # audio = AudioSegment.from_mp3(downloaded_audio_path)
            # audio.export(wav_path, format="wav")
            # print(f"Converted to WAV: {wav_path}")
            # current_audio_path_for_whisper = wav_path
            current_audio_path_for_whisper = downloaded_audio_path


            # 3. Transcribe Audio using Whisper
            print(f"Loading Whisper model ('{WHISPER_MODEL_NAME}') for transcription...")
            model = load_whisper_model() # Get or load the model
            if not model:
                 raise Exception("Whisper model could not be loaded.")

            print(f"Starting transcription for {current_audio_path_for_whisper}...")
            result = model.transcribe(current_audio_path_for_whisper, fp16=False) # fp16=False if not using GPU or issues
            transcribed_text = result["text"]
            print(f"Transcription successful for session {session_id}.")
            # print(f"Transcribed text (first 100 chars): {transcribed_text[:100]}...")


            # 4. Store Transcript and update status
            sessions_collection.update_one(
                {"id": session_id},
                {"$set": {
                    "full_transcript_text": transcribed_text,
                    "transcription_status": "completed"
                }}
            )
            print(f"Stored transcript and updated session {session_id} status to 'completed'")

        # Temporary directory and its contents are automatically cleaned up here.
        return {"status": "success", "session_id": session_id, "message": "Transcription completed."}

    except Exception as exc:
        print(f"Error during transcription task for session {session_id}: {exc}")
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {"transcription_status": "failed", "full_transcript_text": f"Error: {str(exc)}"}}
        )
        # Retry the task if it's a retryable error
        # self.retry(exc=exc) # Celery's built-in retry mechanism
        # For now, just log and mark as failed. Retry logic can be complex.
        # Re-raising will make Celery mark it as failed and retry based on task parameters.
        raise # Re-raise so Celery knows it failed and handles retries/failure logging.

if __name__ == '__main__':
    # This block is for direct testing of the task file, not for Celery execution.
    # You would need to have Redis running and a Celery worker started separately
    # to actually process tasks submitted with .delay() or .apply_async().
    print("This file defines Celery tasks. To run them, start a Celery worker:")
    print("celery -A celery_app.app worker -l info")
    # Example of how to manually call the task function for testing (bypassing Celery queue):
    # if False: # Set to true to test directly (requires DB, yt-dlp, whisper, ffmpeg)
    #     print("Attempting direct call to transcribe_youtube_audio_task (for testing only)...")
    #     # Ensure you have a MongoDB instance running and project.db is configured.
    #     # Create a dummy session entry in DB first for the task to update.
    #     sample_session_id = "test_session_direct_call"
    #     sample_youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Example video
    #     sessions_coll = get_collection("sessions")
    #     sessions_coll.update_one(
    #         {"id": sample_session_id},
    #         {"$set": {
    #             "youtube_url": sample_youtube_url,
    #             "transcription_status": "pending",
    #             "source": "youtube", "createdAt": datetime.utcnow() # Add other required fields
    #         }},
    #         upsert=True
    #     )
    #     try:
    #         # Note: `self` argument is missing here. For direct calls, Celery task's `self` isn't populated.
    #         # If the task uses `self.request` or `self.retry`, direct calls will fail or behave differently.
    #         # Our current task uses `self` for `bind=True` but not explicitly in the code yet for `self.retry`.
    #         # To make it callable directly without `self`, you'd need to adjust or pass None.
    #         # For a bound task, Celery provides `self`.
    #         # transcribe_youtube_audio_task(sample_session_id, sample_youtube_url) # This won't work directly for bound task
    #         print("Direct call test: To properly test, submit via task.delay() and run a worker.")
    #     except Exception as e:
    #         print(f"Error during direct call test: {e}")
