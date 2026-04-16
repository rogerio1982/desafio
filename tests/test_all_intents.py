"""
tests/test_all_intents.py

End-to-end test for all 5 intents.
Run from the project root: python tests/test_all_intents.py
"""

import unittest
import asyncio
from app.core.orchestrator import handle_message

_CASES = [
    ("Tell me about the available cars",      "sess1"),
    ("What is the showroom layout like?",     "sess2"),
    ("I want to buy a vehicle",               "sess3"),
    ("Can you speak that in voice?",          "sess4"),
    ("I need to speak with a human attendant","sess5"),
]

class TestAllIntents(unittest.IsolatedAsyncioTestCase):
    async def test_all_intents(self):
        for message, session_id in _CASES:
            with self.subTest(message=message):
                result = await handle_message(message, session_id)
                self.assertIn("intent", result)
                self.assertIn("channel", result)
                self.assertIn("message_agent", result)
                self.assertIsInstance(result["message_agent"], str)
                self.assertGreater(len(result["message_agent"]), 0)
