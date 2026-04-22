import os
import uuid
import json
import requests
from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)


class SalesforceAuth:
    """Handles OAuth authentication with Salesforce"""

    def __init__(self, domain, client_id, client_secret):
        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = None

    def get_access_token(self):
        """Get or refresh access token using client credentials flow"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        print(f"[AUTH] Getting new access token from {self.domain}")

        token_url = f"https://{self.domain}/services/oauth2/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            response = requests.post(token_url, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expiry = datetime.now() + timedelta(hours=2)

            print("[AUTH] Successfully obtained access token")
            return self.access_token

        except requests.exceptions.RequestException as e:
            print(f"[AUTH ERROR] Failed to get access token: {e}")
            raise


class AgentAPIClient:
    """Handles interactions with Salesforce Agent API"""

    def __init__(self, auth, domain, agent_id):
        self.auth = auth
        self.domain = domain
        self.agent_id = agent_id
        self.base_url = "https://api.salesforce.com/einstein/ai-agent/v1"
        self.current_session_id = None
        self.sequence_id = 0

    def _get_headers(self, streaming=False):
        """Generate headers for API requests"""
        headers = {
            'Authorization': f'Bearer {self.auth.get_access_token()}',
            'Content-Type': 'application/json'
        }
        if streaming:
            headers['Accept'] = 'text/event-stream'
        return headers

    def start_session(self):
        """Start a new agent session"""
        session_key = str(uuid.uuid4())
        url = f"{self.base_url}/agents/{self.agent_id}/sessions"

        payload = {
            'externalSessionKey': session_key,
            'instanceConfig': {
                'endpoint': f'https://{self.domain}'
            },
            'streamingCapabilities': {
                'chunkTypes': ['Text']
            }
        }

        print(f"[SESSION] Starting new session with key: {session_key}")

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=120
            )
            response.raise_for_status()

            data = response.json()
            self.current_session_id = data.get('sessionId')
            self.sequence_id = 0

            print(f"[SESSION] Created session: {self.current_session_id}")
            return self.current_session_id

        except requests.exceptions.RequestException as e:
            print(f"[SESSION ERROR] Failed to start session: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[SESSION ERROR] Response: {e.response.text}")
            raise

    def send_message_streaming(self, session_id, message):
        """Send a message and stream the response"""
        self.sequence_id += 1
        url = f"https://api.salesforce.com/einstein/ai-agent/v1/sessions/{session_id}/messages/stream"

        payload = {
            'message': {
                'sequenceId': self.sequence_id,
                'type': 'Text',
                'text': message
            },
            'variables': []
        }

        print(f"[MESSAGE] Sending message (seq: {self.sequence_id}): {message[:50]}...")

        try:
            response = requests.post(
                url,
                headers=self._get_headers(streaming=True),
                json=payload,
                timeout=120,
                stream=True
            )
            response.raise_for_status()

            return response

        except requests.exceptions.RequestException as e:
            print(f"[MESSAGE ERROR] Failed to send message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[MESSAGE ERROR] Response: {e.response.text}")
            raise

    def end_session(self, session_id):
        """End an agent session"""
        url = f"https://api.salesforce.com/einstein/ai-agent/v1/sessions/{session_id}"

        print(f"[SESSION] Ending session: {session_id}")

        try:
            response = requests.delete(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            print("[SESSION] Session ended successfully")

        except requests.exceptions.RequestException as e:
            print(f"[SESSION ERROR] Failed to end session: {e}")


# Initialize auth and client
auth = SalesforceAuth(
    domain=os.getenv('SALESFORCE_DOMAIN'),
    client_id=os.getenv('SALESFORCE_CLIENT_ID'),
    client_secret=os.getenv('SALESFORCE_CLIENT_SECRET')
)

agent_client = AgentAPIClient(
    auth=auth,
    domain=os.getenv('SALESFORCE_DOMAIN'),
    agent_id=os.getenv('SALESFORCE_AGENT_ID')
)


@app.route('/')
def index():
    """Serve the main chat UI"""
    return send_from_directory('static', 'index.html')


@app.route('/api/start', methods=['POST'])
def start_session():
    """Start a new agent session"""
    try:
        session_id = agent_client.start_session()
        return jsonify({'sessionId': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/message', methods=['POST'])
def send_message():
    """Send a message and stream the response"""
    try:
        data = request.json
        session_id = data.get('sessionId')
        message = data.get('message')

        if not session_id or not message:
            return jsonify({'error': 'Missing sessionId or message'}), 400

        response = agent_client.send_message_streaming(session_id, message)

        def generate():
            """Parse SSE stream and forward to client"""
            current_event = None
            has_sent_data = False

            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')

                    if line_str.startswith('event: '):
                        current_event = line_str[7:].strip()
                        print(f"[STREAM] Event type: {current_event}")

                    elif line_str.startswith('data: '):
                        data_str = line_str[6:]

                        try:
                            event_data = json.loads(data_str)
                            print(f"[STREAM] Data: {json.dumps(event_data, indent=2)}")

                            message_data = event_data.get('message', {})
                            msg_type = message_data.get('type')

                            if current_event == 'TEXT_CHUNK' or msg_type == 'TextChunk':
                                # Try multiple possible fields for the text content
                                text = (message_data.get('message') or
                                       message_data.get('text') or
                                       message_data.get('content') or '')
                                if text:
                                    print(f"[STREAM] Sending text chunk: {text[:50]}...")
                                    has_sent_data = True
                                    yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                                else:
                                    print(f"[STREAM] TEXT_CHUNK with no text found in: {message_data}")

                            elif current_event == 'INFORM' or msg_type == 'Inform':
                                # Handle Inform messages with results
                                text = message_data.get('message', '')
                                result_data = message_data.get('result', [])

                                # Build the full response text
                                response_text = text
                                if result_data:
                                    for item in result_data:
                                        if isinstance(item, dict) and 'value' in item:
                                            value = item['value']
                                            if isinstance(value, dict) and 'result' in value:
                                                response_text += f"\n{value['result']}"

                                if response_text:
                                    print(f"[STREAM] Sending inform message: {response_text[:100]}...")
                                    has_sent_data = True
                                    yield f"data: {json.dumps({'type': 'chunk', 'text': response_text})}\n\n"

                            elif current_event == 'END_OF_TURN' or msg_type == 'EndOfTurn':
                                print("[STREAM] End of turn")
                                yield f"data: {json.dumps({'type': 'end'})}\n\n"

                            elif msg_type == 'ProgressIndicator':
                                print("[STREAM] Progress indicator")
                                yield f"data: {json.dumps({'type': 'progress'})}\n\n"

                        except json.JSONDecodeError as e:
                            print(f"[STREAM ERROR] JSON decode error: {e}")
                            pass

            if not has_sent_data:
                print("[STREAM WARNING] Stream ended without sending any text chunks")

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print(f"[API ERROR] {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/end', methods=['POST'])
def end_session():
    """End the current session"""
    try:
        data = request.json
        session_id = data.get('sessionId')

        if not session_id:
            return jsonify({'error': 'Missing sessionId'}), 400

        agent_client.end_session(session_id)
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Salesforce Agent API Demo Client")
    print("=" * 60)
    print(f"Domain: {os.getenv('SALESFORCE_DOMAIN')}")
    print(f"Agent ID: {os.getenv('SALESFORCE_AGENT_ID')}")
    print("=" * 60)
    print("Starting server at http://localhost:5000")
    print("=" * 60)

    app.run(debug=True, port=5000)
