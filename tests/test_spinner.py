"""Tests for spinner module."""

import pytest
from hooks_sessionindicator.spinner import Spinner, StatusSpinner, SPINNERS


class TestSpinner:
    """Tests for basic Spinner class."""
    
    def test_default_spinner(self):
        """Default spinner uses dots style."""
        spinner = Spinner()
        assert spinner.current_frame() in SPINNERS["dots"]
    
    def test_next_frame_advances(self):
        """next_frame advances through frames."""
        spinner = Spinner(style="line")
        frames = [spinner.next_frame() for _ in range(5)]
        assert frames == ["|", "/", "-", "\\", "|"]
    
    def test_custom_frames(self):
        """Custom frames override style."""
        spinner = Spinner(frames=["a", "b", "c"])
        assert spinner.next_frame() == "a"
        assert spinner.next_frame() == "b"
        assert spinner.next_frame() == "c"
        assert spinner.next_frame() == "a"  # wraps
    
    def test_reset(self):
        """reset() returns to first frame."""
        spinner = Spinner(style="line")
        spinner.next_frame()
        spinner.next_frame()
        spinner.reset()
        assert spinner.current_frame() == "|"


class TestStatusSpinner:
    """Tests for StatusSpinner class."""
    
    def test_idle_shows_icon(self):
        """Idle status shows static icon."""
        spinner = StatusSpinner()
        spinner.set_status("idle")
        assert spinner.next_frame() == "○"
    
    def test_error_shows_icon(self):
        """Error status shows X icon."""
        spinner = StatusSpinner()
        spinner.set_status("error")
        assert spinner.next_frame() == "✗"
    
    def test_thinking_animates(self):
        """Thinking status uses animated spinner."""
        spinner = StatusSpinner()
        spinner.set_status("thinking")
        frames = [spinner.next_frame() for _ in range(3)]
        # Should be different frames (animating)
        assert len(set(frames)) > 1
    
    def test_streaming_animates(self):
        """Streaming status uses wave animation."""
        spinner = StatusSpinner()
        spinner.set_status("streaming")
        frames = [spinner.next_frame() for _ in range(3)]
        # Streaming frames are different
        assert all(f in "▁▂▃▄▅▆▇█" for f in frames)
