# Load environment variables from .env file if it exists
.PHONY: lint

lint:
	-uv run ruff format .
	-uv run ruff check --fix .
	-uv run pyrefly check .
