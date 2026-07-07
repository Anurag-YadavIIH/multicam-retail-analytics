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

## Frontend
```
frontend/src/
  api/client.ts        fetch wrapper (JWT header) + shared types (Camera, Zone, ...)
  hooks/useWebSocket.ts auto-reconnecting WS hook
  components/           CameraStream, ZoneEditor, LiveDetectionCanvas
  pages/                one per route (Dashboard, Cameras, Alerts, Login)
```
- Normal API calls go through `api<T>()` in `client.ts`, which sends the JWT as an
  `Authorization` header. That's the default for everything.
- `<img>`/`<video>` elements can't set custom headers, so anything embedded that
  way (`CameraStream`'s live MJPEG `<img>`, `ZoneEditor`'s snapshot `<img>`) uses
  a short-lived, camera-scoped **stream token** in the URL instead of the full
  access token: `POST /cameras/{id}/stream-token` right before every
  (re)connect - see `docs/API.md` → "Live preview auth". Never put the long-lived
  access token in a URL; that's the whole point of the stream-token split.
- `ZoneEditor` draws zone polygons with plain SVG (no canvas library, keeps the
  bundle lean): the `<svg>`'s `viewBox` is kept equal to the snapshot `<img>`'s
  *rendered* pixel box via a `ResizeObserver`, so 1 SVG unit = 1 CSS pixel and
  vertex handles/strokes render correctly regardless of the camera's aspect
  ratio. Points are stored normalized `[0, 1]` (the system-wide zone
  convention) and only converted to pixels at render time, and from pixels back
  to normalized on click/drag - so a browser resize never invalidates a draft.

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
