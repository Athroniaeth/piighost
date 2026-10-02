# Load environment variables from .env file if it exists
.PHONY: format lint test

format:
	uv run ruff format .
	uv run ruff check --fix .

# pyrefly runs on explicit paths: it resolves its default include glob against the
# ignore files it finds, which silently matches nothing in a git worktree and turns
# the type gate into a no-op that still exits non-zero.
lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run pyrefly check src tests examples docs/tools
	uv run bandit -c pyproject.toml -r src examples
	uv run python skills/piighost-docs/scripts/audit.py

test:
	uv run pytest
