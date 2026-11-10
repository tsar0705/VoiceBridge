import time
from typing import Dict, List, Optional, Any
from app.config import settings


class ConversationService:
    """
    Manages in-memory multi-turn conversational context keyed strictly by session_id.
    Maintains a sliding window of recent messages for context-aware voice assistance.
    Ensures strict session isolation between concurrent users.
    """

    def __init__(self, max_history: Optional[int] = None):
        self.max_history = max_history if max_history is not None else settings.MAX_HISTORY_TURNS
        # session_id -> list of {"role": "user"|"assistant", "content": str, "language": str, "timestamp": float}
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns ordered list of conversation turns for a given session."""
        if not session_id:
            return []
        return list(self._sessions.get(session_id, []))

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        language: Optional[str] = None,
    ) -> None:
        """
        Appends a message turn to the specified session history.
        Enforces maximum history turn retention limit.
        """
        if not session_id or not content:
            return

        if session_id not in self._sessions:
            self._sessions[session_id] = []

        turn = {
            "role": role,
            "content": content.strip(),
            "language": language,
            "timestamp": time.time(),
        }
        self._sessions[session_id].append(turn)

        # Enforce sliding window limit
        if len(self._sessions[session_id]) > self.max_history:
            self._sessions[session_id] = self._sessions[session_id][-self.max_history:]

    def clear_history(self, session_id: str) -> bool:
        """
        Clears conversation history for the given session ID.
        Returns True if session was present and cleared, False otherwise.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        """Checks if active conversation history exists for a given session ID."""
        return bool(session_id and session_id in self._sessions)

    def get_turn_count(self, session_id: str) -> int:
        """Returns the number of turns currently recorded for the session."""
        return len(self._sessions.get(session_id, []))


# Shared singleton instance
conversation_service = ConversationService()
