import pytest # Required for fixtures
import json
# client fixture is now from conftest.py

def test_graphql_hello_query(client): # client fixture from conftest.py
    response = client.post(
        '/graphql',
        data=json.dumps({
            "query": "{ hello(name: \"TestUser\") }" # Escaped quotes for JSON within bash heredoc
        }),
        content_type='application/json'
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert 'hello' in json_data['data']
    assert json_data['data']['hello'] == "Hello, TestUser!"

def test_graphiql_interface(client): # client fixture from conftest.py
    response = client.get('/graphql', headers={"Accept": "text/html"}) # Ensure Accept header
    assert response.status_code == 200
    assert 'text/html' in response.content_type

def test_submit_youtube_link_success(client):
    """Test the /api/youtube-link endpoint with valid data."""
    payload = {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "enhance_options": ["transcript", "summary"]
    }
    response = client.post('/api/youtube-link', json=payload) # Use json=payload for Flask test client

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["message"] == "YouTube link received"
    assert json_data["submitted_url"] == payload["youtube_url"]
    assert json_data["processed_options"] == payload["enhance_options"]

def test_submit_youtube_link_missing_url(client):
    """Test the /api/youtube-link endpoint with missing youtube_url."""
    payload = {"enhance_options": ["transcript"]}
    response = client.post('/api/youtube-link', json=payload)

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["message"] == "Missing 'youtube_url' in request body"

def test_submit_youtube_link_not_json(client):
    """Test the /api/youtube-link endpoint with non-JSON data."""
    response = client.post('/api/youtube-link', data="not a json string") # Sending plain text

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["status"] == "error"
    assert json_data["message"] == "Request must be JSON"
