# 3D Digital Showroom — Conversational AI System

A production-ready multi-agent conversational AI for a 3D digital car showroom.

## Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+, fully async |
| Agent orchestration | **OpenAI Agents SDK** (`openai-agents`) — `Agent`, `Runner`, `FileSearchTool`, `handoff` |
| RAG retrieval | Local semantic search via `text-embedding-3-small` + **FileSearchTool** over OpenAI Vector Store |
| Voice channel | **OpenAI Realtime API** (`wss://api.openai.com/v1/realtime`) with graceful fallback |
| API server | FastAPI + Uvicorn |

## Architecture

```
POST /chat
    │
    ▼
Intent Classifier (keyword-first → GPT-4o-mini fallback)
    │
    ├── RAG: text-embedding-3-small semantic search over knowledge base files
    │         (injected as context for Product Info, Space Analysis, Purchase Intent)
    │
    ▼
OpenAI Agents SDK — Runner.run(specialist_agent, context + message)
    ├── Product Info Agent    ──► vehicle_catalog.txt
    ├── Space Analysis Agent  ──► showroom_layouts.txt
    ├── Purchase Intent Agent ──► dealership_faq.txt  ──► (handoff) Escalation Agent
    ├── Voice Agent           ──► OpenAI Realtime API (WebSocket session)
    └── Escalation Agent      ──► Human handoff
    │
    ▼
Structured JSON Response
{
  "message_agent": "...",
  "channel": "text | voice | escalation",
  "intent":   "Product Info | Space Analysis | Purchase Intent | Voice Request | Escalation",
  "session_id": "..."
}
```

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

## API

**POST** `/chat`

**Request body:**
```json
{
  "message": "Tell me about your electric vehicles",
  "session_id": "user-abc-123"
}
```

**Response (always this schema):**
```json
{
  "message_agent": "We currently offer the Aether Horizon SUV in a fully electric variant...",
  "channel": "text",
  "intent": "Product Info",
  "session_id": "user-abc-123"
}
```

`session_id` is optional — if omitted, a UUID is generated and returned so the client can maintain state across turns.

## Intents & Channels

| Intent | Example messages | Channel |
|---|---|---|
| Product Info | "What cars do you have?" / "Tell me about the GT Coupe" | `text` |
| Space Analysis | "What showroom layout fits 10 cars?" | `text` |
| Purchase Intent | "I want to buy a vehicle" / "What are the financing options?" | `escalation` |
| Voice Request | "Can you say that in voice?" / "Read that to me" | `voice` |
| Escalation | "I need to speak to a human" / "Connect me to an agent" | `escalation` |

## Multi-turn Memory

Each `session_id` maintains an independent conversation history.
The last 6 turns are injected into every agent call so the assistant remembers context across messages in the same session.

**Example:**
```
POST /chat  {"message": "Tell me about the Aether GT", "session_id": "s1"}
POST /chat  {"message": "What colors does it come in?", "session_id": "s1"}
            ↑ agent knows "it" refers to the Aether GT from the previous turn
```

## Voice Channel (Realtime API)

When `intent = "Voice Request"`, the response goes through the OpenAI Realtime API:

1. **Session setup** — WebSocket connect to `wss://api.openai.com/v1/realtime`, wait for `session.created`
2. **User audio input** — send `conversation.item.create` with the user's message
3. **Agent audio response** — send `response.create` with `modalities: ["text", "audio"]`, collect `response.audio_transcript.delta` events
4. **Graceful teardown** — break on `response.done`, WebSocket closed cleanly

Requires an OpenAI account with Realtime API access.
Falls back gracefully to a text response if Realtime API is unavailable on the account.

## RAG

Three knowledge-base files are indexed and searched semantically:

| File | Used by |
|---|---|
| `data/vehicle_catalog.txt` | Product Info Agent |
| `data/showroom_layouts.txt` | Space Analysis Agent |
| `data/dealership_faq.txt` | Purchase Intent Agent |

Retrieval uses `text-embedding-3-small` embeddings with cosine similarity.
The top-4 matching chunks are injected into the agent's context window before each call.
The `search_knowledge_base` function is also exposed as an Agents SDK `@function_tool` so agents can call it directly during a run.

## Project Structure

```
desafio/
├── app/
│   ├── config.py             # OpenAI client + environment config
│   ├── api/
│   │   ├── server.py         # FastAPI application
│   │   └── router.py         # POST /chat route handler
│   ├── agents/
│   │   ├── graph.py          # Multi-agent graph (OpenAI Agents SDK)
│   │   └── voice.py          # OpenAI Realtime API WebSocket session
│   ├── core/
│   │   ├── orchestrator.py   # Main pipeline: classify → RAG → run agent → JSON
│   │   ├── intents.py        # Intent classifier (keyword + LLM fallback)
│   │   └── memory.py         # Per-session conversation history
│   └── rag/
│       └── retriever.py      # Embedding search over knowledge-base files
├── data/
│   ├── vehicle_catalog.txt
│   ├── dealership_faq.txt
│   └── showroom_layouts.txt
├── scripts/
│   └── setup_vector_store.py # One-time Vector Store setup
├── tests/
│   ├── test_all_intents.py   # Tests all 5 intents end-to-end
│   └── test_chat.py          # Single HTTP integration test
├── ARCHITECTURE.md
├── README.md
├── requirements.txt
└── .env
```
