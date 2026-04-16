"""
tests/test_chat.py

Single HTTP integration test against the running server.
Start the server first: uvicorn app.api.server:app --reload
Run: python tests/test_chat.py
"""

import json

import requests

_URL = "http://127.0.0.1:8000/chat"
_PAYLOAD = {
    "message": "I want to know about the available cars",
    "session_id": "test123",
}

response = requests.post(_URL, json=_PAYLOAD)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
