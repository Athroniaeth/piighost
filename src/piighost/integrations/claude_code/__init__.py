"""Claude Code hooks integration (optional: client for the runner).

handle_hook is pure and needs only the core library, so it imports eagerly. The
run entrypoint builds a PIIGhostClient, which needs the httpx optional dependency,
so it is imported lazily: reaching for run without the extra raises a helpful
ImportError, while importing this package never pulls httpx in.
"""

from typing import Any

from piighost.integrations.claude_code.hooks import handle_hook

__all__ = ["handle_hook", "run"]


def __getattr__(name: str) -> Any:
    """Import run on demand so its httpx dependency stays optional."""
    if name == "run":
        from piighost.integrations.claude_code.runner import run

        return run

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
