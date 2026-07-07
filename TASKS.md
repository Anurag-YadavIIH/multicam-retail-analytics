# Build checklist

## Done ✅
- [x] Repo scaffold, .env.example, Makefile, pyproject (ruff/black/pytest)
- [x] Docker Compose: lite (8 GB) + full profile (Kafka/MinIO/MLflow/Prometheus/Grafana/Celery)
- [x] PostgreSQL schema (users, cameras, zones, frames, detections, tracks, events,
      alerts, analytics_snapshots, reports, audit_logs) + Alembic migration + seed
- [x] JWT auth, refresh tokens, RBAC (admin/manager/viewer), audit logs
- [x] Camera CRUD + zones API, heartbeat/health, worker ingest endpoints
- [x] Analytics API: overview, traffic, snapshots, peak hours, dwell
- [x] Alert engine: thresholds, 5-min dedup, Slack/email/webhook dispatch
- [x] WebSockets: detections / alerts / analytics channels
- [x] Vision: YOLO11 detector (batch, GPU, ONNX-ready), resilient VideoSource,
      face blur, heatmap accumulator + PNG rendering
- [x] Tracking: ByteTrack wrapper, track store (trajectory/speed/dwell/zones, recovery)
- [x] Analytics engine: counts, unique visitors, dwell, zone/queue/shelf, loitering,
      restricted zones, entry/exit events
- [x] Camera worker: per-camera threads, throttling, heartbeats, Kafka (optional)
- [x] Celery: health sweep, daily reports, retention purge (beat schedules)
- [x] Frontend: login, dashboard (KPIs, live detection canvas, traffic chart,
      live alert feed), cameras CRUD, alerts page — dark ops theme
- [x] Monitoring: Prometheus metrics + Grafana dashboard provisioning
- [x] MLOps: MLflow train script + model registry, DVC pipeline, ONNX/TensorRT export
- [x] Datasets: sample video fetcher, Kaggle/MOT/SKU-110K downloader + docs
- [x] Tests: 86 passing (unit/integration/e2e), ~89% coverage on backend+domain
- [x] CI: ruff, black, pytest, docker builds, Trivy scan
- [x] Docs: README, ARCHITECTURE (mermaid: system/sequence/ER/UML/deployment),
      API, DEPLOYMENT, TRAINING, INFERENCE, DEVELOPER_GUIDE, CONTRIBUTING
- [x] MJPEG live video preview + snapshot (Redis frame cache), scoped short-lived
      stream tokens for `<img>`/WS auth, live preview panel on the Cameras page

## Next (great Claude Code sessions) 🚧
- [ ] Zone editor UI (draw polygons over a camera snapshot) — can now reuse
      GET /cameras/{id}/snapshot for the background image
- [ ] Cross-camera Re-ID service (OSNet embeddings over Kafka closed-track topic)
- [ ] Occupancy forecasting (Prophet/ARIMA on analytics_snapshots)
- [ ] Anomaly detection on traffic/queue series
- [ ] Heatmap gallery page + report PDF export
- [ ] k8s manifests in deployment/ (Helm chart)
