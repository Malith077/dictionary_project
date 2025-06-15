# project/services/mic_service.py

def log_client_connection(client_address):
    """Logs a new client connection to the WebSocket."""
    print(f"[Service: MicStream] Client {client_address} connected.")

def log_client_disconnection(client_address):
    """Logs a client disconnection from the WebSocket."""
    print(f"[Service: MicStream] Client {client_address} disconnected.")

def handle_mic_message(client_address, message_data):
    """
    Handles an incoming message (audio chunk) from the WebSocket.
    For now, it just logs the size of the received data.
    """
    if isinstance(message_data, str):
        print(f"[Service: MicStream] Received text message from {client_address}: {message_data[:100]}...")
        # Here you could return an error structure if text is not expected,
        # which the WebSocket handler in app.py could then send.
        # For now, per requirement, only send back on error, this is just logging.
    elif isinstance(message_data, bytes):
        print(f"[Service: MicStream] Received audio chunk: {len(message_data)} bytes from {client_address}.")
    else:
        print(f"[Service: MicStream] Received message of unexpected type ({type(message_data)}) from {client_address}.")

    # This service function itself doesn't send data back to the WebSocket client.
    # It processes/logs and could return data for the main WebSocket handler to decide what to do.
    # For now, it doesn't need to return anything.
