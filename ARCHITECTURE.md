# Architecture Document — 3D Digital Showroom Conversational AI

## 1. Agent Decomposition

The system is composed of six agents, each with a single, clearly bounded responsibility. All agents are instantiated using the OpenAI Agents SDK (`Agent`, `Runner`, `FileSearchTool`, `handoff`).

---

### Triage Agent
**Responsibility:** Receive the initial message and, in cases where the orchestrator needs to delegate routing to the model rather than relying on keyword classification, forward to the correct specialist.

**Why this boundary:** The triage agent is the SDK-level entry point and exists primarily as a fallback router. In normal operation, the Python orchestrator classifies intent deterministically (keyword-first) and routes directly to the specialist agent — bypassing triage entirely. The triage agent is only invoked when intent is genuinely ambiguous and no keyword match was found. Keeping it separate from the specialists means the routing logic stays outside any single domain expert.

---

### Product Info Agent
**Responsibility:** Answer questions about vehicle models, trims, specifications, pricing, colors, range, charging, and technology packages. Grounded exclusively in `vehicle_catalog.txt`.

**Why this boundary:** Vehicle catalog knowledge is factual and structured (each entry is a fixed schema with fields like `motor_output_hp`, `range_miles`, `price_usd`). Isolating this agent prevents showroom layout or financing language from contaminating vehicle answers. It also means the agent can be replaced or retrained on a new catalog without touching the other agents.

**Tools:** `FileSearchTool` (OpenAI Vector Store), `search_knowledge_base` (`@function_tool` wrapping local embedding search)

---

### Space Analysis Agent
**Responsibility:** Answer questions about showroom floor layouts, square footage requirements, vehicle display capacity, lighting and flooring recommendations, and dealership tier configurations. Grounded exclusively in `showroom_layouts.txt`.

**Why this boundary:** Layout advice is architectural and operational, not transactional. A customer asking "how many cars fit in a 3,000 sq ft space?" needs a different reasoning chain than one asking "what is the price of the GT Coupe?" Separating them avoids the model blending concerns — e.g., inferring pricing from floor configuration or vice versa.

**Tools:** `FileSearchTool`, `search_knowledge_base`

---

### Purchase Intent Agent
**Responsibility:** Guide users through purchasing decisions — financing terms, APR, lease options, trade-in appraisal, delivery timelines, and ordering flow. Grounded in `dealership_faq.txt`. Can escalate to the Escalation Agent via SDK handoff if the user needs human intervention.

**Why this boundary:** Purchase conversations are process-oriented and involve liability-sensitive information (financing rates, credit qualification). Keeping this in a dedicated agent makes it straightforward to update financial terms, add new FAQ entries, or apply different compliance rules without touching product or layout agents. The built-in handoff to Escalation also reflects a real business rule: complex purchase decisions often require a human.

**Tools:** `FileSearchTool`, `search_knowledge_base`, `handoff → EscalationAgent`

---

### Voice Agent
**Responsibility:** Generate responses formatted for text-to-speech — concise, no markdown, conversational prose. After the agent produces its text, the orchestrator passes that text through the OpenAI Realtime API WebSocket session to obtain an audio transcript.

**Why this boundary:** Voice formatting is a presentation concern that cuts across all domains. Rather than adding TTS-awareness to every specialist agent, a dedicated Voice Agent handles any voice-directed query with the appropriate tone and structure. If the user asks a voice-format question about vehicles, the Voice Agent responds in voice style; the product details themselves are retrieved from context already injected by the orchestrator.

---

### Escalation Agent
**Responsibility:** Acknowledge the user's need for human contact, collect follow-up information (name, preferred contact time), and confirm that a human agent will follow up.

**Why this boundary:** Escalation is always terminal — once a user asks for a human, no other agent should attempt to answer the underlying query. Making this a separate agent with a distinct identity ensures it is never accidentally selected for product or layout questions, and its response style (empathetic, action-oriented) is enforced in isolation.

---

### Boundary rationale summary

The boundaries follow a single principle: **one agent per knowledge source or per output modality**. Three agents map to the three provided text files. One agent handles voice formatting. One handles terminal escalation. The triage agent is an SDK-required entry point. This decomposition means each agent can be updated, swapped, or evaluated independently.

---

## 2. Workflow Diagram

