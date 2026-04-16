"""
app/core/orchestrator.py

Central message-processing pipeline.

Flow per request:
    1. Classify intent  (keyword-first → GPT-4o-mini fallback)
    2. Retrieve RAG context  (embedding search, injected for knowledge-based intents)
    3. Assemble agent input  (RAG context + last-6-turns conversation history)
    4. Run specialist agent  (OpenAI Agents SDK Runner)
    5. Post-process voice responses through the Realtime API session
    6. Persist turn to memory and return structured JSON
"""

import os

from agents import Runner, set_default_openai_key
from dotenv import load_dotenv

from app.agents.graph import create_agent_graph
from app.agents.voice import speak_text
from app.core.intents import classify_intent
from app.core.memory import ConversationMemory
from app.rag.retriever import search_local_kb

load_dotenv()
set_default_openai_key(os.getenv("OPENAI_API_KEY", ""))

_INTENT_CHANNEL: dict[str, str] = {
    "Product Info":    "text",
    "Space Analysis":  "text",
    "Purchase Intent": "escalation",
    "Voice Request":   "voice",
    "Escalation":      "escalation",
}

# Intents that retrieve knowledge-base context before the agent call
_RAG_INTENTS = {"Product Info", "Space Analysis", "Purchase Intent"}

# Agent graph — built once on first request
_agents: dict | None = None


def _get_agents() -> dict:
    global _agents
    if _agents is None:
        _agents = create_agent_graph()
    return _agents


async def handle_message(message: str, session_id: str) -> dict:
    """Process *message* and return the structured JSON response dict."""
    memory = ConversationMemory(session_id)
    memory.add_message("user", message)

    # 1. Intent classification
    intent = await classify_intent(message)
    channel = _INTENT_CHANNEL.get(intent, "text")

    # 2. RAG context injection
    rag_block = ""
    if intent in _RAG_INTENTS:
        snippets = search_local_kb(message)
        if snippets:
            rag_block = f"[KNOWLEDGE BASE CONTEXT]\n{snippets}\n[END CONTEXT]\n\n"

    # 3. Conversation history (rolling 6-turn window)
    history = memory.get_history()
    conversation = "\n".join(
        f"{turn['role'].upper()}: {turn['message']}" for turn in history[-6:]
    )
    agent_input = rag_block + conversation

    # 4. Run specialist agent
    agents = _get_agents()
    agent = agents.get(intent, agents["triage"])
    result = await Runner.run(agent, agent_input)
    response = result.final_output or "I'm here to help. Could you please provide more details?"

    # 5. Voice post-processing (Realtime API session)
    if intent == "Voice Request":
        response = await speak_text(response, session_id)

    memory.add_message("assistant", response)

    return {
        "message_agent": response,
        "channel": channel,
        "intent": intent,
        "session_id": session_id,
    }
