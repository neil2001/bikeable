.PHONY: dev test lint

dev:
	docker compose up --build

test:
	cd backend && uv run pytest
	cd frontend && npm run build

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npx tsc -b --pretty false
