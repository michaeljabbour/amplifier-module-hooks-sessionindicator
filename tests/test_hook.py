"""Tests for the main SessionIndicatorHook."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from hooks_sessionindicator.hook import SessionIndicatorHook, SessionState


class TestSessionState:
    """Tests for SessionState dataclass."""
    
    def test_elapsed_seconds_no_start(self):
        """No start time returns 0."""
        state = SessionState()
        assert state.elapsed_seconds() == 0.0
    
    def test_elapsed_seconds_with_start(self):
        """Elapsed seconds calculated from start time."""
        state = SessionState(started_at=datetime.now() - timedelta(seconds=30))
        elapsed = state.elapsed_seconds()
        assert 29 <= elapsed <= 31  # Allow some tolerance
    
    def test_format_elapsed_minutes(self):
        """Format elapsed time as MM:SS."""
        state = SessionState(started_at=datetime.now() - timedelta(minutes=5, seconds=30))
        formatted = state.format_elapsed()
        assert formatted == "05:30"
    
    def test_format_elapsed_hours(self):
        """Format elapsed time as H:MM:SS for long sessions."""
        state = SessionState(started_at=datetime.now() - timedelta(hours=1, minutes=5, seconds=30))
        formatted = state.format_elapsed()
        assert formatted == "1:05:30"
    
    def test_format_tokens_small(self):
        """Format small token counts as-is."""
        state = SessionState(input_tokens=500, output_tokens=200)
        assert state.format_tokens() == "500↑ 200↓"
    
    def test_format_tokens_thousands(self):
        """Format large token counts with K suffix."""
        state = SessionState(input_tokens=12500, output_tokens=45000)
        formatted = state.format_tokens()
        assert "12.5K↑" in formatted
        assert "45.0K↓" in formatted
    
    def test_seconds_since_activity(self):
        """Seconds since last activity calculated correctly."""
        state = SessionState(last_activity=datetime.now() - timedelta(seconds=10))
        since = state.seconds_since_activity()
        assert 9 <= since <= 11


class TestSessionIndicatorHook:
    """Tests for SessionIndicatorHook."""
    
    def test_disabled_without_tty(self):
        """Hook is disabled when terminal doesn't support status line."""
        with patch("hooks_sessionindicator.hook.supports_status_line", return_value=False):
            hook = SessionIndicatorHook({})
            assert hook._enabled is False
    
    def test_subscribed_events(self):
        """Hook subscribes to expected events."""
        hook = SessionIndicatorHook({})
        events = hook.subscribed_events
        
        assert "session:start" in events
        assert "session:end" in events
        assert "llm:request" in events
        assert "tool:pre" in events
        assert "task:agent_spawned" in events
    
    @pytest.mark.asyncio
    async def test_tool_pre_updates_status(self):
        """tool:pre event updates status to executing."""
        hook = SessionIndicatorHook({})
        hook._enabled = True
        hook._state = SessionState()
        
        await hook.on_event("tool:pre", {"tool_name": "bash"})
        
        assert hook._state.status == "executing"
        assert hook._state.current_tool == "bash"
    
    @pytest.mark.asyncio
    async def test_tool_post_clears_tool(self):
        """tool:post event clears current tool."""
        hook = SessionIndicatorHook({})
        hook._enabled = True
        hook._state = SessionState(status="executing", current_tool="bash")
        
        await hook.on_event("tool:post", {})
        
        assert hook._state.status == "thinking"
        assert hook._state.current_tool is None
    
    @pytest.mark.asyncio
    async def test_agent_spawned_tracks_subsession(self):
        """task:agent_spawned tracks active sub-sessions."""
        hook = SessionIndicatorHook({})
        hook._enabled = True
        hook._state = SessionState()
        
        await hook.on_event("task:agent_spawned", {
            "session_id": "sub-123",
            "agent": "amplifier-expert"
        })
        
        assert "sub-123" in hook._state.active_subsessions
        assert hook._state.active_subsessions["sub-123"] == "amplifier-expert"
        assert hook._state.status == "delegating"
    
    def test_stuck_warning_threshold(self):
        """Stuck warning shown after threshold exceeded."""
        hook = SessionIndicatorHook({"stuck_threshold": 30.0})
        hook._state = SessionState(
            status="executing",
            last_activity=datetime.now() - timedelta(seconds=35)
        )
        
        assert hook._should_show_stuck_warning() is True
    
    def test_no_stuck_warning_when_idle(self):
        """No stuck warning when status is idle."""
        hook = SessionIndicatorHook({"stuck_threshold": 30.0})
        hook._state = SessionState(
            status="idle",
            last_activity=datetime.now() - timedelta(seconds=100)
        )
        
        assert hook._should_show_stuck_warning() is False
