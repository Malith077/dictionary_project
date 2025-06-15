import graphene
from datetime import datetime
from . import models # Import the placeholder data models

# --- Graphene Type Definitions with Resolvers ---

class KeywordSpan(graphene.ObjectType):
    class Meta:
        description = "Defines the position of a keyword highlight within a transcript chunk."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword)) # Use lambda for forward reference
    startIndex = graphene.Int(required=True)
    endIndex = graphene.Int(required=True)

    def resolve_keyword(self, info):
        # self is a dictionary from KEYWORD_SPANS_DATA
        keyword_data = models.KEYWORDS_DATA.get(self.get("keyword_id"))
        if keyword_data:
            # Need to resolve nested session for the keyword
            session_data = models.get_session_by_id(keyword_data.get("session_id"))
            if session_data:
                keyword_data["session_obj"] = session_data # Pass session object for Keyword resolver
            return keyword_data # Graphene will use Keyword's resolvers
        return None

class TranscriptChunk(graphene.ObjectType):
    class Meta:
        description = "A paragraph chunk of a transcript for rendering."
    id = graphene.ID(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session)) # Use lambda
    content = graphene.String(required=True)
    keywordSpans = graphene.List(graphene.NonNull(KeywordSpan), required=True)

    def resolve_session(self, info):
        # self is a dictionary from TRANSCRIPT_CHUNKS_DATA
        return models.get_session_by_id(self.get("session_id"))

    def resolve_keywordSpans(self, info):
        # self is a dictionary from TRANSCRIPT_CHUNKS_DATA
        return models.get_keyword_spans_by_ids(self.get("keyword_span_ids", []))

class Definition(graphene.ObjectType):
    class Meta:
        description = "A definition for a keyword, including context and model used."
    id = graphene.ID(required=True)
    keyword = graphene.Field(graphene.NonNull(lambda: Keyword)) # Use lambda
    contextSummary = graphene.String(required=True)
    definitionText = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True)
    modelUsed = graphene.String(required=True)

    def resolve_keyword(self, info):
        # self is a dictionary from DEFINITIONS_DATA
        keyword_data = models.KEYWORDS_DATA.get(self.get("keyword_id"))
        if keyword_data:
             # Need to resolve nested session for the keyword
            session_data = models.get_session_by_id(keyword_data.get("session_id"))
            if session_data:
                keyword_data["session_obj"] = session_data
            return keyword_data
        return None

class Keyword(graphene.ObjectType):
    class Meta:
        description = "Represents a keyword identified in a session."
    id = graphene.ID(required=True)
    slug = graphene.String(required=True)
    term = graphene.String(required=True)
    session = graphene.Field(graphene.NonNull(lambda: Session)) # Use lambda
    definitions = graphene.List(graphene.NonNull(Definition), required=True)

    def resolve_session(self, info):
        # self is a dictionary from KEYWORDS_DATA
        # If session_obj was pre-fetched (e.g. by KeywordSpan resolver), use it
        if "session_obj" in self:
            return self["session_obj"]
        return models.get_session_by_id(self.get("session_id"))

    def resolve_definitions(self, info):
        # self is a dictionary from KEYWORDS_DATA
        return models.get_definitions_by_ids(self.get("definition_ids", []))

class Session(graphene.ObjectType):
    class Meta:
        description = "Represents a recorded or processed session."
    id = graphene.ID(required=True)
    title = graphene.String()
    source = graphene.String(required=True)
    createdAt = graphene.DateTime(required=True)
    transcript = graphene.List(graphene.NonNull(TranscriptChunk), required=True)
    keywords = graphene.List(graphene.NonNull(Keyword), required=True)
    summary = graphene.String()

    def resolve_transcript(self, info):
        # self is a dictionary from SESSIONS_DATA
        return models.get_transcript_chunks_by_ids(self.get("transcript_ids", []))

    def resolve_keywords(self, info):
        # self is a dictionary from SESSIONS_DATA
        # For each keyword, we need to ensure its 'session' field can be resolved.
        # The Keyword.resolve_session will handle it, but we pass the parent session data
        # to avoid redundant lookups if possible (though models.py doesn't use it yet).
        keyword_data_list = models.get_keywords_by_ids(self.get("keyword_ids", []))
        for kw_data in keyword_data_list:
            kw_data["session_obj"] = self # Pass the parent session object
        return keyword_data_list

# --- Query Class with Resolvers ---
class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    session = graphene.Field(Session, id=graphene.ID(required=True))
    sessions = graphene.List(graphene.NonNull(Session))
    keyword_by_slug = graphene.Field(Keyword, slug=graphene.String(required=True))
    search_keyword = graphene.List(graphene.NonNull(Keyword), term=graphene.String(required=True))

    def resolve_hello(self, info, name):
        return f"Hello, {name}!"

    def resolve_session(self, info, id):
        return models.get_session_by_id(id)

    def resolve_sessions(self, info):
        return models.get_all_sessions()

    def resolve_keyword_by_slug(self, info, slug):
        keyword_data = models.get_keyword_by_slug(slug)
        if keyword_data:
            # Resolve the session for this keyword
            session_data = models.get_session_by_id(keyword_data.get("session_id"))
            if session_data:
                 # Attach session object to keyword data so Keyword.resolve_session can use it
                keyword_data["session_obj"] = session_data
        return keyword_data


    def resolve_search_keyword(self, info, term):
        results = models.search_keywords_by_term(term)
        for kw_data in results:
            # Resolve the session for each found keyword
            session_data = models.get_session_by_id(kw_data.get("session_id"))
            if session_data:
                kw_data["session_obj"] = session_data
        return results

schema = graphene.Schema(query=Query)
