import os
import tempfile
import uuid # For generating IDs
from datetime import datetime

from celery_app import app as celery_app # Import the Celery app instance
from project.db import get_collection
# from project.mongodb_schemas import TranscriptChunkSchema # For validation if needed

# Attempt to import NLP/ML libraries and services
NLP_LIBS_AVAILABLE = False
OLLAMA_SERVICE_AVAILABLE = False
try:
    import whisper
    import yt_dlp
    from pydub import AudioSegment

    from sentence_transformers import SentenceTransformer
    from keybert import KeyBERT
    from project.vector_db import add_chunk_embedding, get_chroma_collection
    # import nltk

    NLP_LIBS_AVAILABLE = True
    print("All NLP/ML libraries (Whisper, yt-dlp, ST, KeyBERT, ChromaDB access) imported successfully for tasks.py.")
except ImportError as e:
    print(f"WARNING (project.tasks.nlp_libs): One or more NLP/ML packages are not installed. Tasks relying on them will not run correctly. Error: {e}")
    SentenceTransformer = None
    KeyBERT = None
    whisper = None
    # Define dummy functions for vector_db interactions if NLP_LIBS_AVAILABLE is False
    def add_chunk_embedding(*args, **kwargs):
        print("Dummy add_chunk_embedding called as NLP libraries are missing.")
        pass
    def get_chroma_collection(*args, **kwargs):
        print("Dummy get_chroma_collection called as NLP libraries are missing.")
        class DummyCollection:
            def count(self): return 0
            def upsert(self, *args, **kwargs): pass
        return DummyCollection()


try:
    from project.services import ollama_service
    OLLAMA_SERVICE_AVAILABLE = True
    print("ollama_service imported successfully for tasks.py.")
except ImportError as e:
    print(f"WARNING (project.tasks.ollama_service): project.services.ollama_service could not be imported. Definition generation task will not run correctly. Error: {e}")
    # Define a dummy ollama_service if it's not available
    class DummyOllamaService:
        def generate_definition(self, *args, **kwargs):
            print("Ollama service (dummy): generate_definition called, but service not available.")
            return None
    ollama_service = DummyOllamaService()


# --- Model Loading Functions (Whisper, SentenceTransformer, KeyBERT) ---
whisper_model_instance = None
WHISPER_MODEL_NAME = "base"
def load_whisper_model():
    global whisper_model_instance
    if whisper_model_instance is None and whisper:
        try:
            print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
            whisper_model_instance = whisper.load_model(WHISPER_MODEL_NAME)
            print(f"Whisper model '{WHISPER_MODEL_NAME}' loaded.")
        except Exception as e: print(f"Error loading Whisper model: {e}"); raise
    elif not whisper: raise ImportError("Whisper library not found.")
    return whisper_model_instance

sentence_model_instance = None
SENTENCE_MODEL_NAME = 'all-MiniLM-L6-v2'
def load_sentence_model():
    global sentence_model_instance
    if sentence_model_instance is None and SentenceTransformer:
        try:
            print(f"Loading SentenceTransformer model: {SENTENCE_MODEL_NAME}...")
            sentence_model_instance = SentenceTransformer(SENTENCE_MODEL_NAME)
            print(f"SentenceTransformer model '{SENTENCE_MODEL_NAME}' loaded.")
        except Exception as e: print(f"Error loading SentenceTransformer model: {e}"); raise
    elif not SentenceTransformer: raise ImportError("SentenceTransformer library not found.")
    return sentence_model_instance

keybert_model_instance = None
def load_keybert_model():
    global keybert_model_instance
    if keybert_model_instance is None and KeyBERT and SentenceTransformer:
        try:
            print("Loading KeyBERT model...")
            doc_model = load_sentence_model()
            keybert_model_instance = KeyBERT(model=doc_model)
            print("KeyBERT model loaded.")
        except Exception as e: print(f"Error loading KeyBERT model: {e}"); raise
    elif not KeyBERT or not SentenceTransformer: raise ImportError("KeyBERT or SentenceTransformer library not found.")
    return keybert_model_instance

