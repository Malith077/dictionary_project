import os
import chromadb # The main chromadb package
from typing import List, Optional # Added for type hinting consistency
# chromadb.Client() by default is an in-memory client.
# For persistence, chromadb.PersistentClient(path="...") is used.

# --- ChromaDB Client Configuration ---
CHROMA_DB_PATH_DEFAULT = "./chroma_db_store" # Store data in this directory
CHROMA_COLLECTION_NAME_DEFAULT = "transcript_embeddings"

CHROMA_DB_PATH = os.environ.get("CHROMA_DB_PATH", CHROMA_DB_PATH_DEFAULT)
CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", CHROMA_COLLECTION_NAME_DEFAULT)

# Initialize a persistent client.
# This client will create the directory if it doesn't exist.
# Ensure the directory is writable by the application.
try:
    # For chromadb versions 0.4.x and later, http client is also an option for server mode
    # client = chromadb.HttpClient(host='localhost', port=8000)
    # For local, persistent storage:
    persistent_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    print(f"ChromaDB PersistentClient initialized. Data will be stored in: {CHROMA_DB_PATH}")
except Exception as e:
    print(f"FATAL: Failed to initialize ChromaDB PersistentClient at path {CHROMA_DB_PATH}: {e}")
    print("Ensure the path is writable and chromadb is installed correctly.")
    # If client fails to init, subsequent calls will fail.
    # Application might need to handle this gracefully or exit.
    persistent_client = None

def get_chroma_collection(collection_name: str = CHROMA_COLLECTION_NAME):
    """
    Gets or creates a ChromaDB collection.
    """
    if persistent_client is None:
        raise ConnectionError("ChromaDB client is not initialized. Check logs for errors.")

    try:
        collection = persistent_client.get_or_create_collection(name=collection_name)
        # print(f"Successfully got or created ChromaDB collection: '{collection_name}'")
        return collection
    except Exception as e:
        # This might happen if there are issues with the DB connection even after client init,
        # or issues with collection creation (e.g. invalid name, though unlikely here).
        print(f"Error getting or creating ChromaDB collection '{collection_name}': {e}")
        raise # Re-raise for Celery task to handle as a failure

def add_chunk_embedding(session_id: str, chunk_id: str, chunk_text: str, embedding_vector: List[float], metadata: Optional[dict] = None):
    """
    Adds a transcript chunk's text, embedding, and metadata to the ChromaDB collection.

    Args:
        session_id (str): ID of the session this chunk belongs to.
        chunk_id (str): Unique ID of the transcript chunk.
        chunk_text (str): The text content of the chunk.
        embedding_vector (list): The sentence embedding vector for the chunk_text.
        metadata (Optional[dict]): Additional metadata to store with the embedding.
                                   session_id and chunk_text will be added automatically if not in metadata.
    """
    if not isinstance(embedding_vector, list) or not all(isinstance(n, (float, int)) for n in embedding_vector):
        print(f"Error: embedding_vector for chunk {chunk_id} is not a list of numbers.")
        # Decide if to raise an error or just log and skip. For now, log and skip.
        return False # Indicate failure

    collection = get_chroma_collection() # Get the default collection

    # ChromaDB `add` method arguments:
    # - ids: List of unique IDs for each document/embedding.
    # - embeddings: List of embedding vectors.
    # - metadatas: List of metadata dictionaries.
    # - documents: List of text documents (optional, but highly recommended for context).

    # Construct metadata
    doc_metadata = metadata if metadata is not None else {}
    # Ensure essential context is in metadata (ChromaDB allows filtering by metadata)
    doc_metadata["session_id"] = session_id
    doc_metadata["chunk_id"] = chunk_id
    # Storing chunk_text in 'documents' is better than in metadata if it's long,
    # but also useful in metadata for quick peeking or if 'documents' is not used for this.
    # For now, let's ensure it's in metadata for our own reference, Chroma will also get it via `documents` param.
    doc_metadata["chunk_text_preview"] = chunk_text[:256] # Store a preview in metadata

    try:
        # Using upsert is generally safer if you might re-process or update chunks
        collection.upsert(
            ids=[chunk_id], # Each chunk_id must be unique within the collection
            embeddings=[embedding_vector],
            metadatas=[doc_metadata],
            documents=[chunk_text] # Store the full chunk text as the document
        )
        # print(f"Added/Updated embedding for chunk_id: {chunk_id} (session: {session_id}) to ChromaDB.")
        return True # Indicate success
    except Exception as e:
        # This could be due to various reasons, e.g., data validation issues by ChromaDB,
        # or connection problems.
        print(f"Error adding/updating embedding for chunk_id {chunk_id} to ChromaDB: {e}")
        return False # Indicate failure


if __name__ == "__main__":
    # Example usage (requires ChromaDB to be installed and writable path)
    print("Attempting ChromaDB example usage...")
    if persistent_client is None:
        print("Cannot run ChromaDB example because client initialization failed.")
    else:
        try:
            # 1. Get/Create collection
            example_collection_name = "test_example_collection"
            example_collection = get_chroma_collection(example_collection_name)
            print(f"Test collection: {example_collection.name}, Count before add: {example_collection.count()}")

            # 2. Add an embedding
            sample_session = "session_test_001"
            sample_chunk = "chunk_test_001"
            sample_text = "This is a test sentence for ChromaDB."
            # Dummy embedding (replace with actual sentence-transformer embedding in real use)
            # all-MiniLM-L6-v2 produces 384-dimensional embeddings
            sample_embedding = [0.1] * 384 # Replace with actual embedding

            print(f"Adding sample embedding for chunk: {sample_chunk}")
            add_success = add_chunk_embedding(
                session_id=sample_session,
                chunk_id=sample_chunk,
                chunk_text=sample_text,
                embedding_vector=sample_embedding,
                metadata={"source": "if_name_main_test"}
            )
            if add_success:
                print(f"Sample embedding added/updated. Collection count: {example_collection.count()}")

                # 3. Query/Search (example)
                # This requires an embedding for the query text itself.
                # query_embedding = [0.12] * 384 # Embedding of a query like "test sentence"
                # results = example_collection.query(
                #     query_embeddings=[query_embedding],
                #     n_results=1
                # )
                # print(f"Query results: {results}")
            else:
                print("Failed to add sample embedding.")

            # Clean up: remove the test item (optional)
            # example_collection.delete(ids=[sample_chunk])
            # print(f"Deleted sample embedding. Collection count after delete: {example_collection.count()}")

            # Clean up: delete the test collection (optional)
            # persistent_client.delete_collection(example_collection_name) # This deletes the whole collection
            # print(f"Deleted test collection: {example_collection_name}")

        except Exception as e:
            print(f"Error during ChromaDB example usage: {e}")
