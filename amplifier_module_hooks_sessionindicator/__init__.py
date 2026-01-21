"""
Session Activity Indicator Hook for Amplifier.

Provides real-time visual feedback about session activity in the terminal:
- Spinner animation showing current state (thinking, executing tool, idle)
- Token consumption tracking (input/output)
- Elapsed session time
- Current tool being executed
"""

# Amplifier module metadata
__amplifier_module_type__ = "hook"
__version__ = "0.1.0"

import asyncio
import logging
import sys
import threading
from datetime import datetime
from typing import Any

from amplifier_core import HookResult, ModuleCoordinator

from amplifier_module_hooks_sessionindicator.spinner import Spinner
from amplifier_module_hooks_sessionindicator.terminal import StatusLine, supports_status_line

logger = logging.getLogger(__name__)

__all__ = ["SessionIndicatorHook", "mount"]


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """
    Mount the session indicator hook.

    Args:
        coordinator: Module coordinator
        config: Optional configuration
            - position: Status line position ("bottom" or "inline", default: "bottom")
            - show_tokens: Show token counts (default: True)
            - show_elapsed: Show elapsed time (default: True)
            - update_interval: Seconds between display updates (default: 0.1)
            - stuck_threshold: Seconds before showing stuck warning (default: 60.0)
            - spinner_style: Spinner animation style (default: "dots")

    Returns:
        Optional cleanup function
    """
    config = config or {}
    hook = SessionIndicatorHook(coordinator, config)
    hook.register(coordinator.hooks)
    logger.info("Mounted hooks-sessionindicator")
    
    async def cleanup():
        hook.stop()
        logger.debug("Session indicator hook cleaned up")
    
    return cleanup


class SessionIndicatorHook:
    """
    Hook that displays real-time session activity in the terminal.
    """

    def __init__(self, coordinator: ModuleCoordinator, config: dict[str, Any]):
        self.coordinator = coordinator
        
        # Configuration
        self.position = config.get("position", "bottom")
        self.show_tokens = config.get("show_tokens", True)
        self.show_elapsed = config.get("show_elapsed", True)
        self.update_interval = config.get("update_interval", 0.1)
        self.stuck_threshold = config.get("stuck_threshold", 60.0)
        self.spinner_style = config.get("spinner_style", "dots")
        self.priority = config.get("priority", 100)  # Run after other hooks
        
        # State tracking
        self.started_at: datetime | None = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.current_state = "idle"
        self.current_tool: str | None = None
        self.current_agent: str | None = None
        self.last_activity = datetime.now()
        
        # Display components
        self.spinner = Spinner(style=self.spinner_style)
        self.status_line: StatusLine | None = None
        self._update_thread: threading.Thread | None = None
        self._running = False
        
        # Check if terminal supports status line
        self._enabled = supports_status_line()
        if not self._enabled:
            logger.debug("Terminal doesn't support status line, hook disabled")

    def register(self, hooks):
        """Register this hook for relevant lifecycle events."""
        if not self._enabled:
            return
            
        # Session lifecycle
        hooks.register("session:start", self.on_session_start, priority=self.priority, name="hooks-sessionindicator")
        hooks.register("session:end", self.on_session_end, priority=self.priority, name="hooks-sessionindicator")
        
        # Provider/LLM events
        hooks.register("provider:request", self.on_provider_request, priority=self.priority, name="hooks-sessionindicator")
        hooks.register("provider:response", self.on_provider_response, priority=self.priority, name="hooks-sessionindicator")
        
        # Tool events
        hooks.register("tool:pre", self.on_tool_pre, priority=self.priority, name="hooks-sessionindicator")
        hooks.register("tool:post", self.on_tool_post, priority=self.priority, name="hooks-sessionindicator")
        
        # Content streaming
        hooks.register("thinking:delta", self.on_thinking, priority=self.priority, name="hooks-sessionindicator")
        hooks.register("content_block:delta", self.on_content, priority=self.priority, name="hooks-sessionindicator")
        
        logger.debug("Session indicator registered for events")

    def _start_display(self):
        """Start the background display update thread."""
        if self._running or not self._enabled:
            return
            
        self._running = True
        self.status_line = StatusLine(position=self.position)
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def _update_loop(self):
        """Background thread that updates the status line."""
        while self._running:
            try:
                self._render_status()
                threading.Event().wait(self.update_interval)
            except Exception as e:
                logger.debug(f"Status line update error: {e}")

    def _render_status(self):
        """Render the current status to the terminal."""
        if not self.status_line or not self._enabled:
            return
            
        parts = []
        
        # Spinner with state
        frame = self.spinner.next_frame()
        if self.current_state == "thinking":
            parts.append(f"{frame} thinking")
        elif self.current_state == "streaming":
            parts.append(f"{frame} streaming")
        elif self.current_state == "tool":
            tool_name = self.current_tool or "tool"
            parts.append(f"{frame} {tool_name}")
        elif self.current_state == "agent":
            agent_name = self.current_agent or "agent"
            parts.append(f"{frame} → {agent_name}")
        else:
            parts.append(f"{frame} idle")
        
        # Token counts
        if self.show_tokens:
            input_k = f"{self.input_tokens / 1000:.1f}K" if self.input_tokens >= 1000 else str(self.input_tokens)
            output_k = f"{self.output_tokens / 1000:.1f}K" if self.output_tokens >= 1000 else str(self.output_tokens)
            parts.append(f"{input_k}↑ {output_k}↓")
        
        # Elapsed time
        if self.show_elapsed and self.started_at:
            elapsed = datetime.now() - self.started_at
            minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
            if minutes >= 60:
                hours, minutes = divmod(minutes, 60)
                parts.append(f"{hours}:{minutes:02d}:{seconds:02d}")
            else:
                parts.append(f"{minutes:02d}:{seconds:02d}")
        
        # Stuck warning
        idle_seconds = (datetime.now() - self.last_activity).total_seconds()
        if idle_seconds > self.stuck_threshold:
            parts.append(f"⚠ {int(idle_seconds)}s idle")
        
        status = " │ ".join(parts)
        self.status_line.update(status)

    def stop(self):
        """Stop the display update thread."""
        self._running = False
        if self.status_line:
            self.status_line.clear()
            self.status_line = None

    # Event handlers
    async def on_session_start(self, event: str, data: dict[str, Any]) -> HookResult:
        self.started_at = datetime.now()
        self.last_activity = datetime.now()
        self._start_display()
        return HookResult()

    async def on_session_end(self, event: str, data: dict[str, Any]) -> HookResult:
        self.stop()
        return HookResult()

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "thinking"
        self.last_activity = datetime.now()
        return HookResult()

    async def on_provider_response(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "idle"
        self.last_activity = datetime.now()
        # Update token counts if available
        if "usage" in data:
            usage = data["usage"]
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
        return HookResult()

    async def on_tool_pre(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "tool"
        self.current_tool = data.get("tool_name", "tool")
        self.last_activity = datetime.now()
        
        # Check if it's a task/agent spawn
        if self.current_tool == "task":
            self.current_state = "agent"
            self.current_agent = data.get("input", {}).get("agent", "agent")
        
        return HookResult()

    async def on_tool_post(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "idle"
        self.current_tool = None
        self.current_agent = None
        self.last_activity = datetime.now()
        return HookResult()

    async def on_thinking(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "thinking"
        self.last_activity = datetime.now()
        return HookResult()

    async def on_content(self, event: str, data: dict[str, Any]) -> HookResult:
        self.current_state = "streaming"
        self.last_activity = datetime.now()
        return HookResult()
