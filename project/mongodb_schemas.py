from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

# Pydantic models define the expected structure for MongoDB documents.

class KeywordSpanSchema(BaseModel): # Unchanged from previous version for now
    id: str = Field(..., description="Unique identifier for the keyword span")
    keyword_id: str = Field(..., description="Identifier of the associated keyword")
    startIndex: int = Field(..., description="Start index of the keyword in the content")
    endIndex: int = Field(..., description="End index of the keyword in the content")

class TranscriptChunkSchema(BaseModel): # Updated
    id: str = Field(..., description="Unique identifier for the transcript chunk")
    session_id: str = Field(..., description="Identifier of the parent session")
    content: str = Field(..., description="Text content of the transcript chunk")
    start_time: Optional[float] = Field(None, description="Start time of the chunk in seconds from the beginning of the audio")
    end_time: Optional[float] = Field(None, description="End time of the chunk in seconds from the beginning of the audio")
    keywordSpans: List[KeywordSpanSchema] = Field(default_factory=list, description="List of keyword spans within this chunk (if using detailed span mapping)")
    # Note: KeywordSpans might become less relevant if keywords are linked via KeywordSchema.contexts to the chunk itself.
    # For now, keeping it for potential fine-grained highlighting within a chunk.

class KeywordContextSchema(BaseModel): # New Schema
    transcript_chunk_id: str = Field(..., description="ID of the TranscriptChunk where the keyword appears")
    # embedding_id: Optional[str] = Field(None, description="ID of the embedding in ChromaDB for this chunk's context (optional here, might be managed separately)")
    context_preview: str = Field(..., description="A snippet of the context (e.g., the chunk content or a summary)")
    # start_time_in_chunk: Optional[float] = Field(None, description="Relative start time of keyword in this chunk (if available)")
    # end_time_in_chunk: Optional[float] = Field(None, description="Relative end time of keyword in this chunk (if available)")
    # For simplicity, the chunk's overall start_time (from TranscriptChunkSchema, referenced by transcript_chunk_id) can serve as context timestamp.

class DefinitionSchema(BaseModel): # Unchanged for now
    id: str = Field(..., description="Unique identifier for the definition")
    keyword_id: str = Field(..., description="Identifier of the associated keyword")
    contextSummary: str = Field(..., description="Summary of the context in which the keyword was defined") # This might relate to KeywordContextSchema later
    definitionText: str = Field(..., description="The generated definition text")
    createdAt: datetime = Field(..., description="Timestamp of when the definition was created")
    modelUsed: str = Field(..., description="Identifier of the LLM model used to generate the definition")

class KeywordSchema(BaseModel): # Updated
    id: str = Field(..., description="Unique identifier for the keyword")
    term: str = Field(..., description="The keyword term itself")
    slug: str = Field(..., description="URL-safe unique slug for the keyword (generated from term)")
    session_id: str = Field(..., description="Identifier of the session where this keyword was identified")
    contexts: List[KeywordContextSchema] = Field(default_factory=list, description="List of contexts where this keyword appears")
    definition_ids: List[str] = Field(default_factory=list, description="List of IDs of definitions for this keyword")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of keyword creation")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of last update to keyword contexts or definitions")

    @validator('slug', pre=True, always=True)
    def generate_slug(cls, v, values):
        # Basic slug generation from term if slug is not provided
        # A more robust slugifier might be needed (e.g., python-slugify)
        if v is None and 'term' in values:
            term_value = values['term']
            # Simple slug: lowercase, replace spaces with hyphens, remove special chars
            slug_candidate = term_value.lower().replace(' ', '-')
            slug_candidate = ''.join(e for e in slug_candidate if e.isalnum() or e == '-')
            return slug_candidate
        return v


class SessionSchema(BaseModel): # Updated
    id: str = Field(..., description="Unique identifier for the session")
    title: Optional[str] = Field(None, description="Optional title for the session")
    source: str = Field(..., description="Source of the session (e.g., 'youtube', 'mic')")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the session was created")
    summary: Optional[str] = Field(None, description="Optional summary of the session")

    youtube_url: Optional[str] = Field(None, description="URL of the YouTube video, if applicable")
    transcription_status: Optional[str] = Field(None, description="Status of transcription (e.g., pending, processing, completed, failed)")
    full_transcript_text: Optional[str] = Field(None, description="The full transcribed text, if available")

    nlp_status: Optional[str] = Field(None, description="Status of NLP processing (e.g., pending, nlp_processing, nlp_completed, nlp_failed)")

    transcript_ids: List[str] = Field(default_factory=list, description="List of IDs of transcript chunks for this session")
    keyword_ids: List[str] = Field(default_factory=list, description="List of IDs of keywords identified in this session (overall session keywords, distinct from chunk-specific keyword contexts)")


if __name__ == "__main__":
    # Example for KeywordSchema with new context
    kw_context_data = {
        "transcript_chunk_id": "chunk123",
        "context_preview": "This chunk talks about blockchain technology and its impact."
    }
    kw_data = {
        "id": "kw1",
        "term": "blockchain technology",
        "session_id": "sess456",
        "contexts": [kw_context_data],
        # slug will be auto-generated if not provided
    }
    try:
        kw_instance = KeywordSchema(**kw_data)
        print("Keyword instance with context created successfully:")
        print(kw_instance.model_dump_json(indent=2))
        assert kw_instance.slug == "blockchain-technology" # From auto-slugify
    except Exception as e:
        print(f"Error creating KeywordSchema instance: {e}")

    # Example for SessionSchema with new nlp_status
    sess_data = {
        "id": "sess789",
        "source": "youtube",
        "youtube_url": "http://youtube.com/...",
        "transcription_status": "completed",
        "nlp_status": "pending"
        # Note: createdAt will be auto-filled by default_factory
    }
    try:
        sess_instance = SessionSchema(**sess_data)
        print("\nSession instance with nlp_status created successfully:")
        print(sess_instance.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error creating SessionSchema instance: {e}")
