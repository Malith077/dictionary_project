import os
import tempfile
import uuid # For generating TranscriptChunk IDs
from datetime import datetime

from celery_app import app as celery_app
from project.db import get_collection
from project.mongodb_schemas import TranscriptChunkSchema # For validation if inserting Pydantic models

# Attempt to import NLP/ML libraries
NLP_LIBS_AVAILABLE = False
try:
    import whisper
    import yt_dlp
    from pydub import AudioSegment # Keep for potential audio conversion, though yt-dlp handles mp3

    from sentence_transformers import SentenceTransformer
    from keybert import KeyBERT
    from project.vector_db import add_chunk_embedding, get_chroma_collection # ChromaDB functions
    # import nltk # For sentence tokenization if Whisper segments are not granular enough

    NLP_LIBS_AVAILABLE = True
    print("All NLP/ML libraries imported successfully for tasks.py.")
except ImportError as e:
    print(f"WARNING (project.tasks): One or more NLP/ML packages (whisper, yt_dlp, pydub, sentence-transformers, keybert, chromadb) are not installed. Tasks will not run correctly. Error: {e}")
    # Define placeholders if needed for Celery to register tasks even if libs are missing.
    # This allows the rest of the app to load if Celery worker isn't the current process.
    SentenceTransformer = None
    KeyBERT = None
    whisper = None
    # add_chunk_embedding might still be callable if vector_db.py loaded, but will fail if chromadb client is None.
    # Define dummy get_chroma_collection if needed, or ensure vector_db.py handles its absence.
    def get_chroma_collection(collection_name=None): # Dummy
        print("WARNING: get_chroma_collection called but ChromaDB related libraries might be missing.")
        class DummyCollection:
            def count(self): return 0
            def upsert(self, *args, **kwargs): pass
        return DummyCollection()

    def add_chunk_embedding(*args, **kwargs): # Dummy
        print("WARNING: add_chunk_embedding called but ChromaDB related libraries might be missing.")
        pass

# --- Whisper Model Loading ---
whisper_model_instance = None # Renamed to avoid conflict with whisper module
WHISPER_MODEL_NAME = "base"

def load_whisper_model():
    global whisper_model_instance
    if whisper_model_instance is None and whisper: # Check if whisper module was imported
        try:
            print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
            whisper_model_instance = whisper.load_model(WHISPER_MODEL_NAME)
            print("Whisper model loaded successfully.")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise
    elif not whisper:
        print("ERROR: Whisper library not available, cannot load model.")
        raise ImportError("Whisper library not found, cannot proceed with transcription.")
    return whisper_model_instance

# --- Sentence Transformer Model Loading ---
sentence_model_instance = None
SENTENCE_MODEL_NAME = 'all-MiniLM-L6-v2'

def load_sentence_model():
    global sentence_model_instance
    if sentence_model_instance is None and SentenceTransformer: # Check if SentenceTransformer was imported
        try:
            print(f"Loading SentenceTransformer model: {SENTENCE_MODEL_NAME}...")
            sentence_model_instance = SentenceTransformer(SENTENCE_MODEL_NAME)
            print("SentenceTransformer model loaded successfully.")
        except Exception as e:
            print(f"Error loading SentenceTransformer model: {e}")
            raise
    elif not SentenceTransformer:
        print("ERROR: SentenceTransformer library not available, cannot load model.")
        raise ImportError("SentenceTransformer library not found, cannot proceed with embeddings.")
    return sentence_model_instance

# --- KeyBERT Model Loading ---
keybert_model_instance = None

def load_keybert_model():
    global keybert_model_instance
    if keybert_model_instance is None and KeyBERT and SentenceTransformer: # KeyBERT uses sentence-transformers
        try:
            print("Loading KeyBERT model...")
            # KeyBERT can use various embedding models; ensure the one used is compatible or explicitly set.
            # It often defaults to a SentenceTransformer model if not specified.
            # We can pass our loaded sentence_model_instance to KeyBERT for consistency if desired.
            doc_model = load_sentence_model() # Ensure sentence model is loaded for KeyBERT
            keybert_model_instance = KeyBERT(model=doc_model) # Or let KeyBERT load its default
            print("KeyBERT model loaded successfully.")
        except Exception as e:
            print(f"Error loading KeyBERT model: {e}")
            raise
    elif not KeyBERT or not SentenceTransformer:
        print("ERROR: KeyBERT or SentenceTransformer library not available, cannot load model.")
        raise ImportError("KeyBERT or SentenceTransformer library not found, cannot proceed with keyword extraction.")
    return keybert_model_instance


