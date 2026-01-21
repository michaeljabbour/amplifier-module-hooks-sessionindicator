"""
Session Activity Indicator Hook for Amplifier.

Provides real-time visual feedback about session activity in the terminal:
- Spinner animation showing current state (thinking, executing tool, idle)
- Token consumption tracking (input/output)
- Elapsed session time
- Current tool being executed

Usage in bundle:
    hooks:
      - module: hooks-sessionindicator
        source: local
        path: ~/dev/amplifier-module-hooks-sessionindicator
        config:
          position: bottom      # bottom | top | inline
          show_tokens: true     # Show token counts
          show_elapsed: true    # Show elapsed time
          update_interval: 0.1  # Seconds between updates
"""

from hooks_sessionindicator.hook import SessionIndicatorHook

__all__ = ["SessionIndicatorHook", "mount"]
__version__ = "0.1.0"


def mount(coordinator, config: dict | None = None) -> SessionIndicatorHook:
    """
    Module entry point - called by Amplifier coordinator.
    
    Args:
        coordinator: The Amplifier coordinator instance
        config: Optional configuration dict
        
    Returns:
        The mounted hook instance
    """
    hook = SessionIndicatorHook(config or {})
    coordinator.register_hook(hook)
    return hook