```
User
 │
 │  POST /chat  {message, session_id}
 ▼
┌─────────────────────────────────────────────────────────┐
│  router.py — /chat endpoint                             │
│  Generates session_id if not provided (uuid4)           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  orchestrator.py — handle_message()                     │
│                                                         │
│  Step 1 — Intent Classification (intents.py)            │
│  ┌─────────────────────────────────────────────────┐    │
│  │ _keyword_classify()                             │    │
│  │   Score each intent by keyword overlap          │    │
│  │   Tie-break: Escalation > Purchase > Voice >    │    │
│  │              Space Analysis > Product Info      │    │
│  │                                                 │    │
│  │ If score == 0 → GPT-4o-mini classify (fallback) │    │
│  │ If API fails  → default to "Escalation"         │    │
│  └─────────────────────────────────────────────────┘    │
│                     │                                   │
│  Step 2 — RAG Context Injection                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ if intent ∈ {Product Info, Space Analysis,      │    │
│  │              Purchase Intent}:                  │    │
│  │   search_local_kb(message)                      │    │
│  │   → embed query via text-embedding-3-small      │    │
│  │   → cosine similarity over all cached chunks    │    │
│  │   → top-4 chunks (score > 0.1)                  │    │
│  │   → prepend as [KNOWLEDGE BASE CONTEXT] block   │    │
│  └─────────────────────────────────────────────────┘    │
│                     │                                   │
│  Step 3 — Conversation History                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ ConversationMemory(session_id).get_history()    │    │
│  │ Append last 6 turns as ROLE: message lines      │    │
│  └─────────────────────────────────────────────────┘    │
│                     │                                   │
│  Step 4 — Agent Dispatch (OpenAI Agents SDK)            │
│  ┌─────────────────────────────────────────────────┐    │
│  │ agents[intent] → specialist agent               │    │
│  │ Runner.run(agent, rag_context + history)        │    │
│  │                                                 │    │
│  │ Product Info    → ProductInfoAgent              │    │
│  │ Space Analysis  → SpaceAnalysisAgent            │    │
│  │ Purchase Intent → PurchaseIntentAgent           │    │
│  │                     └──(if needed)──► Escalation│    │
│  │ Voice Request   → VoiceAgent                    │    │
│  │ Escalation      → EscalationAgent               │    │
│  │ (unknown)       → TriageAgent (SDK routing)     │    │
│  └─────────────────────────────────────────────────┘    │
│                     │                                   │
│  Step 5 — Voice Channel (Voice Request only)            │
│  ┌─────────────────────────────────────────────────┐    │
│  │ speak_text(agent_response, session_id)          │    │
│  │   WebSocket → wss://api.openai.com/v1/realtime  │    │
│  │   1. Connect + wait for session.created         │    │
│  │   2. conversation.item.create (user text)       │    │
│  │   3. response.create (modalities: text + audio) │    │
│  │   4. Collect response.audio_transcript.delta    │    │
│  │   5. Break on response.done (graceful teardown) │    │
│  │   Fallback: "[Voice channel] {text}" if error   │    │
│  └─────────────────────────────────────────────────┘    │
│                     │                                   │
│  Step 6 — Build response + update memory                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
       {
         "message_agent": "...",
         "channel":        "text | voice | escalation",
         "intent":         "Product Info | ...",
         "session_id":     "..."
       }
```

---

## 3. RAG Strategy

### Knowledge base structure

Each of the three files follows an identical physical format:
- A file-level header (domain, version, description)
- Individual records separated by `\n\n---\n\n`
- Each record is a self-contained entry with a structured key-value header (e.g., `[id: vc_001]`, `category:`, `name:`, `tags:`) followed by the factual content

This structure was chosen by the data authors and is well-suited for chunking because:
- Every `---` separator marks a semantic boundary — no record depends on its neighbours for meaning
- The key-value headers within each chunk carry enough context for the embedding model to understand what domain it is in (`category: financing`, `name: Aether GT Coupe`) without needing surrounding records

### Chunking strategy

Chunks are split on blank lines (`\n\n`), then filtered to keep only those with more than 30 characters. This preserves the record boundaries as designed in the source files. No overlap window or fixed-size sliding window is used — the records are already granular enough (each entry covers one vehicle trim, one layout tier, or one FAQ entry) that overlap would create noise rather than context.

### Retrieval method

1. At first request, all chunks from all three files are loaded and embedded in a single batch call to `text-embedding-3-small`. Results are stored in an in-process dictionary cache keyed by chunk text.
2. The user query is also embedded with the same model.
3. Cosine similarity is computed between the query vector and every chunk vector.
4. The top-4 chunks with a similarity score above `0.1` are selected and concatenated with `---` separators.
5. This context block is prepended to the agent's input as `[KNOWLEDGE BASE CONTEXT] ... [END CONTEXT]`.