# --- Celery Tasks ---

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_youtube_audio_task(self, session_id: str, youtube_url: str):
    """
    Downloads YouTube audio, transcribes using Whisper, creates TranscriptChunk documents,
    and stores the full transcript in the Session document.
    """
    if not whisper or not yt_dlp: # Check specific critical libraries for this task
        print(f"ERROR (Task {self.request.id if self.request else 'direct_call'}): Missing critical libraries (whisper, yt_dlp). Aborting transcription.")
        sessions_collection = get_collection("sessions")
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {"transcription_status": "failed", "full_transcript_text": "Error: Missing required libraries for transcription."}}
        )
        # To prevent retry if libs are missing (non-transient error)
        # self.update_state(state='FAILURE', meta={'exc_type': 'ImportError', 'exc_message': 'Missing libraries'})
        # raise Ignore() # Tells Celery not to retry
        return {"status": "error", "message": "Missing libraries, task aborted."}


    sessions_collection = get_collection("sessions")
    chunks_collection = get_collection("transcriptChunks")

    current_audio_path_for_whisper = None # Define to ensure it's available in broader scope for model.transcribe

    try:
        print(f"Task transcribe_youtube_audio_task started for session_id: {session_id}, youtube_url: {youtube_url}")
        sessions_collection.update_one({"id": session_id}, {"$set": {"transcription_status": "processing"}})

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_filename_template = os.path.join(tmpdir, 'audio_%(id)s.%(ext)s')
            ydl_opts = {
                'format': 'bestaudio/best', 'outtmpl': audio_filename_template,
                'noplaylist': True, 'quiet': True,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
            }
            downloaded_audio_path = None
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=True)
                for f_name in os.listdir(tmpdir): # Find the downloaded mp3
                    if f_name.endswith(".mp3"): downloaded_audio_path = os.path.join(tmpdir, f_name); break
                if not downloaded_audio_path: raise Exception("Downloaded audio (mp3) not found.")

            print(f"Audio downloaded: {downloaded_audio_path}")
            current_audio_path_for_whisper = downloaded_audio_path # Assign to broader scope variable

            model = load_whisper_model()
            print(f"Starting transcription for {current_audio_path_for_whisper}...")
            transcription_result = model.transcribe(current_audio_path_for_whisper, fp16=False, word_timestamps=False) # Get segments

            full_text = transcription_result["text"]
            created_chunk_ids = []

            print(f"Processing {len(transcription_result.get('segments', []))} transcript segments for session {session_id}...")
            for segment in transcription_result.get("segments", []):
                chunk_id = str(uuid.uuid4())
                chunk_content = segment["text"].strip()
                if not chunk_content: continue

                chunk_doc_data = {
                    "id": chunk_id,
                    "session_id": session_id,
                    "content": chunk_content,
                    "start_time": segment.get("start"),
                    "end_time": segment.get("end"),
                    "keywordSpans": []
                }
                chunks_collection.insert_one(chunk_doc_data)
                created_chunk_ids.append(chunk_id)

            sessions_collection.update_one(
                {"id": session_id},
                {"$set": {
                    "full_transcript_text": full_text,
                    "transcript_ids": created_chunk_ids,
                    "transcription_status": "completed",
                    "nlp_status": "pending" # Set NLP status to pending after transcription
                }}
            )
            print(f"Transcription successful, {len(created_chunk_ids)} chunks created for session {session_id}.")

            # If transcription is successful, trigger NLP task
            if NLP_LIBS_AVAILABLE: # Check if NLP libs are there before queueing
                 process_nlp_for_session_task.delay(session_id=session_id)
                 print(f"Enqueued process_nlp_for_session_task for session {session_id}")
            else:
                 print(f"Skipping enqueue of NLP task for session {session_id} due to missing libraries.")
                 sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_skipped_missing_libs"}})


        return {"status": "success", "session_id": session_id, "chunks_created": len(created_chunk_ids)}
    except Exception as exc:
        print(f"Error in transcribe_youtube_audio_task for session {session_id}: {exc}")
        sessions_collection.update_one(
            {"id": session_id},
            {"$set": {"transcription_status": "failed", "full_transcript_text": f"Transcription Error: {str(exc)}"}}
        )
        raise

