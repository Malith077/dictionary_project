import os
import json
# Attempt to import requests. This will only work if the environment has it installed.
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("WARNING (ollama_service): 'requests' library not found. Ollama API calls will not work.")
    REQUESTS_AVAILABLE = False

# --- Ollama Configuration ---
OLLAMA_HOST_DEFAULT = "http://localhost:11434"
OLLAMA_MODEL_DEFAULT = "deepseek-coder:6.7b" # User can override with e.g., deepseek-r1:8b

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", OLLAMA_HOST_DEFAULT)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL_DEFAULT)
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_HOST}/api/chat"

def generate_definition(keyword_term: str, context_text: str) -> str | None:
    """
    Generates a definition for a keyword given its context using a local Ollama model.

    Args:
        keyword_term (str): The keyword to define.
        context_text (str): The surrounding text context for the keyword.

    Returns:
        Optional[str]: The generated definition text, or None if an error occurs.
    """
    if not REQUESTS_AVAILABLE:
        print(f"Ollama Service: 'requests' library not available. Cannot generate definition for '{keyword_term}'.")
        # Simulate an error or return a placeholder if desired for environments without requests
        # For now, indicate failure clearly.
        # raise RuntimeError("requests library is not installed, cannot call Ollama API.")
        return f"Error: 'requests' library not installed. Definition for '{keyword_term}' not generated."


    system_prompt = "You are an expert lexicographer. Define the given keyword based on the provided context. Provide only the definition text, be concise and clear."
    user_prompt = f"Keyword: '{keyword_term}'\nContext: '{context_text}'\nDefine the keyword."

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False # We want the full response, not a stream
    }

    headers = {"Content-Type": "application/json"}

    print(f"Ollama Service: Requesting definition for '{keyword_term}' using model '{OLLAMA_MODEL}' at '{OLLAMA_CHAT_ENDPOINT}'. Context (first 100 chars): {context_text[:100]}...")

    try:
        response = requests.post(OLLAMA_CHAT_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=60) # 60s timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4XX or 5XX)

        response_data = response.json()

        # The structure of the response for /api/chat typically includes a 'message' object
        # with 'role': 'assistant' and 'content': 'the_definition_text'
        if response_data and "message" in response_data and "content" in response_data["message"]:
            definition_text = response_data["message"]["content"].strip()
            print(f"Ollama Service: Definition received for '{keyword_term}': {definition_text[:100]}...")
            return definition_text
        else:
            print(f"Ollama Service: Unexpected response structure from Ollama for '{keyword_term}'. Response: {response_data}")
            return None # Or a more specific error message / raise exception

    except requests.exceptions.RequestException as e:
        print(f"Ollama Service: HTTP Request error for '{keyword_term}': {e}")
        return None # Or raise to indicate failure to Celery task
    except json.JSONDecodeError as e:
        print(f"Ollama Service: Error decoding JSON response from Ollama for '{keyword_term}': {e}. Response text: {response.text[:200] if 'response' in locals() and hasattr(response, 'text') else 'Response text not available'}") # Ensure response exists before accessing .text
        return None
    except Exception as e:
        print(f"Ollama Service: An unexpected error occurred while generating definition for '{keyword_term}': {e}")
        return None

if __name__ == "__main__":
    print("Ollama Service module. For testing generate_definition (requires running Ollama & requests):")
    if REQUESTS_AVAILABLE:
        # Example usage (uncomment to test, ensure Ollama is running with the specified model)
        # test_keyword = "API"
        # test_context = "An API, or Application Programming Interface, is a set of rules that allows different software applications to communicate with each other. It defines the methods and data formats that applications can use to request and exchange information."
        # print(f"\nTesting definition generation for keyword: '{test_keyword}'")
        # definition = generate_definition(test_keyword, test_context)
        # if definition:
        #     print(f"Generated Definition: {definition}")
        # else:
        #     print("Failed to generate definition.")

        # print(f"\nTo use this service, ensure OLLAMA_HOST (default: {OLLAMA_HOST_DEFAULT}) and OLLAMA_MODEL (default: {OLLAMA_MODEL_DEFAULT}) are set correctly.")
        # print(f"Currently using OLLAMA_MODEL: {OLLAMA_MODEL}")
        pass
    else:
        print("Skipping example usage because 'requests' library is not available.")
