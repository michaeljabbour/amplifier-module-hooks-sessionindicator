"""
Terminal utilities for status line display.

Handles ANSI escape codes, terminal capability detection,
and safe cursor manipulation.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO


# ANSI escape sequences
ANSI_SAVE_CURSOR = "\033[s"
ANSI_RESTORE_CURSOR = "\033[u"
ANSI_CLEAR_LINE = "\033[2K"
ANSI_MOVE_TO_COL_1 = "\033[1G"
ANSI_HIDE_CURSOR = "\033[?25l"
ANSI_SHOW_CURSOR = "\033[?25h"

# Colors
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"
ANSI_YELLOW = "\033[33m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_CYAN = "\033[36m"


def supports_status_line(stream: TextIO | None = None) -> bool:
    """
    Check if the terminal supports ANSI escape codes for status line.
    
    Args:
        stream: The output stream to check (default: stderr)
        
    Returns:
        True if ANSI escape codes are supported
    """
    stream = stream or sys.stderr
    
    # Must be a TTY
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    
    # Check TERM environment variable
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    
    # Check for NO_COLOR environment variable
    if os.environ.get("NO_COLOR"):
        return False
    
    # Check for AMPLIFIER_NO_STATUS environment variable
    if os.environ.get("AMPLIFIER_NO_STATUS"):
        return False
    
    # Most modern terminals support ANSI
    return True


def get_terminal_width(default: int = 80) -> int:
    """Get terminal width, with fallback."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


class StatusLine:
    """
    Manages a status line at the bottom of the terminal.
    
    Uses ANSI escape codes to maintain a persistent line that
    doesn't interfere with normal output scrolling.
    """
    
    def __init__(
        self,
        stream: TextIO | None = None,
        position: str = "bottom",
    ):
        """
        Initialize status line.
        
        Args:
            stream: Output stream (default: stderr)
            position: "bottom" or "inline"
        """
        self._stream = stream or sys.stderr
        self._position = position
        self._visible = False
        self._last_content = ""
        self._width = get_terminal_width()
    
    def show(self) -> None:
        """Make the status line visible."""
        if self._visible:
            return
        
        self._visible = True
        
        if self._position == "bottom":
            # Add a blank line at bottom for status
            self._write("\n")
    
    def hide(self) -> None:
        """Hide the status line and restore terminal state."""
        if not self._visible:
            return
        
        self._visible = False
        
        # Clear the status line
        self._write(f"{ANSI_CLEAR_LINE}{ANSI_MOVE_TO_COL_1}")
        
        if self._position == "bottom":
            # Move up to reclaim the line
            self._write("\033[1A")
    
    def update(self, content: str) -> None:
        """Update the status line content."""
        if not self._visible:
            return
        
        # Truncate to terminal width (leave room for padding)
        max_width = self._width - 2
        if len(content) > max_width:
            content = content[: max_width - 3] + "..."
        
        # Skip update if content unchanged
        if content == self._last_content:
            return
        
        self._last_content = content
        
        # Format: save cursor, move to status line, clear, write, restore
        if self._position == "bottom":
            # Move to bottom row
            self._write(
                f"{ANSI_SAVE_CURSOR}"
                f"\033[999;1H"  # Move to row 999 (will clamp to bottom)
                f"{ANSI_CLEAR_LINE}"
                f"{ANSI_DIM}{content}{ANSI_RESET}"
                f"{ANSI_RESTORE_CURSOR}"
            )
        else:
            # Inline: just update current line
            self._write(
                f"{ANSI_MOVE_TO_COL_1}"
                f"{ANSI_CLEAR_LINE}"
                f"{ANSI_DIM}{content}{ANSI_RESET}"
            )
    
    def _write(self, text: str) -> None:
        """Write to stream and flush."""
        try:
            self._stream.write(text)
            self._stream.flush()
        except (IOError, OSError):
            # Terminal might be gone (e.g., pipe closed)
            self._visible = False


class ProgressBar:
    """Simple progress bar for bounded operations."""
    
    def __init__(self, total: int, width: int = 20):
        self.total = total
        self.current = 0
        self.width = width
    
    def update(self, current: int) -> None:
        """Update current progress."""
        self.current = min(current, self.total)
    
    def increment(self, amount: int = 1) -> None:
        """Increment progress."""
        self.update(self.current + amount)
    
    def render(self) -> str:
        """Render the progress bar as a string."""
        if self.total == 0:
            pct = 100
        else:
            pct = int(100 * self.current / self.total)
        
        filled = int(self.width * self.current / max(self.total, 1))
        empty = self.width - filled
        
        bar = "█" * filled + "░" * empty
        return f"{bar} {pct}%"
