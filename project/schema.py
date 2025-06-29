import graphene
from datetime import datetime
from .db import get_collection
# from bson import ObjectId # If using ObjectIds as primary keys

# --- Helper Functions ---
def map_document_id(doc):
    # Placeholder for ID mapping if MongoDB uses _id and GraphQL uses 'id'
    # For now, assumes 'id' field exists as a string in the document.
    return doc

# --- Graphene ObjectType Definitions ---

# Forward declarations for types that might be referenced before definition (using lambda)
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
            keyword_doc = get_collection("keywords").find_one({"id": keyword_id})
            return map_document_id(keyword_doc)
        return None

class TranscriptChunk(graphene.ObjectType): # Updated
    class Meta:
        description = "A segment of a transcript, typically corresponding to a sentence or short audio passage."
    id = graphene.ID(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session)) # Corrected lambda usage
    content = graphene.String(required=True)

    startTime = graphene.Float(name="start_time", description="Start time of the chunk in seconds.")
    endTime = graphene.Float(name="end_time", description="End time of the chunk in seconds.")

    keywordSpans = graphene.List(graphene.NonNull(lambda: KeywordSpan)) # Corrected lambda usage

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_keywordSpans(self, info):
        spans_data = self.get("keywordSpans", [])
        return [map_document_id(span) for span in spans_data if span]

class KeywordContext(graphene.ObjectType): # New
    class Meta:
        description = "Describes a specific context in which a keyword appears within a transcript."
    transcriptChunkId = graphene.ID(name="transcript_chunk_id", required=True)
    contextPreview = graphene.String(name="context_preview", required=True)

    transcriptChunk = graphene.Field(lambda: TranscriptChunk) # Corrected lambda usage

    def resolve_transcriptChunk(self, info):
        chunk_id = self.get("transcript_chunk_id")
        if chunk_id:
            chunk_doc = get_collection("transcriptChunks").find_one({"id": chunk_id})
            return map_document_id(chunk_doc)
        return None


class Definition(graphene.ObjectType):
    class Meta:
        description = "A definition for a keyword."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword)) # Corrected lambda usage
    contextSummary = graphene.String(required=True)
    definitionText = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True)
    modelUsed = graphene.String(required=True)

    def resolve_keyword(self, info):
        keyword_id = self.get("keyword_id")
        if keyword_id:
            keyword_doc = get_collection("keywords").find_one({"id": keyword_id})
            return map_document_id(keyword_doc)
        return None

class Keyword(graphene.ObjectType): # Updated
    class Meta:
        description = "Represents a keyword identified in a session, with its various contexts."
    id = graphene.ID(required=True)
    term = graphene.String(required=True)
    slug = graphene.String(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session), description="The session this keyword belongs to.") # Corrected lambda usage

    contexts = graphene.List(graphene.NonNull(lambda: KeywordContext), description="List of contexts where this keyword appears.") # Corrected lambda usage

    definitions = graphene.List(graphene.NonNull(lambda: Definition)) # Corrected lambda usage

    createdAt = graphene.DateTime(name="created_at")
    updatedAt = graphene.DateTime(name="updated_at")

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_contexts(self, info):
        return self.get("contexts", [])

    def resolve_definitions(self, info):
        definition_ids = self.get("definition_ids", [])
        defs_collection = get_collection("definitions")
        definitions_data = [map_document_id(defs_collection.find_one({"id": def_id})) for def_id in definition_ids]
        return [d for d in definitions_data if d]

class Session(graphene.ObjectType): # Updated
    class Meta:
        description = "Represents a recorded or processed session."
    id = graphene.ID(required=True)
    title = graphene.String()
    source = graphene.String(required=True)
    createdAt = graphene.DateTime(name="createdAt", required=True) # Explicit name mapping for consistency
    summary = graphene.String()

    youtubeUrl = graphene.String(name="youtube_url")
    transcriptionStatus = graphene.String(name="transcription_status")
    fullTranscriptText = graphene.String(name="full_transcript_text")
    nlpStatus = graphene.String(name="nlp_status")

    transcript = graphene.List(graphene.NonNull(lambda: TranscriptChunk)) # Corrected lambda usage
    keywords = graphene.List(graphene.NonNull(lambda: Keyword)) # Corrected lambda usage


    def resolve_transcript(self, info):
        transcript_ids = self.get("transcript_ids", [])
        chunks_collection = get_collection("transcriptChunks")
        transcript_data = [map_document_id(chunks_collection.find_one({"id": t_id})) for t_id in transcript_ids]
        return [t for t in transcript_data if t]

    def resolve_keywords(self, info):
        keyword_ids = self.get("keyword_ids", [])
        keywords_collection = get_collection("keywords")
        keywords_data = [map_document_id(keywords_collection.find_one({"id": k_id})) for k_id in keyword_ids]
        return [k for k in keywords_data if k]

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

schema = graphene.Schema(query=Query, types=[KeywordContext, TranscriptChunk, Keyword, Session, Definition, KeywordSpan])
