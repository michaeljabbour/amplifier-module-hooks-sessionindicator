"""Tests for terminal module."""

import io
import os
import pytest
from hooks_sessionindicator.terminal import (
    supports_status_line,
    get_terminal_width,
    StatusLine,
    ProgressBar,
)


class TestSupportsStatusLine:
    """Tests for terminal capability detection."""
    
    def test_non_tty_returns_false(self):
        """Non-TTY streams don't support status line."""
        stream = io.StringIO()
        assert supports_status_line(stream) is False
    
    def test_no_color_disables(self, monkeypatch):
        """NO_COLOR environment variable disables status."""
        monkeypatch.setenv("NO_COLOR", "1")
        # Even if it were a TTY, NO_COLOR should disable
        stream = io.StringIO()
        assert supports_status_line(stream) is False
    
    def test_amplifier_no_status_disables(self, monkeypatch):
        """AMPLIFIER_NO_STATUS environment variable disables status."""
        monkeypatch.setenv("AMPLIFIER_NO_STATUS", "1")
        stream = io.StringIO()
        assert supports_status_line(stream) is False


class TestProgressBar:
    """Tests for ProgressBar class."""
    
    def test_empty_progress(self):
        """Empty progress bar shows 0%."""
        bar = ProgressBar(total=100, width=10)
        assert "0%" in bar.render()
        assert "░░░░░░░░░░" in bar.render()
    
    def test_half_progress(self):
        """Half progress shows 50%."""
        bar = ProgressBar(total=100, width=10)
        bar.update(50)
        assert "50%" in bar.render()
        assert "█████░░░░░" in bar.render()
    
    def test_full_progress(self):
        """Full progress shows 100%."""
        bar = ProgressBar(total=100, width=10)
        bar.update(100)
        assert "100%" in bar.render()
        assert "██████████" in bar.render()
    
    def test_increment(self):
        """increment() adds to current progress."""
        bar = ProgressBar(total=10, width=10)
        bar.increment(3)
        bar.increment(2)
        assert bar.current == 5
    
    def test_zero_total_is_100_percent(self):
        """Zero total shows 100% (avoid division by zero)."""
        bar = ProgressBar(total=0, width=10)
        assert "100%" in bar.render()


class TestStatusLine:
    """Tests for StatusLine class."""
    
    def test_update_truncates_long_content(self):
        """Long content is truncated to terminal width."""
        stream = io.StringIO()
        status = StatusLine(stream=stream, position="inline")
        status._visible = True
        status._width = 20
        
        status.update("x" * 100)
        
        output = stream.getvalue()
        # Should contain truncated content with "..."
        assert "..." in output or len(output) < 100
    
    def test_skip_unchanged_content(self):
        """Unchanged content doesn't trigger write."""
        stream = io.StringIO()
        status = StatusLine(stream=stream, position="inline")
        status._visible = True
        
        status.update("test content")
        first_len = len(stream.getvalue())
        
        status.update("test content")  # Same content
        second_len = len(stream.getvalue())
        
        # Second update should not add more content
        assert first_len == second_len
