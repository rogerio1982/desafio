# 3D Digital Showroom — Conversational AI System

A production-ready multi-agent conversational AI for a 3D digital car showroom.



### Tools and Technologies

- **Python 3.11+ (async throughout):**
    - The entire backend is asynchronous, leveraging the best performance of modern Python.

- **OpenAI Agents SDK (`openai-agents`):**
    - Multi-agent orchestration layer, making it easy to create, execute, and handoff between specialized agents.

- **OpenAI Vector Store + FileSearchTool:**
    - All Retrieval-Augmented Generation (RAG) is performed via semantic search on local or hosted embeddings.

- **OpenAI Realtime API (wss://api.openai.com/v1/realtime):**
    - The system's voice channel, enabling real-time conversation via WebSocket.


Here's the application flow from the moment the user makes a request until the final response:

1. User sends a request (e.g., POST /chat) with a message.
2. The FastAPI API (app/api/server.py and router.py) receives the request.
3. The message is forwarded to the orchestrator (core/orchestrator.py), which centralizes the flow.
4. The orchestrator calls the intent classifier (core/intents.py) to identify the type of user request (e.g., product information, layout, purchase, voice, or human assistance).
5. Depending on the intent:
• If it's a question about products, space, or purchase, the orchestrator triggers the corresponding agent (app/agents/), which can use the RAG module (rag/retriever.py) to retrieve information from the data files (data/).

• If it's a voice request, it triggers the voice agent (app/agents/voice.py). 

• If it's a human support request, it triggers the escalation agent.

6. The agent processes the request, queries data if necessary, and returns a structured response.
7. The orchestrator assembles the final response in JSON format, including message, channel (text, voice, escalation), intent, and session_id.
8. The API returns this response to the user.

In summary: User → API → Orchestrator → Intent classifier → Specialized agent (can use RAG/data) → Orchestrator → API → User.



## Quick Start

### 1. Prerequisites

- Python 3.11 or higher
- An OpenAI API key (platform.openai.com)

### 2. Install dependencies

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set your API key

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-...your-key-here...
VECTOR_STORE_ID=
```

### 4. (Optional) Create the OpenAI Vector Store

The system works out of the box using local embedding-based RAG.
If you also want to use OpenAI's hosted **FileSearchTool**, run this once:

```bash
python scripts/setup_vector_store.py
```

This uploads the three knowledge-base files to an OpenAI Vector Store and saves
the resulting `VECTOR_STORE_ID` to `.env` automatically.
**Skip this step if you just want to run the system** — local RAG is the default and requires no extra setup.

### 5. Start the server

```bash
uvicorn app.api.server:app --reload
```

The server starts at `http://127.0.0.1:8000`.

### 6. Run tests

```bash
# All 5 intents — verifies RAG, routing, JSON schema, and memory
python tests/test_all_intents.py

# Single HTTP request (server must be running)
python tests/test_chat.py
```
