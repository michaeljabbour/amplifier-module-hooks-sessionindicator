"""
Spinner animation for activity indication.
"""

from __future__ import annotations

from typing import Sequence


# Spinner frame sets
SPINNERS: dict[str, Sequence[str]] = {
    "dots": ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"),
    "line": ("|", "/", "-", "\\"),
    "box": ("◰", "◳", "◲", "◱"),
    "arrow": ("←", "↖", "↑", "↗", "→", "↘", "↓", "↙"),
    "bounce": ("⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"),
    "circle": ("◜", "◝", "◞", "◟"),
    "grow": ("⣀", "⣄", "⣤", "⣦", "⣶", "⣷", "⣿", "⣾", "⣼", "⣸"),
    "ellipsis": ("   ", ".  ", ".. ", "..."),
}

DEFAULT_SPINNER = "dots"


class Spinner:
    """Animated spinner that cycles through frames."""
    
    def __init__(
        self,
        style: str = DEFAULT_SPINNER,
        frames: Sequence[str] | None = None,
    ):
        if frames:
            self._frames = frames
        elif style in SPINNERS:
            self._frames = SPINNERS[style]
        else:
            self._frames = SPINNERS[DEFAULT_SPINNER]
        
        self._index = 0
        self._frame_count = len(self._frames)
    
    def next_frame(self) -> str:
        """Get the next spinner frame and advance."""
        frame = self._frames[self._index]
        self._index = (self._index + 1) % self._frame_count
        return frame
    
    def current_frame(self) -> str:
        """Get current frame without advancing."""
        return self._frames[self._index]
    
    def reset(self) -> None:
        """Reset to first frame."""
        self._index = 0


class StatusSpinner(Spinner):
    """Spinner that changes appearance based on status."""
    
    STATUS_ICONS: dict[str, str] = {
        "idle": "○",
        "error": "✗",
        "success": "✓",
        "warning": "⚠",
    }
    
    STREAMING_FRAMES = ("▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂")
    
    def __init__(self, style: str = DEFAULT_SPINNER):
        super().__init__(style)
        self._status = "thinking"
        self._streaming_index = 0
    
    def set_status(self, status: str) -> None:
        """Set current status."""
        self._status = status
    
    def next_frame(self) -> str:
        """Get next frame based on current status."""
        if self._status in self.STATUS_ICONS:
            return self.STATUS_ICONS[self._status]
        elif self._status == "streaming":
            frame = self.STREAMING_FRAMES[self._streaming_index]
            self._streaming_index = (self._streaming_index + 1) % len(self.STREAMING_FRAMES)
            return frame
        else:
            return super().next_frame()