@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def process_nlp_for_session_task(self, session_id: str):
    """
    Processes a session's transcript chunks for NLP: embeddings and keywords.
    """
    if not NLP_LIBS_AVAILABLE:
        print(f"ERROR (Task {self.request.id if self.request else 'direct_call'}): Missing critical libraries for NLP. Aborting.")
        sessions_collection = get_collection("sessions")
        sessions_collection.update_one(
            {"id": session_id}, {"$set": {"nlp_status": "nlp_failed", "error_message": "Missing libraries for NLP."}}
        )
        return {"status": "error", "message": "Missing libraries for NLP, task aborted."}

    sessions_collection = get_collection("sessions")
    chunks_collection = get_collection("transcriptChunks")
    keywords_collection = get_collection("keywords")

    try:
        print(f"Task process_nlp_for_session_task started for session_id: {session_id}")
        session_doc = sessions_collection.find_one({"id": session_id})
        if not session_doc:
            print(f"Error: Session {session_id} not found for NLP processing.")
            return {"status": "error", "message": f"Session {session_id} not found."}

        if session_doc.get("transcription_status") != "completed":
            print(f"Warning: Transcription for session {session_id} is not 'completed' (status: {session_doc.get('transcription_status')}). Skipping NLP.")
            sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_skipped_transcription_not_done"}})
            return {"status": "skipped", "message": "Transcription not completed."}

        sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_processing"}})

        transcript_chunk_ids = session_doc.get("transcript_ids", [])
        if not transcript_chunk_ids:
            print(f"No transcript chunks found for session {session_id}. Skipping NLP.")
            sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_completed_no_chunks"}})
            return {"status": "success", "message": "No chunks to process."}

        sbert_model = load_sentence_model()
        kb_model = load_keybert_model()
        vector_collection = get_chroma_collection()
        print(f"ChromaDB collection '{vector_collection.name}' ready, current count: {vector_collection.count()}")

        all_session_keyword_ids = set(session_doc.get("keyword_ids", []))

        for chunk_id in transcript_chunk_ids:
            chunk_doc = chunks_collection.find_one({"id": chunk_id})
            if not chunk_doc or not chunk_doc.get("content"):
                print(f"Warning: TranscriptChunk {chunk_id} not found or has no content. Skipping.")
                continue

            chunk_content = chunk_doc["content"]
            chunk_start_time = chunk_doc.get("start_time")

            print(f"Generating embedding for chunk {chunk_id} (session {session_id})...")
            embedding = sbert_model.encode(chunk_content).tolist()

            metadata_for_chroma = {
                "session_id": session_id,
                "chunk_id": chunk_id,
                "start_time": chunk_start_time if chunk_start_time is not None else -1
            }
            add_chunk_embedding(
                session_id=session_id, chunk_id=chunk_id,
                chunk_text=chunk_content, embedding_vector=embedding,
                metadata=metadata_for_chroma
            )
            print(f"Stored embedding for chunk {chunk_id} in ChromaDB.")

            print(f"Extracting keywords for chunk {chunk_id}...")
            keywords_with_scores = kb_model.extract_keywords(chunk_content, top_n=5, use_mmr=True, diversity=0.7)
            extracted_keyword_terms = [kw[0] for kw in keywords_with_scores]
            print(f"Extracted keywords for chunk {chunk_id}: {extracted_keyword_terms}")

            for term in extracted_keyword_terms:
                # Basic slug generation, ensure it's consistent with Pydantic model's validator
                slug = term.lower().replace(' ', '-').translate(str.maketrans('', '', '!"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~'))

                keyword_doc_id = str(uuid.uuid4()) # Generate ID for keyword document if new

                keyword_context_data = {
                    "transcript_chunk_id": chunk_id,
                    "context_preview": chunk_content[:150] + "..." if len(chunk_content) > 150 else chunk_content,
                }

                update_result = keywords_collection.update_one(
                    {"term": term, "session_id": session_id},
                    {
                        "$setOnInsert": { "id": keyword_doc_id, "slug": slug, "term": term, "session_id": session_id, "created_at": datetime.utcnow(), "definition_ids": [] },
                        "$addToSet": {"contexts": keyword_context_data},
                        "$set": {"updated_at": datetime.utcnow()}
                    },
                    upsert=True
                )
                if update_result.upserted_id: # If a new keyword document was created
                    all_session_keyword_ids.add(keyword_doc_id) # Add the new keyword's main ID
                else: # Keyword already existed for this session, find its ID to ensure it's in the session's list
                    existing_kw_doc = keywords_collection.find_one({"term": term, "session_id": session_id}, {"id": 1})
                    if existing_kw_doc:
                        all_session_keyword_ids.add(existing_kw_doc["id"])
            print(f"Updated/Stored keywords for chunk {chunk_id} in MongoDB.")

        # Update the session with the complete list of distinct keyword IDs
        sessions_collection.update_one({"id": session_id}, {"$set": {"keyword_ids": list(all_session_keyword_ids), "nlp_status": "nlp_completed"}})
        print(f"NLP processing completed successfully for session {session_id}. Session keyword_ids updated.")
        return {"status": "success", "session_id": session_id, "message": "NLP processing completed."}

    except Exception as exc:
        print(f"Error during NLP processing task for session {session_id}: {exc}")
        sessions_collection.update_one(
            {"id": session_id}, {"$set": {"nlp_status": "nlp_failed", "error_message": f"NLP Error: {str(exc)}"}}
        )
        raise

if __name__ == '__main__':
    print("This file defines Celery tasks. To run them, start a Celery worker.")
    print("Example: celery -A celery_app.app worker -l info")