A TF-IDF fallback activates if the embedding API call fails, using token frequency overlap as a proxy for relevance.

### Why `text-embedding-3-small`

The knowledge base records use consistent vocabulary and structured field names. The small model is sufficient for this domain-specific retrieval task and is significantly cheaper than `text-embedding-3-large`. The embeddings are cached for the process lifetime, so the cost is incurred only once per unique chunk (typically once at server startup).

### Why not Vector Store exclusively

OpenAI's Vector Store with `FileSearchTool` is included in the agent tooling and is the intended primary retrieval mechanism. During development, indexing stalled indefinitely on the target account (a platform-level issue confirmed by observing `in_progress` status with no completion after several minutes across multiple attempts). Local embedding search was introduced as a reliable alternative that produces equivalent retrieval quality for this dataset size.

---

## 4. State Management

### Per-session in-memory store

Conversation state is managed by `ConversationMemory` (`app/memory.py`). It maintains a class-level dictionary (`_sessions`) keyed by `session_id`. Each value is a list of `{role, message}` dicts appended in chronological order.

```
ConversationMemory._sessions = {
    "session-abc": [
        {"role": "user",      "message": "Tell me about the Aether GT"},
        {"role": "assistant", "message": "The Aether GT Coupe is..."},
        {"role": "user",      "message": "What colors does it come in?"},
        ...
    ],
    "session-xyz": [ ... ]
}
```

### How history is used

At each turn, the orchestrator retrieves the last 6 entries (3 full turns) from the session history and formats them as:

```
USER: Tell me about the Aether GT
ASSISTANT: The Aether GT Coupe is...
USER: What colors does it come in?
```

This block is appended after the RAG context and before the current message, giving the agent a rolling conversation window. The agent sees enough history to resolve pronouns and carry context across turns without the input growing unboundedly.

### Session identity

`session_id` is client-provided. If absent, the router generates a UUID v4 and returns it in the response so the client can reuse it on subsequent calls.

### Tradeoffs of this approach

This is process-local state. It is fast, dependency-free, and sufficient for a single-server deployment. It does not survive server restarts and cannot scale horizontally across multiple processes. In production this would be replaced by a shared store (Redis, a database) with a TTL policy.

---

## 5. What I Would Change with More Time

### 1. Replace in-memory session state with a persistent store
The current `ConversationMemory` is lost on every server restart. A Redis store with a 24-hour TTL would make sessions durable and allow horizontal scaling. The interface (`add_message`, `get_history`) is already abstract enough that this swap would be isolated to `memory.py`.

### 2. Fix Vector Store indexing and make it the primary RAG path
The intended architecture had `FileSearchTool` as the sole RAG mechanism — files are uploaded to OpenAI, indexed once, and retrieved natively inside the agent run loop. This is cleaner because retrieval happens inside the SDK trace (observable, reproducible) rather than in orchestrator pre-processing. The local embedding approach works well, but it requires every deployment to re-embed all chunks on first request, and the in-process cache is ephemeral.

### 3. Streaming responses
The current `/chat` endpoint returns a complete JSON object after the full agent run completes. For a realistic showroom UX, the `message_agent` field should stream token-by-token using server-sent events or WebSocket. The Agents SDK supports streaming via `Runner.run_streamed()`.

### 4. Proper input validation and error responses
The `/chat` endpoint currently accepts any JSON body and silently handles missing fields with `.get()` defaults. A Pydantic request model would enforce the contract, return 422 errors for bad input, and document the schema automatically in the FastAPI OpenAPI spec.

### 5. Chunk overlap and hybrid retrieval
The current chunking splits strictly on blank lines with no overlap. If a relevant fact spans a chunk boundary (e.g., a vehicle price mentioned at the end of one chunk and charging specs at the start of the next), the retrieval will miss the combined context. A sliding window with 10–20% overlap, combined with a BM25 keyword pass before the embedding re-rank, would improve recall on precise factual queries.

### 6. Evaluation harness
There is no automated evaluation of retrieval quality or response accuracy. A golden-set of question/expected-answer pairs (drawn from the knowledge base files) would allow measuring retrieval precision@k and response faithfulness before any change is deployed. Without this, the only signal is manual inspection of test outputs.

### 7. Voice session returning audio bytes
The current voice implementation returns a text transcript of the Realtime API response. A complete voice pipeline would return base64-encoded PCM or Opus audio (from `response.audio.delta` events) directly in the JSON response or via a separate binary endpoint, so a frontend could play the audio rather than re-synthesize it client-side.