# --- Celery Tasks ---

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_youtube_audio_task(self, session_id: str, youtube_url: str):
    sessions_collection = get_collection("sessions")
    chunks_collection = get_collection("transcriptChunks")

    if not whisper or not yt_dlp:
        task_id = self.request.id if self.request else "direct_call"
        print(f"ERROR (Task {task_id}): Missing whisper/yt_dlp. Aborting transcription for session {session_id}.")
        sessions_collection.update_one({"id": session_id}, {"$set": {"transcription_status": "failed", "full_transcript_text": "Error: Missing libraries for transcription."}})
        return {"status": "error", "message": "Missing libraries for transcription"}

    try:
        print(f"Task transcribe_youtube_audio_task started for session_id: {session_id}")
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
                for f_name in os.listdir(tmpdir):
                    if f_name.endswith(".mp3"): downloaded_audio_path = os.path.join(tmpdir, f_name); break
                if not downloaded_audio_path: raise Exception("Downloaded audio (mp3) not found.")

            model = load_whisper_model()
            transcription_result = model.transcribe(downloaded_audio_path, fp16=False, word_timestamps=False)

            full_text = transcription_result["text"]
            created_chunk_ids = []

            for segment in transcription_result.get("segments", []):
                chunk_id = str(uuid.uuid4())
                chunk_content = segment["text"].strip()
                if not chunk_content: continue
                chunk_doc_data = {
                    "id": chunk_id, "session_id": session_id, "content": chunk_content,
                    "start_time": segment.get("start"), "end_time": segment.get("end"),
                    "keywordSpans": []
                }
                chunks_collection.insert_one(chunk_doc_data)
                created_chunk_ids.append(chunk_id)

            sessions_collection.update_one(
                {"id": session_id},
                {"$set": {
                    "full_transcript_text": full_text, "transcript_ids": created_chunk_ids,
                    "transcription_status": "completed", "nlp_status": "pending"
                }}
            )
            print(f"Transcription successful for session {session_id}, {len(created_chunk_ids)} chunks created.")

            if NLP_LIBS_AVAILABLE:
                print(f"Enqueuing NLP processing task for session {session_id}")
                process_nlp_for_session_task.delay(session_id=session_id)
            else:
                print(f"Skipping NLP processing for session {session_id} due to missing libraries.")
                sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_skipped_missing_libs"}})

        return {"status": "success", "session_id": session_id, "chunks_created": len(created_chunk_ids)}
    except Exception as exc:
        print(f"Error in transcribe_youtube_audio_task for session {session_id}: {exc}")
        sessions_collection.update_one({"id": session_id}, {"$set": {"transcription_status": "failed", "full_transcript_text": f"Transcription Error: {str(exc)}"}})
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def process_nlp_for_session_task(self, session_id: str):
    sessions_collection = get_collection("sessions")
    chunks_collection = get_collection("transcriptChunks")
    keywords_collection = get_collection("keywords")
    task_id_str = self.request.id if self.request else "direct_call"

    if not NLP_LIBS_AVAILABLE:
        print(f"ERROR (Task {task_id_str}): Missing NLP libs. Aborting NLP for session {session_id}.")
        sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_failed", "error_message": "Missing libraries for NLP."}})
        return {"status": "error", "message": "Missing libraries for NLP"}

    try:
        print(f"Task process_nlp_for_session_task started for session_id: {session_id}")
        session_doc = sessions_collection.find_one({"id": session_id})
        if not session_doc or session_doc.get("transcription_status") != "completed":
            print(f"Skipping NLP for session {session_id}: session not found or transcription not complete.")
            return {"status": "skipped", "message": "Session not found or transcription not complete."}

        sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_processing"}})
        transcript_chunk_ids = session_doc.get("transcript_ids", [])
        if not transcript_chunk_ids:
            sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_completed_no_chunks"}})
            return {"status": "success", "message": "No chunks to process for NLP."}

        sbert_model = load_sentence_model()
        kb_model = load_keybert_model()
        vector_collection = get_chroma_collection()
        if vector_collection: print(f"ChromaDB collection '{vector_collection.name}' ready, current count: {vector_collection.count()}")

        all_session_keyword_ids = set(session_doc.get("keyword_ids", []))

        for chunk_id in transcript_chunk_ids:
            chunk_doc = chunks_collection.find_one({"id": chunk_id})
            if not chunk_doc or not chunk_doc.get("content"): continue
            chunk_content = chunk_doc["content"]

            embedding = sbert_model.encode(chunk_content).tolist()
            metadata_for_chroma = {"session_id": session_id, "chunk_id": chunk_id, "start_time": chunk_doc.get("start_time", -1)}
            add_chunk_embedding(session_id, chunk_id, chunk_content, embedding, metadata_for_chroma)

            keywords_with_scores = kb_model.extract_keywords(chunk_content, top_n=5, use_mmr=True, diversity=0.7)
            for term, score in keywords_with_scores:
                slug = term.lower().replace(' ', '-').translate(str.maketrans('', '', '!"#$%&\'()*+,./:;<=>?@[\\]^_`{|}~'))
                keyword_doc_id = str(uuid.uuid4())
                keyword_context_data = {"transcript_chunk_id": chunk_id, "context_preview": chunk_content[:150] + "..."}
                update_result = keywords_collection.update_one(
                    {"term": term, "session_id": session_id},
                    {"$setOnInsert": { "id": keyword_doc_id, "slug": slug, "term": term, "session_id": session_id, "created_at": datetime.utcnow(), "definition_ids": [] },
                     "$addToSet": {"contexts": keyword_context_data}, "$set": {"updated_at": datetime.utcnow()}},
                    upsert=True
                )
                if update_result.upserted_id: all_session_keyword_ids.add(keyword_doc_id)
                else:
                    existing_kw_doc = keywords_collection.find_one({"term": term, "session_id": session_id}, {"id": 1})
                    if existing_kw_doc: all_session_keyword_ids.add(existing_kw_doc["id"])

        sessions_collection.update_one({"id": session_id}, {"$set": {"keyword_ids": list(all_session_keyword_ids), "nlp_status": "nlp_completed", "definition_status": "pending"}})
        print(f"NLP processing completed for session {session_id}.")

        if OLLAMA_SERVICE_AVAILABLE:
            print(f"Enqueuing definition generation task for session {session_id}")
            generate_definitions_for_session_task.delay(session_id=session_id)
        else:
            print(f"Skipping definition generation for session {session_id} due to missing Ollama service/requests lib.")
            sessions_collection.update_one({"id": session_id}, {"$set": {"definition_status": "defs_skipped_missing_service"}})

        return {"status": "success", "session_id": session_id, "message": "NLP processing completed."}
    except Exception as exc:
        print(f"Error in process_nlp_for_session_task for session {session_id}: {exc}")
        sessions_collection.update_one({"id": session_id}, {"$set": {"nlp_status": "nlp_failed", "error_message": f"NLP Error: {str(exc)}"}})
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=180)
def generate_definitions_for_session_task(self, session_id: str):
    sessions_collection = get_collection("sessions") # Define for this scope
    keywords_collection = get_collection("keywords")
    definitions_collection = get_collection("definitions")
    task_id_str = self.request.id if self.request else "direct_call"

    if not OLLAMA_SERVICE_AVAILABLE:
        print(f"ERROR (Task {task_id_str}): Ollama service not available. Aborting definition generation for session {session_id}.")
        sessions_collection.update_one({"id": session_id}, {"$set": {"definition_status": "defs_failed", "error_message": "Ollama service/requests not available."}})
        return {"status": "error", "message": "Ollama service not available"}

    try:
        print(f"Task generate_definitions_for_session_task started for session_id: {session_id}")
        session_doc = sessions_collection.find_one({"id": session_id})
        if not session_doc or session_doc.get("nlp_status") != "nlp_completed":
            print(f"Skipping definition generation for session {session_id}: NLP not completed or session not found.")
            return {"status": "skipped", "message": "NLP not completed or session not found."}

        sessions_collection.update_one({"id": session_id}, {"$set": {"definition_status": "defs_processing"}})

        session_keywords = list(keywords_collection.find({"session_id": session_id}))
        if not session_keywords:
            print(f"No keywords found for session {session_id} to generate definitions for.")
            sessions_collection.update_one({"id": session_id}, {"$set": {"definition_status": "defs_completed_no_keywords"}})
            return {"status": "success", "message": "No keywords to define."}

        total_definitions_generated = 0
        for keyword_doc in session_keywords:
            keyword_term = keyword_doc["term"]
            keyword_id = keyword_doc["id"]

            for context_entry in keyword_doc.get("contexts", []):
                context_preview = context_entry["context_preview"]

                print(f"Generating definition for keyword '{keyword_term}' in context: {context_preview[:50]}...")
                definition_text = ollama_service.generate_definition(keyword_term, context_preview)

                if definition_text:
                    def_id = str(uuid.uuid4())
                    definition_doc_data = {
                        "id": def_id, "keyword_id": keyword_id,
                        "context_preview": context_preview, "definition_text": definition_text,
                        "created_at": datetime.utcnow(),
                        "llm_model_identifier": os.environ.get("OLLAMA_MODEL", ollama_service.OLLAMA_MODEL_DEFAULT if hasattr(ollama_service, 'OLLAMA_MODEL_DEFAULT') else "unknown")
                    }
                    # Validate with Pydantic before insert (optional)
                    # from project.mongodb_schemas import DefinitionSchema
                    # validated_def_data = DefinitionSchema(**definition_doc_data).model_dump()
                    # definitions_collection.insert_one(validated_def_data)
                    definitions_collection.insert_one(definition_doc_data)

                    keywords_collection.update_one(
                        {"id": keyword_id},
                        {"$addToSet": {"definition_ids": def_id}, "$set": {"updated_at": datetime.utcnow()}}
                    )
                    total_definitions_generated += 1

        sessions_collection.update_one({"id": session_id}, {"$set": {"definition_status": "defs_completed"}})
        print(f"Definition generation completed for session {session_id}. Generated {total_definitions_generated} definitions.")
        return {"status": "success", "session_id": session_id, "definitions_generated": total_definitions_generated}

    except Exception as exc:
        print(f"Error in generate_definitions_for_session_task for session {session_id}: {exc}")
        sessions_collection.update_one(
            {"id": session_id}, {"$set": {"definition_status": "defs_failed", "error_message": f"Definition Gen Error: {str(exc)}"}}
        )
        raise

if __name__ == '__main__':
    print("This file defines Celery tasks. To run them, start a Celery worker.")
    print("Example: celery -A celery_app.app worker -l info")
