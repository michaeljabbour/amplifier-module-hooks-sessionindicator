"""Tests for unstick functionality."""

import signal
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from hooks_sessionindicator.unstick import UnstickHandler, StuckDetection


class TestStuckDetection:
    """Tests for StuckDetection configuration."""
    
    def test_default_thresholds(self):
        """Default thresholds are reasonable."""
        config = StuckDetection()
        assert config.idle_threshold == 60.0
        assert config.critical_threshold == 180.0
    
    def test_slow_tools_configured(self):
        """Slow tools are pre-configured."""
        config = StuckDetection()
        assert "task" in config.slow_tools
        assert "bash" in config.slow_tools


class TestUnstickHandler:
    """Tests for UnstickHandler."""
    
    def test_install_uninstall(self):
        """Handler installs and uninstalls cleanly."""
        handler = UnstickHandler()
        
        original = signal.getsignal(signal.SIGINT)
        
        handler.install()
        assert handler._installed is True
        
        handler.uninstall()
        assert handler._installed is False
        
        # Original handler restored
        assert signal.getsignal(signal.SIGINT) == original
    
    def test_first_interrupt_calls_cancel(self):
        """First Ctrl+C calls on_cancel callback."""
        cancel_called = []
        handler = UnstickHandler(on_cancel=lambda: cancel_called.append(True))
        
        # Simulate SIGINT
        handler._handle_sigint(signal.SIGINT, None)
        
        assert len(cancel_called) == 1
        assert handler._interrupt_count == 1
    
    def test_escalation_within_window(self):
        """Rapid interrupts escalate the action."""
        abort_called = []
        handler = UnstickHandler(
            on_cancel=lambda: None,
            on_abort=lambda: abort_called.append(True)
        )
        
        # First interrupt
        handler._handle_sigint(signal.SIGINT, None)
        assert handler._interrupt_count == 1
        
        # Second interrupt within window
        handler._handle_sigint(signal.SIGINT, None)
        assert handler._interrupt_count == 2
        assert len(abort_called) == 1
    
    def test_escalation_resets_after_window(self):
        """Interrupt count resets after escalation window."""
        handler = UnstickHandler()
        
        # First interrupt
        handler._handle_sigint(signal.SIGINT, None)
        
        # Simulate time passing
        handler._last_interrupt = datetime.now() - timedelta(seconds=5)
        
        # Next interrupt should reset count
        handler._handle_sigint(signal.SIGINT, None)
        assert handler._interrupt_count == 1
    
    def test_third_interrupt_raises_keyboard_interrupt(self):
        """Third interrupt raises KeyboardInterrupt by default."""
        handler = UnstickHandler(
            on_cancel=lambda: None,
            on_abort=lambda: None,
        )
        
        handler._handle_sigint(signal.SIGINT, None)
        handler._handle_sigint(signal.SIGINT, None)
        
        with pytest.raises(KeyboardInterrupt):
            handler._handle_sigint(signal.SIGINT, None)
    
    def test_custom_exit_handler(self):
        """Custom exit handler is called instead of raising."""
        exit_called = []
        handler = UnstickHandler(
            on_cancel=lambda: None,
            on_abort=lambda: None,
            on_exit=lambda: exit_called.append(True)
        )
        
        handler._handle_sigint(signal.SIGINT, None)
        handler._handle_sigint(signal.SIGINT, None)
        handler._handle_sigint(signal.SIGINT, None)
        
        assert len(exit_called) == 1
