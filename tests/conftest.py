"""Pytest configuration for hooks-sessionindicator tests."""

import pytest


@pytest.fixture
def mock_tty(monkeypatch):
    """Fixture to simulate a TTY environment."""
    import sys
    import io
    
    class MockTTY(io.StringIO):
        def isatty(self):
            return True
    
    mock_stderr = MockTTY()
    monkeypatch.setattr(sys, "stderr", mock_stderr)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("AMPLIFIER_NO_STATUS", raising=False)
    
    return mock_stderr
