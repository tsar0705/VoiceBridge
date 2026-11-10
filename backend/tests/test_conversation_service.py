import pytest
from app.services.conversation_service import ConversationService


def test_add_and_retrieve_history():
    """Verify storing user and assistant turns in a session."""
    conv = ConversationService(max_history=5)
    conv.add_message("sess_1", "user", "வணக்கம்", language="ta")
    conv.add_message("sess_1", "assistant", "வணக்கம்! நான் உங்களுக்கு எவ்வாறு உதவ முடியும்?", language="Tamil")

    history = conv.get_history("sess_1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "வணக்கம்"
    assert history[0]["language"] == "ta"
    assert history[1]["role"] == "assistant"
    assert "உதவ முடியும்" in history[1]["content"]


def test_session_isolation():
    """Verify that sessions do not leak context across different session IDs."""
    conv = ConversationService(max_history=5)
    conv.add_message("user_A", "user", "Hello from User A")
    conv.add_message("user_B", "user", "Namaste from User B")

    history_a = conv.get_history("user_A")
    history_b = conv.get_history("user_B")

    assert len(history_a) == 1
    assert history_a[0]["content"] == "Hello from User A"
    assert len(history_b) == 1
    assert history_b[0]["content"] == "Namaste from User B"


def test_history_sliding_window_limit():
    """Verify that turns exceeding max_history are dropped from the beginning."""
    conv = ConversationService(max_history=4)
    for i in range(10):
        conv.add_message("sess_limit", "user" if i % 2 == 0 else "assistant", f"Message {i}")

    history = conv.get_history("sess_limit")
    assert len(history) == 4
    assert history[0]["content"] == "Message 6"
    assert history[-1]["content"] == "Message 9"


def test_clear_session_history():
    """Verify clearing a conversation session."""
    conv = ConversationService(max_history=5)
    conv.add_message("sess_reset", "user", "Test message")
    assert conv.session_exists("sess_reset") is True

    cleared = conv.clear_history("sess_reset")
    assert cleared is True
    assert conv.get_history("sess_reset") == []
    assert conv.session_exists("sess_reset") is False

    # Second clear returns False
    assert conv.clear_history("sess_reset") is False


def test_empty_or_unknown_session():
    """Verify unknown session IDs return empty history gracefully."""
    conv = ConversationService()
    assert conv.get_history("unknown_session_xyz") == []
    assert conv.get_history("") == []
    assert conv.get_turn_count("nonexistent") == 0
