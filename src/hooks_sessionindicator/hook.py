"""
Core hook implementation for session activity indicator.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from hooks_sessionindicator.terminal import StatusLine, supports_status_line
from hooks_sessionindicator.spinner import Spinner


@dataclass
class SessionState:
    """Tracks current session state for display."""
    
    session_id: str | None = None
    started_at: datetime | None = None
    status: str = "idle"
    current_tool: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    turn_count: int = 0
    is_streaming: bool = False
    last_activity: datetime | None = None
    
    # Sub-session tracking
    active_subsessions: dict[str, str] = field(default_factory=dict)  # id -> agent name
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time since session start."""
        if not self.started_at:
            return 0.0
        return (datetime.now() - self.started_at).total_seconds()
    
    def format_elapsed(self) -> str:
        """Format elapsed time as MM:SS or HH:MM:SS."""
        secs = int(self.elapsed_seconds())
        if secs >= 3600:
            return f"{secs // 3600}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"
        return f"{secs // 60:02d}:{secs % 60:02d}"
    
    def format_tokens(self) -> str:
        """Format token counts with K suffix for thousands."""
        def fmt(n: int) -> str:
            if n >= 10000:
                return f"{n / 1000:.1f}K"
            elif n >= 1000:
                return f"{n / 1000:.1f}K"
            return str(n)
        return f"{fmt(self.input_tokens)}↑ {fmt(self.output_tokens)}↓"
    
    def seconds_since_activity(self) -> float:
        """Get seconds since last activity (for stuck detection)."""
        if not self.last_activity:
            return 0.0
        return (datetime.now() - self.last_activity).total_seconds()


