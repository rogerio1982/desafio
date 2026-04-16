"""
app/core/memory.py

Per-session conversation history store.

Each session_id maps to an ordered list of {role, message} entries.
The store is process-local — it is fast and dependency-free for single-server
deployments. Replace with a shared store (Redis + TTL) for horizontal scaling.
"""

from typing import TypedDict


class Turn(TypedDict):
    role: str
    message: str


class ConversationMemory:
    _sessions: dict[str, list[Turn]] = {}

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        if session_id not in self._sessions:
            self._sessions[session_id] = []

    def add_message(self, role: str, message: str) -> None:
        self._sessions[self.session_id].append({"role": role, "message": message})

    def get_history(self) -> list[Turn]:
        return self._sessions[self.session_id]
