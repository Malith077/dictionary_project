from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# Pydantic models define the expected structure for MongoDB documents.
# These serve as explicit schemas at the application level.

class KeywordSpanSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the keyword span")
    keyword_id: str = Field(..., description="Identifier of the associated keyword")
    startIndex: int = Field(..., description="Start index of the keyword in the content")
    endIndex: int = Field(..., description="End index of the keyword in the content")

class TranscriptChunkSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the transcript chunk")
    session_id: str = Field(..., description="Identifier of the parent session")
    content: str = Field(..., description="Text content of the transcript chunk")
    keywordSpans: List[KeywordSpanSchema] = Field(default_factory=list, description="List of keyword spans within this chunk")

class DefinitionSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the definition")
    keyword_id: str = Field(..., description="Identifier of the associated keyword")
    contextSummary: str = Field(..., description="Summary of the context in which the keyword was defined")
    definitionText: str = Field(..., description="The generated definition text")
    createdAt: datetime = Field(..., description="Timestamp of when the definition was created")
    modelUsed: str = Field(..., description="Identifier of the LLM model used to generate the definition")

class KeywordSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the keyword")
    slug: str = Field(..., description="URL-safe unique slug for the keyword")
    term: str = Field(..., description="The keyword term itself")
    session_id: str = Field(..., description="Identifier of the session where this keyword was identified")
    definition_ids: List[str] = Field(default_factory=list, description="List of IDs of definitions for this keyword")

class SessionSchema(BaseModel): # Updated SessionSchema
    id: str = Field(..., description="Unique identifier for the session")
    title: Optional[str] = Field(None, description="Optional title for the session")
    source: str = Field(..., description="Source of the session (e.g., 'youtube', 'mic')")
    createdAt: datetime = Field(..., description="Timestamp of when the session was created")
    summary: Optional[str] = Field(None, description="Optional summary of the session")

    youtube_url: Optional[str] = Field(None, description="URL of the YouTube video, if applicable")
    transcription_status: Optional[str] = Field(None, description="Status of transcription (e.g., pending, processing, completed, failed)")
    full_transcript_text: Optional[str] = Field(None, description="The full transcribed text, if available")

    # Existing fields for relationships
    transcript_ids: List[str] = Field(default_factory=list, description="List of IDs of transcript chunks for this session")
    keyword_ids: List[str] = Field(default_factory=list, description="List of IDs of keywords identified in this session")

# Example of how these models could be used (for illustration, not part of the app logic here):
if __name__ == "__main__":
    sample_session_data = {
        "id": "session123",
        "source": "youtube",
        "createdAt": datetime.now(),
        "transcript_ids": ["chunk1", "chunk2"],
        "keyword_ids": ["keywordA"],
        "title": "My First Session",
        "youtube_url": "https://youtube.com/watch?v=example",
        "transcription_status": "pending"
    }
    try:
        session_instance = SessionSchema(**sample_session_data)
        print("Session instance created successfully:")
        print(session_instance.model_dump_json(indent=2))
        assert session_instance.youtube_url == "https://youtube.com/watch?v=example"
        assert session_instance.full_transcript_text is None

    except Exception as e:
        print(f"Error creating Pydantic model instance: {e}")

    sample_chunk_data = {
        "id": "chunk1",
        "session_id": "session123",
        "content": "This is a sample transcript chunk.",
        "keywordSpans": [
            {"id": "span1", "keyword_id": "keyA", "startIndex": 10, "endIndex": 16}
        ]
    }
    try:
        chunk_instance = TranscriptChunkSchema(**sample_chunk_data)
        print("\nTranscriptChunk instance created successfully:")
        print(chunk_instance.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error creating Pydantic model instance: {e}")
