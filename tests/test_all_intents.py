"""
tests/test_all_intents.py

End-to-end test for all 5 intents.
Run from the project root: python tests/test_all_intents.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.core.orchestrator import handle_message

_CASES = [
    ("Tell me about the available cars",      "sess1"),
    ("What is the showroom layout like?",     "sess2"),
    ("I want to buy a vehicle",               "sess3"),
    ("Can you speak that in voice?",          "sess4"),
    ("I need to speak with a human attendant","sess5"),
]


async def run_tests() -> None:
    for message, session_id in _CASES:
        try:
            result = await handle_message(message, session_id)
            preview = result["message_agent"][:80]
            print(f"OK [{result['intent']}] channel={result['channel']} msg={preview}")
        except Exception:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_tests())
