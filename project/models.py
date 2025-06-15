# Placeholder data structures / stubs
# In a real application, these would be SQLAlchemy models or similar.
from datetime import datetime

# Sample data (will be used by resolver stubs)
SESSIONS_DATA = {
    "1": {
        "id": "1", "title": "First Session", "source": "youtube",
        "createdAt": datetime.utcnow(), "transcript_ids": ["t1", "t2"],
        "keyword_ids": ["k1"], "summary": "This is a summary of the first session."
    },
    "2": {
        "id": "2", "title": "Second Session", "source": "mic",
        "createdAt": datetime.utcnow(), "transcript_ids": ["t3"],
        "keyword_ids": ["k2"], "summary": "Summary of the second session."
    }
}

TRANSCRIPT_CHUNKS_DATA = {
    "t1": {"id": "t1", "session_id": "1", "content": "Hello world, this is the first chunk.", "keyword_span_ids": ["ks1"]},
    "t2": {"id": "t2", "session_id": "1", "content": "Another part of the transcript.", "keyword_span_ids": []},
    "t3": {"id": "t3", "session_id": "2", "content": "Transcript for the second session.", "keyword_span_ids": ["ks2"]},
}

KEYWORDS_DATA = {
    "k1": {"id": "k1", "slug": "hello-world", "term": "Hello World", "session_id": "1", "definition_ids": ["d1"]},
    "k2": {"id": "k2", "slug": "another-keyword", "term": "Another Keyword", "session_id": "2", "definition_ids": []},
}

KEYWORD_SPANS_DATA = {
    "ks1": {"id": "ks1", "keyword_id": "k1", "startIndex": 0, "endIndex": 11},
    "ks2": {"id": "ks2", "keyword_id": "k2", "startIndex": 15, "endIndex": 30},
}

DEFINITIONS_DATA = {
    "d1": {"id": "d1", "keyword_id": "k1", "contextSummary": "Greeting", "definitionText": "A common greeting.", "createdAt": datetime.utcnow(), "modelUsed": "gpt-3.5-turbo"}
}

# Helper functions to simulate data fetching
def get_session_by_id(session_id):
    return SESSIONS_DATA.get(session_id)

def get_all_sessions():
    return list(SESSIONS_DATA.values())

def get_transcript_chunks_by_ids(ids):
    return [TRANSCRIPT_CHUNKS_DATA.get(id) for id in ids if id in TRANSCRIPT_CHUNKS_DATA]

def get_keywords_by_ids(ids):
    return [KEYWORDS_DATA.get(id) for id in ids if id in KEYWORDS_DATA]

def get_keyword_by_slug(slug):
    for kw in KEYWORDS_DATA.values():
        if kw["slug"] == slug:
            return kw
    return None

def search_keywords_by_term(term_str):
    results = []
    for kw in KEYWORDS_DATA.values():
        if term_str.lower() in kw["term"].lower():
            results.append(kw)
    return results

def get_keyword_spans_by_ids(ids):
    return [KEYWORD_SPANS_DATA.get(id) for id in ids if id in KEYWORD_SPANS_DATA]

def get_definitions_by_ids(ids):
    return [DEFINITIONS_DATA.get(id) for id in ids if id in DEFINITIONS_DATA]
