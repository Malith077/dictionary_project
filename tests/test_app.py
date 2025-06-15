import pytest
import json
from project.app import create_app # Import the create_app factory

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_graphql_hello_query(client):
    # Send a POST request to the /graphql endpoint
    response = client.post(
        '/graphql',
        data=json.dumps({
            "query": '{ hello(name: "TestUser") }'
        }),
        content_type='application/json'
    )

    # Check if the response status code is 200 (OK)
    assert response.status_code == 200

    # Parse the JSON response
    json_data = response.get_json()

    # Check if the data contains the expected greeting
    assert 'data' in json_data
    assert 'hello' in json_data['data']
    assert json_data['data']['hello'] == "Hello, TestUser!"

def test_graphiql_interface(client):
    # Send a GET request to the /graphql endpoint
    response = client.get('/graphql', headers={'Accept': 'text/html'})

    # Check if the response status code is 200 (OK)
    assert response.status_code == 200

    # Check if the response content type is HTML (indicating GraphiQL)
    assert 'text/html' in response.content_type
