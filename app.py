import graphene
from flask import Flask
from flask_graphql import GraphQLView

# Define the GraphQL schema (as before)
class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    def resolve_hello(self, info, name):
        return f"Hello, {name}!"

schema = graphene.Schema(query=Query)

# Create the Flask app
app = Flask(__name__)

# Add the GraphQL endpoint
app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view(
        'graphql',
        schema=schema,
        graphiql=True  # Enable GraphiQL interface for easy testing in browser
    )
)

if __name__ == '__main__':
    app.run(port=3002)
