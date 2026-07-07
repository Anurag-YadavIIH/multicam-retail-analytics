# Developer guide

## Layout
```
backend/     FastAPI app (api/ core/ models/ schemas/ crud/ services/) + alembic
vision/      detector, video source, heatmaps, privacy blur
tracking/    ByteTrack wrapper + track lifecycle store (pure python)
analytics/   zone geometry + analytics engine (pure python, fully unit-tested)
streaming/   camera worker (threads) + kafka producer
frontend/    React + TS + Tailwind + Recharts dashboard
tests/       unit / integration (API on SQLite) / e2e (synthetic pipeline)
```

## Local dev loop
```bash
pip install -r backend/requirements.txt pytest pytest-cov ruff black
docker compose up -d postgres redis
alembic upgrade head && python -m scripts.seed_db
uvicorn backend.app.main:app --reload
cd frontend && npm install && npm run dev   # proxies /api and /ws to :8000
```
Vision worker locally (needs torch): `pip install -r vision/requirements.txt` then
`BACKEND_URL=http://localhost:8000 python -m streaming.camera_worker`.

## Conventions
- Ruff + Black, line length 100 (`make lint`, `make fmt`)
- Type hints everywhere; SQLAlchemy 2.0 `Mapped[...]` style
- Domain packages (`analytics/`, `tracking/`) must not import FastAPI/torch/cv2
  (except `vision.heatmap` render); this is what keeps them testable in CI without GPUs
- New tables → new alembic revision (`alembic revision -m "..."`), never edit 0001

## Adding an analytics feature (example: fitting-room occupancy)
1. Add a `ZoneType` if needed → alembic revision
2. Extend `AnalyticsEngine.process` + snapshot dict → unit tests in `tests/unit`
3. Surface it: column on `AnalyticsSnapshot`, ingest mapping, API endpoint, dashboard card
