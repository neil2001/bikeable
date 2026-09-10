.PHONY: dev test lint build-graph

dev:
	docker compose up --build

test:
	cd backend && uv run pytest
	cd frontend && npm run build

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npx tsc -b --pretty false

build-graph:
	cd backend && uv run python ../scripts/build_city_graph.py vancouver
