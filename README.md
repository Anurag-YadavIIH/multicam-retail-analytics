# Smart Multi-Camera Retail Analytics System

[![CI](https://github.com/Anurag-YadavIIH/multicam-retail-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/Anurag-YadavIIH/multicam-retail-analytics/actions/workflows/ci.yml)

Production-style computer-vision platform for retail stores: multi-camera ingestion,
YOLO detection, ByteTrack multi-object tracking, zone/queue/shelf analytics, real-time
alerts, a React ops dashboard, and full observability — all runnable on a laptop with
Docker Compose.

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL · Redis · Celery · Kafka ·
Ultralytics YOLO11 · ByteTrack (supervision) · ONNX Runtime · React + TypeScript + Vite +
Tailwind + Recharts · MinIO · MLflow · DVC · Prometheus · Grafana · GitHub Actions

```
cameras (RTSP/USB/file) ──► vision worker ──► FastAPI ingest ──► PostgreSQL
                             YOLO11 + ByteTrack     │                 │
                             zones/queues/shelves   ├─► WebSockets ──► React dashboard
                             face blur, heatmaps    ├─► Alerts (Slack/email/webhook)
                                                    └─► Prometheus ──► Grafana
```

## Demo

Draw a zone on a live camera feed and watch it show up in the analytics within
seconds — that's the core loop: **Cameras → select a camera → Edit zones → draw
a queue polygon → Save → Dashboard queue/dwell metrics update live**, all from
the same looping demo video. Spin up the lite stack below (~2 min), open
http://localhost:5173, and log in with `admin@retail.local` / `admin12345`.

## Quick start (8 GB RAM friendly — "lite" mode)

Requirements: Docker Desktop, ~6 GB free RAM, ~8 GB disk.

```bash
cp .env.example .env
python scripts/download_sample_video.py        # fetches a retail demo clip
docker compose up -d --build postgres redis backend vision-worker frontend
```

Then open:

| URL | What | Login |
|---|---|---|
| http://localhost:5173 | Ops dashboard | admin@retail.local / admin12345 |
| http://localhost:8000/docs | Swagger / OpenAPI | JWT via /auth/login |
| http://localhost:8000/metrics | Prometheus metrics | — |

The seeded `demo-entrance` camera plays the sample video on loop; within a minute you
will see live detections streaming on the dashboard, traffic charts filling in, and
queue alerts firing when the configured thresholds are crossed.

## Full stack (Kafka, MinIO, MLflow, Prometheus, Grafana, Celery)

Needs ~12 GB RAM (a cloud VM or a bigger desktop):

```bash
docker compose --profile full up -d --build
# Grafana http://localhost:3001 (admin/admin) · MLflow http://localhost:5000
# MinIO console http://localhost:9001 · Prometheus http://localhost:9090
```

## Feature map

| Area | Where |
|---|---|
| Camera CRUD, RTSP/USB/file, health + auto-reconnect | `backend/app/api/v1/cameras.py`, `vision/video_source.py` |
| YOLO11 detection, batch, GPU, class remapping | `vision/detector.py`, `configs/classes.yaml` |
| ByteTrack, persistent IDs, trajectory, speed, lost-track recovery | `tracking/` |
| Visitor counts, dwell, zone occupancy, peak hours, queues, shelves, loitering, restricted zones | `analytics/engine.py` |
| Heatmaps (movement/footfall/queue/shelf) → PNG | `vision/heatmap.py` |
| Alert engine (Slack/email/webhook) with dedup | `backend/app/services/alert_service.py` |
| JWT auth + RBAC (admin/manager/viewer), audit logs | `backend/app/core/`, `backend/app/api/v1/users.py` |
| WebSockets: detections/alerts/analytics | `backend/app/api/v1/ws.py` |
| Live MJPEG preview + snapshot (Redis frame cache) | `backend/app/api/v1/cameras.py`, `vision/preview.py` |
| Zone editor (draw/edit polygons over a snapshot, plain SVG) | `frontend/src/components/ZoneEditor.tsx` |
| Cross-camera Re-ID: on-worker OSNet embeddings, inline gallery matcher | `vision/reid.py`, `backend/app/services/reid_matcher.py`, `docs/REID.md` |
| Kafka event bus (optional) | `streaming/kafka_client.py` |
| Celery: health sweeps, daily reports, retention | `backend/app/services/tasks.py` |
| Prometheus metrics + Grafana dashboard | `monitoring/` |
| MLflow training + model registry, DVC pipeline | `scripts/train.py`, `dvc.yaml` |
| ONNX / TensorRT export | `scripts/export_onnx.py` |
| Face blurring (privacy by default) | `vision/privacy.py` |
| LLM daily briefing (Groq/OpenAI) | `scripts/report_narrator.py` |

## Real cameras & datasets

Add an RTSP camera from the dashboard (Cameras → Add camera) or in bulk via
`configs/cameras.example.yaml` + `python scripts/register_cameras.py`. USB webcams use
the device index (`0`).

Datasets (Kaggle retail people/RPC, SKU-110K, MOT17/20, CrowdHuman…):
`python scripts/download_datasets.py --list` — see `datasets/README.md`. Fine-tuning
with MLflow tracking: `docs/TRAINING.md`.

## Development

```bash
pip install -r backend/requirements.txt -r vision/requirements.txt
pip install pytest pytest-cov ruff black
pytest                       # 126 tests, ~90% coverage on backend/analytics/tracking/vision
ruff check . && black .
cd frontend && npm install && npm run dev
```

Docs: [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) ·
[Deployment](docs/DEPLOYMENT.md) · [Training](docs/TRAINING.md) ·
[Inference](docs/INFERENCE.md) · [Developer guide](docs/DEVELOPER_GUIDE.md) ·
[Contributing](docs/CONTRIBUTING.md)

## License

MIT — see [LICENSE](LICENSE).
