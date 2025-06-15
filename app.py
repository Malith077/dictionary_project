from flask_sockets import Sockets
from project.app import create_app
from project.services import mic_service # Import the mic_service module
import json # For potentially sending JSON error messages back

app = create_app()
sockets = Sockets(app)

@sockets.route('/api/mic-stream')
def mic_stream_socket(ws):
    client_address = ws.handler.client_address if hasattr(ws, 'handler') and hasattr(ws.handler, 'client_address') else "Unknown"

    mic_service.log_client_connection(client_address) # Call service function

    try:
        while not ws.closed:
            message = ws.receive()
            if message:
                # Delegate message handling to the service
                mic_service.handle_mic_message(client_address, message)
                # As per requirement, only send response if there is an issue.
                # The service function currently only logs. If it were to return an error status/message:
                # error_response = mic_service.handle_mic_message(client_address, message)
                # if error_response and ws and not ws.closed:
                #    ws.send(json.dumps(error_response))
            else:
                # Client initiated close or empty message
                print(f"WebSocket: Received empty message or client initiated close from {client_address}, closing socket on server side.")
                break
    except Exception as e:
        print(f"WebSocket: Error on /api/mic-stream for client {client_address}: {e}")
        # Example of sending an error to the client if an unexpected server error occurs
        # This part fulfills the "send response only if there is an issue" for server-side exceptions
        if ws and not ws.closed:
            try:
                ws.send(json.dumps({"type": "error", "message": "An unexpected server error occurred processing your request."}))
            except Exception as send_e:
                print(f"WebSocket: Failed to send error message to client {client_address}: {send_e}")
    finally:
        if not ws.closed:
            ws.close()
        mic_service.log_client_disconnection(client_address) # Call service function

if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    print("Starting Flask app with gevent-websocket server on port 3002 for HTTP and WebSockets.")
    print("WebSocket endpoint available at ws://localhost:3002/api/mic-stream")

    # Ensure gevent and gevent-websocket are installed (already handled in previous steps)
    try:
        server = pywsgi.WSGIServer(('', 3002), app, handler_class=WebSocketHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user.")
    except Exception as e:
        print(f"Failed to start gevent server: {e}")
        print("Falling back to Flask default development server (WebSockets may not work).")
        print("Please ensure gevent and gevent-websocket are installed for WebSocket support.")
        app.run(host='0.0.0.0', port=3002, debug=True) # Fallback, debug=True might be too verbose for this stage
