import graphene
from datetime import datetime
from .db import get_collection # Import MongoDB helper
# from bson import ObjectId # Uncomment if GraphQL IDs need to be MongoDB ObjectIds

# --- Graphene Type Definitions with MongoDB Resolvers ---

# Helper function to map MongoDB '_id' to 'id' if needed,
# and convert ObjectId to string if _id is ObjectId.
# For now, we assume 'id' is already a string field in the DB matching GraphQL ID.
# If _id is the primary key and is a string, this can be simpler.
# If _id is ObjectId, it MUST be converted to string for Graphene ID type.
def map_document_id(doc):
    if doc and '_id' in doc:
        # If _id is an ObjectId, convert to string and map to 'id'
        # from bson import ObjectId
        # if isinstance(doc['_id'], ObjectId):
        #     doc['id'] = str(doc['_id'])
        # elif not 'id' in doc: # if _id is string, and no 'id' field, map it
        #     doc['id'] = doc['_id']
        # For this pass, we assume 'id' field exists and is the correct string type.
        # If your DB uses string _id directly, you might not need 'id' field separately.
        # Let's assume documents have an 'id' field that matches the GraphQL ID.
        pass # No explicit mapping if 'id' field is already correct.
    return doc

class KeywordSpan(graphene.ObjectType):
    class Meta:
        description = "Defines the position of a keyword highlight within a transcript chunk."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword))
    startIndex = graphene.Int(required=True)
    endIndex = graphene.Int(required=True)

    def resolve_keyword(self, info):
        # 'self' is a dictionary from a keywordSpans document in MongoDB
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
    keywordSpans = graphene.List(graphene.NonNull(KeywordSpan), required=True) # This is an array of embedded documents or IDs

    def resolve_session(self, info):
        # 'self' is a TranscriptChunk document
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_keywordSpans(self, info):
        # 'self' is a TranscriptChunk document
        # Assuming keywordSpans are stored as an array of embedded documents in TranscriptChunk
        spans_data = self.get("keywordSpans", [])
        # If spans_data are just IDs, we would fetch them:
        # keyword_span_ids = self.get("keyword_span_ids", [])
        # spans_data = [map_document_id(get_collection("keywordSpans").find_one({"id": kid})) for kid in keyword_span_ids]
        return [map_document_id(span) for span in spans_data if span]


class Definition(graphene.ObjectType):
    class Meta:
        description = "A definition for a keyword, including context and model used."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword))
    contextSummary = graphene.String(required=True)
    definitionText = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True) # Ensure this is stored as datetime in MongoDB
    modelUsed = graphene.String(required=True)

    def resolve_keyword(self, info):
        # 'self' is a Definition document
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
    definitions = graphene.List(graphene.NonNull(Definition), required=True) # Array of IDs or embedded

    def resolve_session(self, info):
        # 'self' is a Keyword document
        session_id = self.get("session_id")
        if session_id:
            session_doc = get_collection("sessions").find_one({"id": session_id})
            return map_document_id(session_doc)
        return None

    def resolve_definitions(self, info):
        # 'self' is a Keyword document
        # Assuming definitions are stored as an array of embedded documents in Keyword
        # If they are IDs:
        definition_ids = self.get("definition_ids", [])
        defs_collection = get_collection("definitions")
        # Graphene expects a list of Definition-like dicts
        definitions_data = [map_document_id(defs_collection.find_one({"id": def_id})) for def_id in definition_ids]
        return [d for d in definitions_data if d]


class Session(graphene.ObjectType):
    class Meta:
        description = "Represents a recorded or processed session."
    id = graphene.ID(required=True)
    title = graphene.String()
    source = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True) # Ensure this is stored as datetime in MongoDB
    transcript = graphene.List(graphene.NonNull(TranscriptChunk), required=True) # Array of IDs or embedded
    keywords = graphene.List(graphene.NonNull(Keyword), required=True) # Array of IDs or embedded
    summary = graphene.String()

    def resolve_transcript(self, info):
        # 'self' is a Session document
        # Assuming transcript chunks are stored by IDs in the Session doc
        transcript_ids = self.get("transcript_ids", [])
        chunks_collection = get_collection("transcriptChunks")
        transcript_data = [map_document_id(chunks_collection.find_one({"id": t_id})) for t_id in transcript_ids]
        return [t for t in transcript_data if t]


    def resolve_keywords(self, info):
        # 'self' is a Session document
        keyword_ids = self.get("keyword_ids", [])
        keywords_collection = get_collection("keywords")
        keywords_data = [map_document_id(keywords_collection.find_one({"id": k_id})) for k_id in keyword_ids]
        return [k for k in keywords_data if k]

# --- Query Class with MongoDB Resolvers ---
class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    session = graphene.Field(Session, id=graphene.ID(required=True))
    sessions = graphene.List(graphene.NonNull(Session))
    keyword_by_slug = graphene.Field(Keyword, slug=graphene.String(required=True))
    search_keyword = graphene.List(graphene.NonNull(Keyword), term=graphene.String(required=True))

    def resolve_hello(self, info, name):
        return f"Hello, {name}!"

    def resolve_session(self, info, id):
        sessions_collection = get_collection("sessions")
        # Assuming 'id' is a queryable field in your MongoDB 'sessions' collection
        # If 'id' corresponds to MongoDB's '_id' and it's an ObjectId, you'd do:
        # from bson import ObjectId
        # session_doc = sessions_collection.find_one({"_id": ObjectId(id)})
        session_doc = sessions_collection.find_one({"id": id})
        return map_document_id(session_doc)

    def resolve_sessions(self, info):
        sessions_collection = get_collection("sessions")
        # Convert cursor to list and map IDs if necessary
        return [map_document_id(doc) for doc in sessions_collection.find()]

    def resolve_keyword_by_slug(self, info, slug):
        keywords_collection = get_collection("keywords")
        keyword_doc = keywords_collection.find_one({"slug": slug})
        return map_document_id(keyword_doc)

    def resolve_search_keyword(self, info, term):
        keywords_collection = get_collection("keywords")
        # Simple text search using regex. For more advanced search, MongoDB text indexes are better.
        # Ensure 'term' field is indexed for performance if using regex often.
        # Using 'i' for case-insensitive search
        query = {"term": {"$regex": term, "$options": "i"}}
        return [map_document_id(doc) for doc in keywords_collection.find(query)]

schema = graphene.Schema(query=Query)
