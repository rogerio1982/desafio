"""
app/agents/voice.py

OpenAI Realtime API WebSocket session handler.

Session lifecycle:
    1. Connect to wss://api.openai.com/v1/realtime
    2. Wait for session.created confirmation
    3. Send conversation.item.create  (user text)
    4. Send response.create           (modalities: text + audio)
    5. Collect response.audio_transcript.delta events
    6. Break on response.done         (graceful teardown)

Falls back to "[Voice channel] {text}" if the Realtime API is unavailable.
"""

import asyncio
import json
import os

import websockets
from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.getenv("OPENAI_API_KEY", "")
_REALTIME_MODEL = "gpt-4o-realtime-preview-2024-10-01"
_REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={_REALTIME_MODEL}"


async def speak_text(text: str, session_id: str) -> str:
    """
    Send *text* through a Realtime API session and return the audio transcript.
    Returns a graceful fallback string if the session cannot be established.
    """
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(
            _REALTIME_URL,
            additional_headers=headers,
            open_timeout=10,
        ) as ws:
            # 1. Wait for session setup confirmation
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            event = json.loads(raw)
            if event.get("type") != "session.created":
                return f"[Voice channel] {text}"

            # 2. Send user input
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }))

            # 3. Request audio response
            await ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "modalities": ["text", "audio"],
                    "instructions": (
                        "You are a friendly 3D car showroom assistant. "
                        "Respond naturally as if speaking aloud. Keep it concise."
                    ),
                },
            }))

            # 4. Collect transcript until response.done (graceful teardown)
            transcript = ""
            async for raw_msg in ws:
                ev = json.loads(raw_msg)
                ev_type = ev.get("type", "")

                if ev_type == "response.audio_transcript.delta":
                    transcript += ev.get("delta", "")
                elif ev_type == "response.text.delta":
                    transcript += ev.get("delta", "")
                elif ev_type == "response.done":
                    break
                elif ev_type == "error":
                    raise RuntimeError(ev.get("error", {}).get("message", "Realtime error"))

            return transcript or f"[Voice channel] {text}"

    except Exception:
        return f"[Voice channel] {text}"
