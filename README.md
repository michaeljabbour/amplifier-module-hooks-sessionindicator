# Session Indicator Hook for Amplifier

Real-time visual feedback about session activity in the terminal.

```
⠋ executing: bash │ 1.2K↑ 3.4K↓ │ 02:34
```

## Features

- **Spinner animation** - Shows current activity state (thinking, executing, streaming)
- **Token tracking** - Input/output token consumption
- **Elapsed time** - Session duration
- **Tool display** - Shows which tool is currently executing
- **Stuck detection** - Warns when session appears stuck (configurable threshold)
- **Unstick shortcuts** - Ctrl+C escalation pattern to recover stuck sessions

## Installation

```bash
# From source
pip install -e ~/dev/amplifier-module-hooks-sessionindicator

# Or reference directly in your bundle
```

## Usage

Add to your bundle configuration:

```yaml
hooks:
  - module: hooks-sessionindicator
    source: local
    path: ~/dev/amplifier-module-hooks-sessionindicator
    config:
      position: bottom        # bottom | inline
      show_tokens: true       # Show token counts
      show_elapsed: true      # Show elapsed time
      update_interval: 0.1    # Seconds between updates
      stuck_threshold: 60     # Seconds before showing stuck warning
```

## Display Format

```
⠋ thinking │ 1.2K↑ 3.4K↓ │ 02:34
⠙ executing: grep │ 1.5K↑ 3.8K↓ │ 02:45
⠹ → amplifier-expert │ 2.1K↑ 4.2K↓ │ 03:12
⠸ streaming response │ 2.3K↑ 5.1K↓ │ 03:28
⚠ 65s idle (Ctrl+C to interrupt)
✓ Session complete │ 12.4K↑ 45.2K↓ │ 15:42 │ 8 turns
```

## Keyboard Shortcuts

Cross-platform shortcuts for recovering stuck sessions:

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Cancel current operation (1st press) |
| `Ctrl+C` ×2 | Abort current turn (within 2 seconds) |
| `Ctrl+C` ×3 | Emergency exit (within 2 seconds) |

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `position` | string | `"bottom"` | Status line position (`bottom` or `inline`) |
| `show_tokens` | bool | `true` | Display token consumption |
| `show_elapsed` | bool | `true` | Display elapsed time |
| `update_interval` | float | `0.1` | Seconds between display updates |
| `stuck_threshold` | float | `60.0` | Seconds of inactivity before stuck warning |
| `enable_unstick_hint` | bool | `true` | Show Ctrl+C hint when stuck |

## Environment Variables

| Variable | Effect |
|----------|--------|
| `NO_COLOR` | Disable all ANSI colors |
| `AMPLIFIER_NO_STATUS` | Disable status line entirely |

## Events Subscribed

The hook observes these Amplifier lifecycle events:

- `session:start`, `session:end`, `session:error`
- `llm:request`, `llm:response`, `llm:stream_*`
- `tool:pre`, `tool:post`
- `turn:start`, `turn:end`
- `task:agent_spawned`, `task:agent_complete`

## Development

```bash
cd ~/dev/amplifier-module-hooks-sessionindicator

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type check
pyright

# Lint
ruff check .
```

## License

MIT
