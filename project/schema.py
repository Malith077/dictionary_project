import graphene
from datetime import datetime
from .db import get_collection # Import MongoDB helper
# from bson import ObjectId # Uncomment if GraphQL IDs need to be MongoDB ObjectIds

# --- Graphene Type Definitions with MongoDB Resolvers ---

def map_document_id(doc):
    # Assuming 'id' field exists and is the correct string type.
    # If MongoDB uses _id (ObjectId or string), this function would handle mapping.
    # For example, if _id is ObjectId:
    # if doc and '_id' in doc and isinstance(doc['_id'], ObjectId):
    #    doc['id'] = str(doc['_id']) # Convert ObjectId to string for GraphQL ID
    # If _id is string and you want to use 'id' in GraphQL:
    # elif doc and '_id' in doc and 'id' not in doc:
    #    doc['id'] = doc['_id']
    return doc

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

class TranscriptChunk(graphene.ObjectType):
    class Meta:
        description = "A paragraph chunk of a transcript for rendering."
    id = graphene.ID(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session))
    content = graphene.String(required=True)
    keywordSpans = graphene.List(graphene.NonNull(KeywordSpan))

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_keywordSpans(self, info):
        # Assuming keywordSpans are stored as an array of embedded documents
        spans_data = self.get("keywordSpans", [])
        return [map_document_id(span) for span in spans_data if span]


class Definition(graphene.ObjectType):
    class Meta:
        description = "A definition for a keyword, including context and model used."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword))
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

class Keyword(graphene.ObjectType):
    class Meta:
        description = "Represents a keyword identified in a session."
    id = graphene.ID(required=True)
    slug = graphene.String(required=True)
    term = graphene.String(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session))
    definitions = graphene.List(graphene.NonNull(Definition))

    def resolve_session(self, info):
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_definitions(self, info):
        definition_ids = self.get("definition_ids", [])
        defs_collection = get_collection("definitions")
        definitions_data = [map_document_id(defs_collection.find_one({"id": def_id})) for def_id in definition_ids]
        return [d for d in definitions_data if d]


class Session(graphene.ObjectType): # UPDATED Session Graphene Type
    class Meta:
        description = "Represents a recorded or processed session."
    id = graphene.ID(required=True)
    title = graphene.String()
    source = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True)
    summary = graphene.String()

    # New fields for YouTube and transcription
    # These will map to MongoDB document fields like 'youtube_url', 'transcription_status', 'full_transcript_text'
    # Graphene's default resolver handles dict keys that are snake_case for camelCase fields.
    # Using 'name' makes it explicit if dict keys differ or specific GraphQL names are desired.
    youtubeUrl = graphene.String(name="youtube_url")
    transcriptionStatus = graphene.String(name="transcription_status")
    fullTranscriptText = graphene.String(name="full_transcript_text")

    transcript = graphene.List(graphene.NonNull(TranscriptChunk))
    keywords = graphene.List(graphene.NonNull(Keyword))

    # Default resolvers are used for youtubeUrl, transcriptionStatus, fullTranscriptText.
    # This means Graphene expects the resolved 'Session' object (a dict from MongoDB)
    # to have keys like 'youtube_url', 'transcription_status', 'full_transcript_text'.
    # The 'name' argument maps these dict keys to the camelCase GraphQL field names.

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

# --- Query Class with MongoDB Resolvers ---
class Query(graphene.ObjectType):
    # Argument 'name' was 'default_name' in prompt, using 'name_arg' for clarity if field is 'hello'
    # If GraphQL field is 'hello(default_name: "stranger")', then arg in resolver is 'default_name'.
    # Prompt: hello = graphene.String(name="default_name", default_value="stranger") - this makes the ARGUMENT 'default_name'.
    # The field itself is still 'hello'.
    hello = graphene.String(args={'name_arg': graphene.String(default_value="stranger")})

    session = graphene.Field(Session, id=graphene.ID(required=True))
    sessions = graphene.List(graphene.NonNull(Session))
    keyword_by_slug = graphene.Field(Keyword, slug=graphene.String(required=True))
    search_keyword = graphene.List(graphene.NonNull(Keyword), term=graphene.String(required=True))

    def resolve_hello(self, info, name_arg): # Argument name matches the key in 'args'
        return f"Hello, {name_arg}!"

    def resolve_session(self, info, id):
        sessions_collection = get_collection("sessions")
        session_doc = sessions_collection.find_one({"id": id})
        return map_document_id(session_doc)

    def resolve_sessions(self, info):
        sessions_collection = get_collection("sessions")
        return [map_document_id(doc) for doc in sessions_collection.find()]

    def resolve_keyword_by_slug(self, info, slug):
        keywords_collection = get_collection("keywords")
        keyword_doc = keywords_collection.find_one({"slug": slug})
        return map_document_id(keyword_doc)

    def resolve_search_keyword(self, info, term):
        keywords_collection = get_collection("keywords")
        query = {"term": {"$regex": term, "$options": "i"}}
        return [map_document_id(doc) for doc in keywords_collection.find(query)]

schema = graphene.Schema(query=Query)
