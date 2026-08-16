"""Tests for the conversation memory shared helpers."""

import pytest

from piighost.conversation_memory.base import warn_plaintext
from piighost.exceptions import PIIGhostSecurityWarning


class TestWarnPlaintext:
    def test_emits_a_security_warning_naming_the_backend_and_doc(self) -> None:
        """warn_plaintext warns with the backend name and the security doc URL."""
        with pytest.warns(PIIGhostSecurityWarning) as record:
            warn_plaintext("RedisConversationMemory")
        message = str(record[0].message)
        assert "RedisConversationMemory" in message
        assert "https://athroniaeth.github.io/piighost/security/" in message
