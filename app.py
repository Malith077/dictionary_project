from flask_sockets import Sockets # Import Sockets
from project.app import create_app
import os # Added for checking requirements.txt content

app = create_app() # Get the Flask app instance from our factory
sockets = Sockets(app) # Wrap the app with Sockets

@sockets.route('/api/mic-stream')
def mic_stream_socket(ws):
    # ws is a WebSocket object from gevent-websocket or a similar backend
    client_address = ws.handler.client_address if hasattr(ws, 'handler') and hasattr(ws.handler, 'client_address') else "Unknown"
    print(f"Client {client_address} connected to /api/mic-stream")
    try:
        while not ws.closed:
            message = ws.receive() # Receives a message (audio chunk)
            if message:
                # Assuming message is bytes (audio data)
                if isinstance(message, str):
                    print(f"Received text message on mic-stream (expected audio bytes): {message[:100]}...") # Log first 100 chars
                    # Optionally send an error back if text messages are not expected
                    # import json # Make sure json is imported if using this line
                    # ws.send(json.dumps({"error": "Expected binary audio data, received text."}))
                else: # Assuming binary data
                    print(f"Received audio chunk: {len(message)} bytes from {client_address}")
                # Mock behavior: No explicit ack unless error.
            else:
                # This typically means the client closed the connection gracefully from its end,
                # or an empty message was sent.
                print(f"Received empty message or client initiated close from {client_address}, closing socket.")
                break
    except Exception as e:
        # Log exceptions that occur during WebSocket communication
        # e.g., ConnectionClosed, WebSocketError from gevent-websocket
        print(f"Error on /api/mic-stream for client {client_address}: {e}")
        # No explicit error message sent back to client as per requirement ("send response only if there is an issue")
        # However, the exception itself might cause the socket to close, which the client would detect.
        # If we wanted to send an error:
        # try:
        #     import json # Make sure json is imported
        #     ws.send(json.dumps({"error": "An unexpected server error occurred."}))
        # except Exception as send_e:
        #     print(f"Failed to send error to client {client_address}: {send_e}")
    finally:
        if not ws.closed:
            ws.close() # Ensure the socket is closed on server side if loop exits for other reasons
        print(f"Client {client_address} disconnected from /api/mic-stream")


if __name__ == '__main__':
    # To run Flask with Flask-Sockets, we typically need a WSGI server that supports WebSockets,
    # like gevent. Flask's default development server (Werkzeug) does NOT natively support WebSockets.
    # The `app.run()` will serve HTTP, but `/api/mic-stream` might not work as a WebSocket.

    # For local development and testing Flask-Sockets, gevent is commonly used.
    # Example using gevent's WSGIServer:
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    print("Starting Flask app with gevent-websocket server on port 3002 for HTTP and WebSockets.")
    print("WebSocket endpoint available at ws://localhost:3002/api/mic-stream")

    # Ensure gevent and gevent-websocket are installed (they were as dependencies of Flask-Sockets)
    # This check is a bit redundant here as pip would have handled it, but kept from original plan
    try:
        with open('requirements.txt', 'r+') as f:
            content = f.read()
            needs_install = False
            if "gevent==" not in content: # Basic check, version might differ
                print("Adding gevent to requirements.txt")
                f.write("gevent==23.9.1\n") # Match version from previous install if possible, or use a known good one
                needs_install = True
            if "gevent-websocket==" not in content:
                print("Adding gevent-websocket to requirements.txt")
                f.write("gevent-websocket==0.10.1\n")
                needs_install = True
            # If this script were run standalone without outer pip install, this would be important
            # if needs_install:
            #     print("New WS dependencies added to requirements.txt, please re-run pip install -r requirements.txt and then run app.py")
            #     exit() # Or attempt to subprocess pip install here. For this tool, assume outer control.

    except FileNotFoundError:
        print("requirements.txt not found, cannot check/add gevent and gevent-websocket.")


    try:
        server = pywsgi.WSGIServer(('', 3002), app, handler_class=WebSocketHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user.")
    except Exception as e:
        print(f"Failed to start gevent server: {e}")
        print("Falling back to Flask default development server (WebSockets may not work).")
        print("Please ensure gevent and gevent-websocket are installed and functional for WebSocket support.")
        # Fallback to app.run() might not be ideal for production if WS is critical
        # For dev, it at least runs the HTTP parts.
        app.run(host='0.0.0.0', port=3002, debug=True)
