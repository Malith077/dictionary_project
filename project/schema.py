import graphene
from datetime import datetime
from .db import get_collection
# from bson import ObjectId # If using ObjectIds as primary keys

# --- Helper Functions ---
def map_document_id(doc):
    # Placeholder for ID mapping if MongoDB uses _id and GraphQL uses 'id'
    return doc

# --- Graphene ObjectType Definitions ---

# Forward declarations
class Session(graphene.ObjectType): pass
class Keyword(graphene.ObjectType): pass
class TranscriptChunk(graphene.ObjectType): pass
class Definition(graphene.ObjectType): pass
class KeywordContext(graphene.ObjectType): pass

class KeywordSpan(graphene.ObjectType):
    class Meta:
        description = "Defines the position of a keyword highlight within a transcript chunk."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword))
    startIndex = graphene.Int(required=True)
    endIndex = graphene.Int(required=True)

    def resolve_keyword(self, info):
        keyword_id = self.get("keyword_id")
        if keyword_id:
            return map_document_id(get_collection("keywords").find_one({"id": keyword_id}))
        return None

class TranscriptChunk(graphene.ObjectType):
    class Meta:
        description = "A segment of a transcript."
    id = graphene.ID(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session))
    content = graphene.String(required=True)
    startTime = graphene.Float(name="start_time", description="Start time in seconds.")
    endTime = graphene.Float(name="end_time", description="End time in seconds.")
    keywordSpans = graphene.List(graphene.NonNull(lambda: KeywordSpan))

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            return map_document_id(get_collection("sessions").find_one({"id": session_id}))
        return None

    def resolve_keywordSpans(self, info):
        spans_data = self.get("keywordSpans", [])
        return [map_document_id(span) for span in spans_data if span]

class KeywordContext(graphene.ObjectType):
    class Meta:
        description = "Context of a keyword occurrence."
    transcriptChunkId = graphene.ID(name="transcript_chunk_id", required=True)
    contextPreview = graphene.String(name="context_preview", required=True)
    transcriptChunk = graphene.Field(lambda: TranscriptChunk)

    def resolve_transcriptChunk(self, info):
        chunk_id = self.get("transcript_chunk_id")
        if chunk_id:
            return map_document_id(get_collection("transcriptChunks").find_one({"id": chunk_id}))
        return None

class Definition(graphene.ObjectType): # Updated for Phase 3
    class Meta:
        description = "A contextual definition for a keyword."
    id = graphene.ID(required=True)
    # keyword = graphene.Field(graphene.NonNull(lambda: Keyword)) # Link back to Keyword if needed
    contextPreview = graphene.String(name="context_preview", required=True, description="The text context provided to the LLM.")
    definitionText = graphene.String(name="definition_text", required=True, description="The generated definition.")
    createdAt = graphene.DateTime(name="created_at", required=True, description="Timestamp of definition creation.")
    llmModelIdentifier = graphene.String(name="llm_model_identifier", required=True, description="Identifier of the LLM model used.")

class Keyword(graphene.ObjectType):
    class Meta:
        description = "A keyword identified in a session."
    id = graphene.ID(required=True)
    term = graphene.String(required=True)
    slug = graphene.String(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session))
    contexts = graphene.List(graphene.NonNull(lambda: KeywordContext))
    definitions = graphene.List(graphene.NonNull(lambda: Definition))
    createdAt = graphene.DateTime(name="created_at")
    updatedAt = graphene.DateTime(name="updated_at")

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            return map_document_id(get_collection("sessions").find_one({"id": session_id}))
        return None

    def resolve_contexts(self, info):
        return self.get("contexts", [])

    def resolve_definitions(self, info):
        definition_ids = self.get("definition_ids", [])
        if not definition_ids:
            return []
        defs_collection = get_collection("definitions")
        definition_docs = list(defs_collection.find({"id": {"$in": definition_ids}}))
        return [map_document_id(doc) for doc in definition_docs]


class Session(graphene.ObjectType): # Updated for Phase 3
    class Meta:
        description = "Represents a recorded or processed session."
    id = graphene.ID(required=True)
    title = graphene.String()
    source = graphene.String(required=True)
    createdAt = graphene.DateTime(name="createdAt", required=True)
    summary = graphene.String()

    youtubeUrl = graphene.String(name="youtube_url")
    transcriptionStatus = graphene.String(name="transcription_status")
    fullTranscriptText = graphene.String(name="full_transcript_text")
    nlpStatus = graphene.String(name="nlp_status")
    definitionStatus = graphene.String(name="definition_status")

    transcript = graphene.List(graphene.NonNull(lambda: TranscriptChunk))
    keywords = graphene.List(graphene.NonNull(lambda: Keyword))

    def resolve_transcript(self, info):
        transcript_ids = self.get("transcript_ids", [])
        if not transcript_ids: return []
        return [map_document_id(doc) for doc in get_collection("transcriptChunks").find({"id": {"$in": transcript_ids}})]

    def resolve_keywords(self, info):
        # Fetch all keywords belonging to this session based on session_id stored on Keyword documents
        return [map_document_id(doc) for doc in get_collection("keywords").find({"session_id": self.get("id")})]


# --- Root Query Class ---
class Query(graphene.ObjectType):
    hello = graphene.String(args={'name_arg': graphene.String(default_value="stranger")})
    session = graphene.Field(Session, id=graphene.ID(required=True))
    sessions = graphene.List(graphene.NonNull(Session))
    keyword_by_slug = graphene.Field(Keyword, slug=graphene.String(required=True))
    search_keyword = graphene.List(graphene.NonNull(Keyword), term=graphene.String(required=True))

    def resolve_hello(self, info, name_arg):
        return f"Hello, {name_arg}!"

    def resolve_session(self, info, id):
        return map_document_id(get_collection("sessions").find_one({"id": id}))

    def resolve_sessions(self, info):
        return [map_document_id(doc) for doc in get_collection("sessions").find()]

    def resolve_keyword_by_slug(self, info, slug):
        return map_document_id(get_collection("keywords").find_one({"slug": slug}))

    def resolve_search_keyword(self, info, term):
        query = {"term": {"$regex": term, "$options": "i"}}
        return [map_document_id(doc) for doc in get_collection("keywords").find(query)]

schema = graphene.Schema(query=Query, types=[KeywordContext, Definition, KeywordSpan, TranscriptChunk, Keyword, Session])
