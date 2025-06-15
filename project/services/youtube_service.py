# project/services/youtube_service.py

def handle_youtube_link(youtube_url: str, enhance_options: list):
    """
    Handles the logic for a submitted YouTube link.
    For now, it just logs the information and prepares data for the response.
    """
    print(f"[Service: YouTube] Received YouTube link: {youtube_url}")
    if enhance_options:
        print(f"[Service: YouTube] Enhance options: {enhance_options}")

    # In the future, this service would trigger actual processing,
    # e.g., downloading, transcription, etc.

    # Data to be returned for constructing the JSON response
    response_data = {
        "status": "success",
        "message": "YouTube link processed by service", # Changed message slightly for clarity
        "submitted_url": youtube_url,
        "processed_options": enhance_options
    }
    return response_data
