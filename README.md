# Agentforce Agent API - Custom Client POC

Internal proof-of-concept demonstrating how to build a custom client for Agentforce using the Agent API. This implementation shows OAuth 2.0 authentication, session management, and SSE streaming.

## What This Demonstrates

- Client credentials OAuth flow for server-to-server authentication
- Agent API session lifecycle (create, message, close)
- Server-Sent Events (SSE) for streaming agent responses
- Multi-turn conversations with session context
- Simple web UI for testing and validation

## Quick Start

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

> **Note**: On macOS, use `pip3` instead of `pip`

### 2. Configure Credentials

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` with your Salesforce credentials (see "Getting Your Credentials" section below).

### 3. Run the Application

```bash
python3 app.py
```

> **Note**: On macOS, use `python3` instead of `python`

### 4. Open in Browser

Navigate to `http://localhost:5000` to test the implementation.

## Configuration Setup

### Step 1: Find Your My Domain URL

1. Log into Salesforce
2. Go to **Setup** → **Company Settings** → **My Domain**
3. Copy your domain URL in the format: `yourcompany.my.salesforce.com`
4. ⚠️ **Important**: Use the `.my.salesforce.com` format, NOT `.lightning.force.com`

### Step 2: Create a Connected App (External Client App)

1. Go to **Setup** → **Apps** → **App Manager**
2. Click **New Connected App**
3. Fill in basic information:
   - **Connected App Name**: `Agent API Demo Client`
   - **API Name**: `Agent_API_Demo_Client`
   - **Contact Email**: Your email
4. Enable **OAuth Settings**:
   - **Callback URL**: `http://localhost:5000/callback` (required but not used)
   - Check **Enable OAuth Settings**
   - Check **Enable Client Credentials Flow**
   - Check **Issue JSON Web Token (JWT)**
5. **Selected OAuth Scopes** - Add these scopes:
   - `Access the identity URL service (id, profile, email, address, phone)`
   - `Manage user data via APIs (api)`
   - `Perform requests at any time (refresh_token, offline_access)`
   - `Access to Chatbot API (chatbot_api)`
   - `Access to Salesforce AI Platform API (sfap_api)`
6. Click **Save** and then **Continue**
7. Click **Manage Consumer Details** to view:
   - **Consumer Key** (this is your `SALESFORCE_CLIENT_ID`)
   - **Consumer Secret** (this is your `SALESFORCE_CLIENT_SECRET`)

### Step 3: Find Your Agent ID

⚠️ **Important**: The `SALESFORCE_AGENT_ID` is the **18-character Agent record ID**, NOT the API name or developer name. It always begins with the `0Xx` prefix (the 3-character entity prefix for Agent records).

**Example**: `0XxHs0000010p5vKAA`

**How to find it:**

**Option 1: Via Setup UI (Legacy Agentforce Builder)**
1. Go to **Setup** → **Agentforce Agents**
2. Click on your agent to view the Agent Overview Page
3. Look at the URL in your browser - the 18-character ID is at the end
4. Example URL: `https://yourcompany.salesforce-setup.com/lightning/setup/EinsteinCopilot/0XxSB000000IPCr0AO/edit`
5. The ID `0XxSB000000IPCr0AO` is your `SALESFORCE_AGENT_ID`

**Option 2: Via SOQL Query (New Agentforce Builder)**
1. Open Developer Console
2. Go to **Query Editor**
3. Run: `SELECT Id, DeveloperName, MasterLabel FROM BotDefinition WHERE DeveloperName = 'Your_Agent_Developer_Name'`
4. Use the `Id` value (18-character ID starting with `0Xx`) as your `SALESFORCE_AGENT_ID`

**Option 3: Check the URL in Agent Builder**
1. Open your agent in Agent Builder (legacy or new)
2. Look at the browser URL
3. The 18-character ID in the URL is your agent ID

### Step 4: Update Your .env File

```env
SALESFORCE_DOMAIN=yourcompany.my.salesforce.com
SALESFORCE_CLIENT_ID=3MVG9...your_consumer_key_here
SALESFORCE_CLIENT_SECRET=12345...your_consumer_secret_here
SALESFORCE_AGENT_ID=0XxHs0000010p5vKAA
```

## Project Structure

