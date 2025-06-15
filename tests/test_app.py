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