class SessionIndicatorHook:
    """
    Hook that displays real-time session activity in the terminal.
    
    Subscribes to session lifecycle events and updates a status line
    showing spinner, current activity, token usage, and elapsed time.
    """
    
    # Event types this hook subscribes to
    SUBSCRIBED_EVENTS = [
        "session:start",
        "session:end",
        "session:error",
        "llm:request",
        "llm:response", 
        "llm:stream_start",
        "llm:stream_chunk",
        "llm:stream_end",
        "tool:pre",
        "tool:post",
        "turn:start",
        "turn:end",
        "task:agent_spawned",
        "task:agent_complete",
    ]
    
    def __init__(self, config: dict[str, Any]):
        """
        Initialize the session indicator hook.
        
        Config options:
            position: "bottom" | "top" | "inline" (default: "bottom")
            show_tokens: bool (default: True)
            show_elapsed: bool (default: True)
            update_interval: float (default: 0.1)
            stuck_threshold: float - seconds before showing "possibly stuck" (default: 60)
            enable_unstick_hint: bool - show Ctrl+C hint when stuck (default: True)
        """
        self.config = config
        self._state = SessionState()
        self._lock = threading.Lock()
        self._running = False
        self._update_task: asyncio.Task | None = None
        
        # Configuration
        self._position = config.get("position", "bottom")
        self._show_tokens = config.get("show_tokens", True)
        self._show_elapsed = config.get("show_elapsed", True)
        self._update_interval = config.get("update_interval", 0.1)
        self._stuck_threshold = config.get("stuck_threshold", 60.0)
        self._enable_unstick_hint = config.get("enable_unstick_hint", True)
        
        # Terminal components
        self._status_line: StatusLine | None = None
        self._spinner = Spinner()
        
        # Check terminal capability
        self._enabled = supports_status_line()
    
    @property
    def subscribed_events(self) -> list[str]:
        """Return list of events this hook subscribes to."""
        return self.SUBSCRIBED_EVENTS
    
    async def on_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Handle incoming events from the session.
        
        This is the main entry point called by the Amplifier coordinator.
        """
        if not self._enabled:
            return
            
        handler = getattr(self, f"_handle_{event_type.replace(':', '_')}", None)
        if handler:
            await handler(payload)
        
        # Update last activity timestamp
        with self._lock:
            self._state.last_activity = datetime.now()
    
    # ─────────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────────
    
    async def _handle_session_start(self, payload: dict[str, Any]) -> None:
        """Initialize display on session start."""
        with self._lock:
            self._state = SessionState(
                session_id=payload.get("session_id"),
                started_at=datetime.now(),
                status="starting",
                last_activity=datetime.now(),
            )
        
        self._running = True
        self._status_line = StatusLine(position=self._position)
        self._status_line.show()
        
        # Start background update loop
        self._update_task = asyncio.create_task(self._update_loop())
    
    async def _handle_session_end(self, payload: dict[str, Any]) -> None:
        """Clean up display on session end."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        if self._status_line:
            # Show final summary briefly
            with self._lock:
                summary = self._format_final_summary()
            self._status_line.update(summary)
            await asyncio.sleep(0.5)
            self._status_line.hide()
    
    async def _handle_session_error(self, payload: dict[str, Any]) -> None:
        """Show error state."""
        with self._lock:
            self._state.status = "error"
            error_msg = payload.get("error", "Unknown error")[:50]
            self._state.current_tool = f"Error: {error_msg}"
    
    async def _handle_llm_request(self, payload: dict[str, Any]) -> None:
        """Update state when LLM request is made."""
        with self._lock:
            self._state.status = "thinking"
            self._state.current_tool = None
            self._state.is_streaming = False
            # Track input tokens if available
            if "token_count" in payload:
                self._state.input_tokens += payload["token_count"]
    
    async def _handle_llm_response(self, payload: dict[str, Any]) -> None:
        """Update state when LLM response is received."""
        with self._lock:
            self._state.status = "processing"
            self._state.is_streaming = False
            # Track output tokens if available
            if "token_count" in payload:
                self._state.output_tokens += payload["token_count"]
            elif "usage" in payload:
                usage = payload["usage"]
                if "input_tokens" in usage:
                    self._state.input_tokens = usage["input_tokens"]
                if "output_tokens" in usage:
                    self._state.output_tokens += usage.get("output_tokens", 0)
    
    async def _handle_llm_stream_start(self, payload: dict[str, Any]) -> None:
        """Mark streaming as active."""
        with self._lock:
            self._state.status = "streaming"
            self._state.is_streaming = True
    
    async def _handle_llm_stream_chunk(self, payload: dict[str, Any]) -> None:
        """Keep activity timestamp fresh during streaming."""
        # Just updates last_activity via on_event
        pass
    
    async def _handle_llm_stream_end(self, payload: dict[str, Any]) -> None:
        """Mark streaming as complete."""
        with self._lock:
            self._state.is_streaming = False
            self._state.status = "processing"
    
    async def _handle_tool_pre(self, payload: dict[str, Any]) -> None:
        """Show which tool is being executed."""
        with self._lock:
            tool_name = payload.get("tool_name", payload.get("name", "tool"))
            self._state.status = "executing"
            self._state.current_tool = tool_name
    
    async def _handle_tool_post(self, payload: dict[str, Any]) -> None:
        """Tool execution complete."""
        with self._lock:
            self._state.status = "thinking"
            self._state.current_tool = None
    
    async def _handle_turn_start(self, payload: dict[str, Any]) -> None:
        """New turn started."""
        with self._lock:
            self._state.turn_count += 1
            self._state.status = "thinking"
    
    async def _handle_turn_end(self, payload: dict[str, Any]) -> None:
        """Turn complete, waiting for input."""
        with self._lock:
            self._state.status = "idle"
            self._state.current_tool = None
    
    async def _handle_task_agent_spawned(self, payload: dict[str, Any]) -> None:
        """Track spawned sub-session."""
        with self._lock:
            sub_id = payload.get("session_id", "unknown")
            agent = payload.get("agent", "agent")
            self._state.active_subsessions[sub_id] = agent
            self._state.status = "delegating"
            self._state.current_tool = f"→ {agent}"
    
    async def _handle_task_agent_complete(self, payload: dict[str, Any]) -> None:
        """Sub-session completed."""
        with self._lock:
            sub_id = payload.get("session_id")
            if sub_id and sub_id in self._state.active_subsessions:
                del self._state.active_subsessions[sub_id]
            
            if not self._state.active_subsessions:
                self._state.status = "thinking"
                self._state.current_tool = None
    
    # ─────────────────────────────────────────────────────────────────
    # Display Logic
    # ─────────────────────────────────────────────────────────────────
    
    async def _update_loop(self) -> None:
        """Background loop that updates the status line."""
        while self._running:
            try:
                with self._lock:
                    line = self._format_status_line()
                
                if self._status_line:
                    self._status_line.update(line)
                
                await asyncio.sleep(self._update_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Don't let display errors crash the session
                pass
    
    def _format_status_line(self) -> str:
        """Format the current status line content."""
        parts = []
        
        # Spinner + status
        spinner_char = self._spinner.next_frame()
        status_text = self._get_status_text()
        parts.append(f"{spinner_char} {status_text}")
        
        # Token counts
        if self._show_tokens:
            parts.append(self._state.format_tokens())
        
        # Elapsed time
        if self._show_elapsed:
            parts.append(self._state.format_elapsed())
        
        # Stuck warning
        if self._should_show_stuck_warning():
            stuck_time = int(self._state.seconds_since_activity())
            parts.append(f"⚠ {stuck_time}s idle")
            if self._enable_unstick_hint:
                parts.append("(Ctrl+C to interrupt)")
        
        return " │ ".join(parts)
    
    def _get_status_text(self) -> str:
        """Get human-readable status text."""
        status = self._state.status
        tool = self._state.current_tool
        
        if status == "executing" and tool:
            # Truncate long tool names
            if len(tool) > 20:
                tool = tool[:17] + "..."
            return f"executing: {tool}"
        elif status == "delegating" and tool:
            return tool  # Already formatted as "→ agent"
        elif status == "streaming":
            return "streaming response"
        elif status == "thinking":
            return "thinking"
        elif status == "processing":
            return "processing"
        elif status == "idle":
            return "waiting for input"
        elif status == "error":
            return tool or "error"
        else:
            return status
    
    def _should_show_stuck_warning(self) -> bool:
        """Check if we should show stuck warning."""
        if self._state.status == "idle":
            return False
        return self._state.seconds_since_activity() > self._stuck_threshold
    
    def _format_final_summary(self) -> str:
        """Format summary shown at session end."""
        elapsed = self._state.format_elapsed()
        tokens = self._state.format_tokens()
        turns = self._state.turn_count
        return f"✓ Session complete │ {tokens} │ {elapsed} │ {turns} turns"
