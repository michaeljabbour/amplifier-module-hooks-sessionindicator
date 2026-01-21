"""
Session unstick functionality.

Provides mechanisms to detect stuck sessions and allow users
to interrupt/recover them via keyboard shortcuts.

Cross-platform keyboard handling:
- macOS: Ctrl+C (SIGINT)
- Linux: Ctrl+C (SIGINT)  
- Windows: Ctrl+C (SIGINT), Ctrl+Break

Escalation pattern:
- 1st Ctrl+C: Cancel current tool, continue session
- 2nd Ctrl+C (within 2s): Abort current turn
- 3rd Ctrl+C (within 2s): Emergency exit
"""

from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable


class UnstickAction(Enum):
    """Actions that can be taken when a session appears stuck."""
    CANCEL_CURRENT = "cancel_current"
    ABORT_TURN = "abort_turn"
    EMERGENCY_EXIT = "emergency_exit"


@dataclass
class StuckDetection:
    """Configuration for stuck detection."""
    idle_threshold: float = 60.0
    critical_threshold: float = 180.0
    slow_tools: frozenset[str] = frozenset({"task", "bash", "web_fetch"})
    slow_tool_threshold: float = 300.0


class UnstickHandler:
    """
    Handles keyboard interrupts for stuck session recovery.
    
    Escalation pattern:
    1. First Ctrl+C: Try to cancel current operation gracefully
    2. Second Ctrl+C within 2s: Abort current turn
    3. Third Ctrl+C within 2s: Emergency exit
    """
    
    def __init__(
        self,
        on_cancel: Callable[[], None] | None = None,
        on_abort: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ):
        self._on_cancel = on_cancel
        self._on_abort = on_abort
        self._on_exit = on_exit
        
        self._interrupt_count = 0
        self._last_interrupt: datetime | None = None
        self._escalation_window = 2.0  # seconds
        
        self._original_handler: signal.Handlers | None = None
        self._installed = False
    
    def install(self) -> None:
        """Install signal handlers."""
        if self._installed:
            return
        
        self._original_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)
        self._installed = True
    
    def uninstall(self) -> None:
        """Restore original signal handlers."""
        if not self._installed:
            return
        
        if self._original_handler is not None:
            signal.signal(signal.SIGINT, self._original_handler)
        
        self._installed = False
    
    def _handle_sigint(self, signum: int, frame) -> None:
        """Handle SIGINT (Ctrl+C)."""
        now = datetime.now()
        
        # Check if within escalation window
        if self._last_interrupt:
            elapsed = (now - self._last_interrupt).total_seconds()
            if elapsed < self._escalation_window:
                self._interrupt_count += 1
            else:
                self._interrupt_count = 1
        else:
            self._interrupt_count = 1
        
        self._last_interrupt = now
        
        # Escalate based on count
        if self._interrupt_count == 1:
            self._show_hint("Canceling current operation... (press again to abort turn)")
            if self._on_cancel:
                self._on_cancel()
        elif self._interrupt_count == 2:
            self._show_hint("Aborting turn... (press again to exit)")
            if self._on_abort:
                self._on_abort()
        else:
            self._show_hint("Emergency exit!")
            if self._on_exit:
                self._on_exit()
            else:
                raise KeyboardInterrupt("User requested emergency exit")
    
    def _show_hint(self, message: str) -> None:
        """Show a hint message to the user."""
        sys.stderr.write(f"\n⚠ {message}\n")
        sys.stderr.flush()


KEYBOARD_SHORTCUTS = """
Session Control Shortcuts (works on macOS, Linux, Windows):
───────────────────────────────────────────────────────────
Ctrl+C      Cancel current operation (1st press)
Ctrl+C ×2   Abort current turn (within 2 seconds)
Ctrl+C ×3   Emergency exit (within 2 seconds)
"""


async def wait_for_unstick_or_complete(
    task: asyncio.Task,
    handler: UnstickHandler,
    check_interval: float = 0.5,
) -> bool:
    """
    Wait for a task to complete, with unstick handling.
    
    Returns:
        True if task completed, False if interrupted
    """
    handler.install()
    try:
        while not task.done():
            await asyncio.sleep(check_interval)
        return True
    except asyncio.CancelledError:
        return False
    finally:
        handler.uninstall()
