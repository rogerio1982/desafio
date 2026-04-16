"""
app/agents/graph.py

Multi-agent graph built with the OpenAI Agents SDK.

Agent hierarchy:
    TriageAgent  (fallback router — used only when keyword classification yields no match)
        ├── ProductInfoAgent     tools=[FileSearchTool, search_knowledge_base]
        ├── SpaceAnalysisAgent   tools=[FileSearchTool, search_knowledge_base]
        ├── PurchaseIntentAgent  tools=[FileSearchTool, search_knowledge_base]  → handoff EscalationAgent
        ├── VoiceAgent
        └── EscalationAgent

Returns a dict mapping intent names and "triage" to their respective Agent instances.
"""

import os

from agents import Agent, FileSearchTool
from app.config import VECTOR_STORE_ID
from app.rag.retriever import search_knowledge_base


def _file_search_tool() -> FileSearchTool:
    if not VECTOR_STORE_ID:
        raise EnvironmentError(
            "VECTOR_STORE_ID is not set. Run `python scripts/setup_vector_store.py` first."
        )
    return FileSearchTool(vector_store_ids=[VECTOR_STORE_ID], max_num_results=5)


def create_agent_graph() -> dict[str, Agent]:
    """
    Build and return the full agent graph.
    Called once at server startup; agents are singletons for the process lifetime.
    """
    file_search = _file_search_tool()

    escalation_agent = Agent(
        name="Escalation Agent",
        instructions=(
            "You are a customer service escalation specialist for a 3D digital car showroom. "
            "Always respond in English. "
            "Acknowledge the user's request warmly, confirm that a human agent will follow up shortly, "
            "and collect any information needed to facilitate contact (name, preferred time). "
            "Be empathetic and professional."
        ),
    )

    voice_agent = Agent(
        name="Voice Agent",
        instructions=(
            "You respond on the voice channel for a 3D digital car showroom. "
            "Always respond in English. "
            "Your answer will be converted to speech — keep it concise, conversational, "
            "and free of bullet points or markdown. Speak naturally."
        ),
    )

    product_agent = Agent(
        name="Product Info Agent",
        instructions=(
            "You are a vehicle product specialist for a 3D digital car showroom. "
            "Always respond in English. "
            "Use the knowledge base tools to answer questions about vehicle specs, models, "
            "features, colors, pricing, availability, and technology packages. "
            "Ground every answer in retrieved data. Never invent vehicle details."
        ),
        tools=[file_search, search_knowledge_base],
    )

    space_agent = Agent(
        name="Space Analysis Agent",
        instructions=(
            "You are a showroom space planning specialist for a 3D digital car showroom. "
            "Always respond in English. "
            "Use the knowledge base tools to answer questions about showroom layouts, "
            "floor plans, space requirements, vehicle positioning, and environment configurations. "
            "Provide specific, actionable recommendations grounded in the retrieved layout data."
        ),
        tools=[file_search, search_knowledge_base],
    )

    purchase_agent = Agent(
        name="Purchase Intent Agent",
        instructions=(
            "You are a sales and financing consultant for a 3D digital car showroom. "
            "Always respond in English. "
            "Use the knowledge base tools to answer questions about purchasing, "
            "financing options, installment plans, trade-ins, and dealership policies. "
            "Guide the customer toward completing their purchase. "
            "Hand off to the Escalation Agent if the customer needs direct human assistance."
        ),
        tools=[file_search, search_knowledge_base],
        handoffs=[escalation_agent],
    )

    triage_agent = Agent(
        name="Triage Agent",
        instructions=(
            "You are the orchestrator for a 3D digital car showroom AI assistant. "
            "Always communicate in English. "
            "Analyse the user's message and hand off immediately to the correct specialist:\n"
            "- Product Info Agent: vehicle specs, models, features, pricing, colors, technology\n"
            "- Space Analysis Agent: showroom layout, space planning, floor plans\n"
            "- Purchase Intent Agent: buying, financing, installments, trade-ins, orders\n"
            "- Voice Agent: user explicitly requests a voice or audio response\n"
            "- Escalation Agent: user wants to speak with a human agent\n"
            "Do NOT answer directly — always hand off."
        ),
        handoffs=[product_agent, space_agent, purchase_agent, voice_agent, escalation_agent],
    )

    return {
        "triage": triage_agent,
        "Product Info": product_agent,
        "Space Analysis": space_agent,
        "Purchase Intent": purchase_agent,
        "Voice Request": voice_agent,
        "Escalation": escalation_agent,
    }
