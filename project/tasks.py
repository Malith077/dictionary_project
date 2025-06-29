import os
import tempfile
import uuid
from datetime import datetime
from celery_app import app as celery_app
from project.db import get_collection

try:
    import whisper
    import yt_dlp
    from pydub import AudioSegment
except ImportError as e:
    print(f"Warning: Required packages not installed. Error: {e}")

# Global Whisper model
whisper_model = None
WHISPER_MODEL_NAME = "base"

def load_whisper_model():
    global whisper_model
    if whisper_model is None:
        try:
            print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
            whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
            print("Whisper model loaded successfully.")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise
    return whisper_model


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)  # 5 minutes between retries
def transcribe_youtube_audio_task(self, session_id: str, youtube_url: str, enhance_options: list = None):
    """
    Complete YouTube processing task:
    1. Download video and extract audio
    2. Transcribe audio using Whisper
    3. Save transcript and metadata to database
    4. Process transcript chunks and keywords (if enabled)
    """
    if enhance_options is None:
        enhance_options = []
    
    sessions_collection = get_collection("sessions")
    
    try:
        print(f"Starting YouTube processing task for session: {session_id}")
        
        # Update status to processing
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {
                "transcription_status": "processing",
                "processing_metadata.processing_started_at": datetime.utcnow()
            }}
        )
        
        # Step 1: Download and extract audio
        print(f"Step 1: Downloading audio from {youtube_url}")
        audio_path, video_info = download_youtube_audio(youtube_url)
        
        # Update session with video metadata
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {
                "title": video_info.get("title", "Unknown Title"),
                "processing_metadata.video_title": video_info.get("title"),
                "processing_metadata.video_duration": video_info.get("duration"),
                "processing_metadata.video_description": video_info.get("description", "")[:500],  # Truncate
                "processing_metadata.audio_format": "mp3"
            }}
        )
        
        # Step 2: Transcribe audio
        print(f"Step 2: Transcribing audio for session {session_id}")
        model = load_whisper_model()
        result = model.transcribe(audio_path, fp16=False)
        transcribed_text = result["text"].strip()
        
        # Step 3: Save complete transcript
        print(f"Step 3: Saving transcript for session {session_id}")
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {
                "full_transcript_text": transcribed_text,
                "transcription_status": "completed",
                "processing_metadata.processing_completed_at": datetime.utcnow(),
                "processing_metadata.transcription_model": WHISPER_MODEL_NAME
            }}
        )
        
        # Step 4: Process transcript chunks (if requested)
        if "create_chunks" in enhance_options:
            print(f"Step 4: Creating transcript chunks for session {session_id}")
            chunk_ids = create_transcript_chunks(session_id, transcribed_text)
            sessions_collection.update_one(
                {"id": session_id},
                {"$set": {"transcript_ids": chunk_ids}}
            )
        
        # Step 5: Extract and process keywords (if requested)
        if "extract_keywords" in enhance_options:
            print(f"Step 5: Extracting keywords for session {session_id}")
            keyword_ids = extract_and_save_keywords(session_id, transcribed_text)
            sessions_collection.update_one(
                {"id": session_id},
                {"$set": {"keyword_ids": keyword_ids}}
            )
        
        print(f"YouTube processing completed successfully for session {session_id}")
        return {
            "status": "success",
            "session_id": session_id,
            "transcript_length": len(transcribed_text),
            "processing_time": "completed"
        }
        
    except Exception as exc:
        print(f"Error in YouTube processing task for session {session_id}: {exc}")
        
        # Log the error and update session status
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {
                "transcription_status": "failed",
                "processing_metadata.error_log": [str(exc)],
                "processing_metadata.processing_completed_at": datetime.utcnow()
            }}
        )
        
        # Retry logic
        if self.request.retries < self.max_retries:
            print(f"Retrying task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=exc)
        else:
            print(f"Max retries reached for session {session_id}")
            raise


def download_youtube_audio(youtube_url: str) -> tuple:
    """Download audio from YouTube URL and return path + video info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_filename_template = os.path.join(tmpdir, 'audio_%(id)s.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_filename_template,
            'noplaylist': True,
            'quiet': False,  # Set to False to see more debugging info
            'no_warnings': False,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': 192,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            # Anti-bot measures
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            'extractor_retries': 3,
            'fragment_retries': 3,
            'retries': 3,
            'file_access_retries': 3,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            # Use cookies if available (helps with rate limiting)
            'cookiefile': None,
            # Bypass geo-blocking if needed
            'geo_bypass': True,
            # Additional options to help with YouTube issues
            'youtube_include_dash_manifest': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Attempting to download: {youtube_url}")
                info_dict = ydl.extract_info(youtube_url, download=True)
                
                # Find the downloaded MP3 file
                downloaded_audio_path = None
                for filename in os.listdir(tmpdir):
                    if filename.endswith(".mp3"):
                        downloaded_audio_path = os.path.join(tmpdir, filename)
                        break
                
                if not downloaded_audio_path:
                    raise Exception("Downloaded audio file not found after processing")
                
                # Move file to a persistent temporary location for processing
                persistent_audio_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
                os.rename(downloaded_audio_path, persistent_audio_path)
                
                print(f"Successfully downloaded audio to: {persistent_audio_path}")
                return persistent_audio_path, info_dict
                
        except yt_dlp.DownloadError as e:
            if "403" in str(e) or "Forbidden" in str(e):
                print(f"YouTube blocked the request. Trying with different format...")
                # Try with a different format as fallback
                fallback_opts = ydl_opts.copy()
                fallback_opts['format'] = 'worstaudio/worst'  # Try worst quality as fallback
                fallback_opts['sleep_interval'] = 3  # Longer delay
                
                try:
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl_fallback:
                        info_dict = ydl_fallback.extract_info(youtube_url, download=True)
                        
                        # Find the downloaded file
                        downloaded_audio_path = None
                        for filename in os.listdir(tmpdir):
                            if any(filename.endswith(ext) for ext in ['.mp3', '.m4a', '.webm', '.opus']):
                                downloaded_audio_path = os.path.join(tmpdir, filename)
                                break
                        
                        if not downloaded_audio_path:
                            raise Exception("Fallback download also failed to create audio file")
                        
                        # Convert to mp3 if needed
                        if not downloaded_audio_path.endswith('.mp3'):
                            mp3_path = os.path.join(tmpdir, 'converted_audio.mp3')
                            audio = AudioSegment.from_file(downloaded_audio_path)
                            audio.export(mp3_path, format="mp3")
                            downloaded_audio_path = mp3_path
                        
                        persistent_audio_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
                        os.rename(downloaded_audio_path, persistent_audio_path)
                        
                        print(f"Fallback download successful: {persistent_audio_path}")
                        return persistent_audio_path, info_dict
                        
                except Exception as fallback_error:
                    raise Exception(f"Both primary and fallback downloads failed. Primary: {str(e)}, Fallback: {str(fallback_error)}")
            else:
                raise e


def create_transcript_chunks(session_id: str, transcript_text: str, chunk_size: int = 1000) -> list:
    """Break transcript into chunks and save to database."""
    chunks_collection = get_collection("transcript_chunks")
    chunk_ids = []
    
    # Simple chunking by character count with word boundaries
    words = transcript_text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > chunk_size and current_chunk:
            # Save current chunk
            chunk_id = str(uuid.uuid4())
            chunk_text = " ".join(current_chunk)
            
            chunk_document = {
                "id": chunk_id,
                "session_id": session_id,
                "content": chunk_text,
                "keywordSpans": [],
                "created_at": datetime.utcnow(),
                "chunk_index": len(chunk_ids)
            }
            
            chunks_collection.insert_one(chunk_document)
            chunk_ids.append(chunk_id)
            
            # Reset for next chunk
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    # Save final chunk if any content remains
    if current_chunk:
        chunk_id = str(uuid.uuid4())
        chunk_text = " ".join(current_chunk)
        
        chunk_document = {
            "id": chunk_id,
            "session_id": session_id,
            "content": chunk_text,
            "keywordSpans": [],
            "created_at": datetime.utcnow(),
            "chunk_index": len(chunk_ids)
        }
        
        chunks_collection.insert_one(chunk_document)
        chunk_ids.append(chunk_id)
    
    return chunk_ids


def extract_and_save_keywords(session_id: str, transcript_text: str) -> list:
    """Extract keywords from transcript and save to database."""
    keywords_collection = get_collection("keywords")
    keyword_ids = []
    
    # Simple keyword extraction (you could enhance this with NLP libraries)
    # For now, let's extract words that appear frequently and are longer than 4 characters
    words = transcript_text.lower().split()
    word_freq = {}
    
    for word in words:
        # Clean word (remove punctuation)
        clean_word = ''.join(c for c in word if c.isalnum())
        if len(clean_word) > 4:  # Only consider longer words
            word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
    
    # Get top 20 most frequent words as keywords
    top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    
    for keyword, frequency in top_keywords:
        keyword_id = str(uuid.uuid4())
        
        keyword_document = {
            "id": keyword_id,
            "slug": keyword.lower().replace(" ", "-"),
            "term": keyword,
            "session_id": session_id,
            "definition_ids": [],
            "frequency": frequency,
            "created_at": datetime.utcnow()
        }
        
        keywords_collection.insert_one(keyword_document)
        keyword_ids.append(keyword_id)
    
    return keyword_ids