```
agent-api-poc/
├── .env                    # Your credentials (git-ignored)
├── .env.example           # Template for credentials
├── .gitignore            # Git ignore rules
├── requirements.txt      # Python dependencies
├── app.py               # Flask server + Agent API client
├── static/
│   └── index.html      # Chat UI
└── README.md           # This file
```

## How It Works

### Backend (`app.py`)

**SalesforceAuth Class**
- Manages OAuth 2.0 client credentials flow
- Caches access tokens (valid for ~2 hours)
- Automatically refreshes expired tokens

**AgentAPIClient Class**
- `start_session()` - Creates a new agent conversation session
- `send_message_streaming()` - Sends messages and streams responses via Server-Sent Events (SSE)
- `end_session()` - Terminates a session

**Flask Routes**
- `GET /` - Serves the chat UI
- `POST /api/start` - Starts a new agent session
- `POST /api/message` - Sends a message and streams the response
- `POST /api/end` - Ends the current session

### Frontend (`static/index.html`)

- Basic chat interface for testing
- Streams responses using Fetch API with SSE
- User messages (right, blue) / Agent messages (left, gray)
- Typing indicator during processing
- Session reset capability
- Auto-scroll to latest messages

## Troubleshooting

### 401 Unauthorized Error

**Possible causes:**
- Incorrect Client ID or Client Secret
- Missing OAuth scopes in Connected App
- Token has expired (should auto-refresh, but check logs)

**Solutions:**
- Verify your `.env` credentials match the Connected App
- Check that all required OAuth scopes are enabled
- Review the Connected App's "Manage Consumer Details"

### 404 Not Found Error

**Possible causes:**
- Incorrect Agent ID
- Wrong domain URL format
- Agent not deployed or not accessible

**Solutions:**
- Verify the Agent ID from Setup → Agents
- Ensure domain is `yourcompany.my.salesforce.com` format
- Check that the agent exists and is active
- Verify the "Run As" user has permission to access the agent

### 500 Internal Server Error

**Possible causes:**
- Agent type is "Agentforce (Default)" (not supported by Agent API)
- My Domain not configured correctly
- Agent processing timeout (>120 seconds)

**Solutions:**
- Use a custom agent type, not the default
- Verify My Domain is set up in Salesforce Setup
- Simplify agent logic if it's timing out
- Check Flask console logs for detailed error messages

### No Response from Agent

**Possible causes:**
- Network timeout
- Agent has no topics/actions configured
- Permission issues

**Solutions:**
- Check Flask console logs for errors
- Test the agent in Salesforce's Agent Builder first
- Verify the Connected App has proper permissions
- Ensure the agent has topics and can respond to messages

### Connection Errors

**Solutions:**
- Verify you're connected to the internet
- Check if Salesforce org is accessible
- Ensure firewall isn't blocking requests
- Try accessing your Salesforce domain in a browser

## API Reference

### Agent API Endpoints Used

**Start Session**
```
POST https://{domain}/services/agentforce/api/v1/sessions
```

**Send Message (Streaming)**
```
POST https://{domain}/services/agentforce/api/v1/sessions/{sessionId}/messages
Headers: Accept: text/event-stream
```

**End Session**
```
DELETE https://{domain}/services/agentforce/api/v1/sessions/{sessionId}
```

### Event Stream Types

When streaming responses, the API returns these event types:

- `TextChunk` - Partial agent response text
- `EndOfTurn` - Agent finished responding
- `ProgressIndicator` - Agent is processing
- `ValidationFailureChunk` - Validation error occurred

## Implementation Notes

**What's Included:**
- OAuth token caching (memory, ~2 hour TTL)
- Session management (in-memory, single user)
- SSE streaming implementation
- Basic error handling

**What's NOT Included (production requirements):**
- Persistent storage
- Multi-user support
- Rate limiting
- Comprehensive error handling
- Production security hardening
- Logging/monitoring

## Requirements

- Python 3.7+
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Active Salesforce org with Agentforce
- My Domain enabled
- Agent API access (requires appropriate licenses)

## Resources

- [Salesforce Agent API Documentation](https://developer.salesforce.com/docs/ai/agentforce/guide/agent-api-get-started.html)
- [OAuth 2.0 Client Credentials Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_client_credentials_flow.htm)
- [Creating Connected Apps](https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm)

## Notes

This is an internal POC for reference and testing purposes. Not intended for production use.
