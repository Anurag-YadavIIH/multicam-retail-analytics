.PHONY: up up-lite down logs test lint fmt seed demo migrate

up:            ## Start full stack (needs ~12GB RAM)
	docker compose --profile full up -d --build

up-lite:       ## Start lite stack for 8GB machines
	docker compose up -d --build postgres redis backend vision-worker frontend

down:
	docker compose --profile full down

logs:
	docker compose logs -f backend vision-worker

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m scripts.seed_db

demo:          ## Fetch clips + bring up the lite stack - seeds itself, see docs/DEMO.md
	python scripts/download_sample_video.py
	docker compose up -d --build postgres redis backend vision-worker frontend

test:
	pytest

lint:
	ruff check . && black --check .

fmt:
	ruff check --fix . && black .
