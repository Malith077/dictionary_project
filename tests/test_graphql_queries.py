import pytest
import json
from project.app import create_app
from project.models import SESSIONS_DATA, KEYWORDS_DATA # For asserting against mock data

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def post_graphql_query(client, query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    return client.post(
        '/graphql',
        data=json.dumps(payload),
        content_type='application/json'
    )

# --- Test Cases ---

def test_query_session_by_id(client):
    query = """
        query GetSession($id: ID!) {
            session(id: $id) {
                id
                title
                source
                createdAt
                summary
                transcript {
                    id
                    content
                    keywordSpans {
                        id
                        startIndex
                        endIndex
                        keyword {
                            id
                            slug
                            term
                        }
                    }
                }
                keywords {
                    id
                    slug
                    term
                    definitions {
                        id
                        contextSummary
                        definitionText
                        modelUsed
                    }
                }
            }
        }
    """
    # Test with existing session "1"
    response = post_graphql_query(client, query, {"id": "1"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert 'session' in json_data['data']
    session_data = json_data['data']['session']

    assert session_data['id'] == "1"
    assert session_data['title'] == SESSIONS_DATA["1"]["title"]
    assert session_data['source'] == SESSIONS_DATA["1"]["source"]
    assert session_data['summary'] == SESSIONS_DATA["1"]["summary"]
    assert len(session_data['transcript']) == len(SESSIONS_DATA["1"]["transcript_ids"])
    assert len(session_data['keywords']) == len(SESSIONS_DATA["1"]["keyword_ids"])

    # Check a nested field
    assert session_data['transcript'][0]['id'] == "t1"
    assert session_data['keywords'][0]['id'] == "k1"
    assert session_data['keywords'][0]['definitions'][0]['id'] == "d1"
    assert session_data['transcript'][0]['keywordSpans'][0]['keyword']['slug'] == "hello-world"


    # Test with non-existing session "999"
    response_non_existent = post_graphql_query(client, query, {"id": "999"})
    assert response_non_existent.status_code == 200
    json_data_non_existent = response_non_existent.get_json()
    assert 'data' in json_data_non_existent
    assert json_data_non_existent['data']['session'] is None

def test_query_all_sessions(client):
    query = """
        query GetAllSessions {
            sessions {
                id
                title
            }
        }
    """
    response = post_graphql_query(client, query)
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert 'sessions' in json_data['data']
    sessions_list = json_data['data']['sessions']
    assert len(sessions_list) == len(SESSIONS_DATA)
    assert sessions_list[0]['id'] == "1" # Assuming order, or could check for presence of all IDs

def test_query_keyword_by_slug(client):
    query = """
        query GetKeywordBySlug($slug: String!) {
            keywordBySlug(slug: $slug) {
                id
                slug
                term
                session {
                    id
                    title
                }
                definitions {
                    id
                }
            }
        }
    """
    # Test with existing slug
    test_slug = "hello-world"
    keyword_mock = KEYWORDS_DATA["k1"] # k1 has slug "hello-world"
    response = post_graphql_query(client, query, {"slug": test_slug})
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    keyword_data = json_data['data']['keywordBySlug']
    assert keyword_data is not None
    assert keyword_data['id'] == keyword_mock["id"]
    assert keyword_data['slug'] == test_slug
    assert keyword_data['term'] == keyword_mock["term"]
    assert keyword_data['session']['id'] == keyword_mock["session_id"]
    assert len(keyword_data['definitions']) == len(keyword_mock["definition_ids"])

    # Test with non-existing slug
    response_non_existent = post_graphql_query(client, query, {"slug": "non-existent-slug"})
    assert response_non_existent.status_code == 200
    json_data_non_existent = response_non_existent.get_json()
    assert 'data' in json_data_non_existent
    assert json_data_non_existent['data']['keywordBySlug'] is None

def test_query_search_keyword(client):
    query = """
        query SearchKeywords($term: String!) {
            searchKeyword(term: $term) {
                id
                slug
                term
                session {
                    id
                }
            }
        }
    """
    # Test with term "Hello" (should match "Hello World")
    response = post_graphql_query(client, query, {"term": "Hello"})
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    keywords_list = json_data['data']['searchKeyword']
    assert len(keywords_list) == 1
    assert keywords_list[0]['slug'] == "hello-world"
    assert keywords_list[0]['session']['id'] == KEYWORDS_DATA["k1"]["session_id"]

    # Test with term "Key" (should match "Hello World" and "Another Keyword")
    response_multi = post_graphql_query(client, query, {"term": "Key"}) # "Keyword" is in "Another Keyword"
    assert response_multi.status_code == 200
    json_data_multi = response_multi.get_json()
    assert 'data' in json_data_multi
    keywords_list_multi = json_data_multi['data']['searchKeyword']
    assert len(keywords_list_multi) >= 1 # Should be 1 if "Another Keyword" is matched by "Key"
                                        # The mock search is simple. "Hello World" won't match "Key"
                                        # "Another Keyword" should match "Key"

    # Refined assertion for "Key" search:
    # Our mock search_keywords_by_term checks if `term_str.lower() in kw["term"].lower()`
    # "key" is in "another keyword"
    # "key" is not in "hello world"
    assert any(kw['slug'] == "another-keyword" for kw in keywords_list_multi)
    assert not any(kw['slug'] == "hello-world" for kw in keywords_list_multi)


    # Test with term "NonExistent"
    response_none = post_graphql_query(client, query, {"term": "NonExistentTermForSearch"})
    assert response_none.status_code == 200
    json_data_none = response_none.get_json()
    assert 'data' in json_data_none
    assert len(json_data_none['data']['searchKeyword']) == 0
