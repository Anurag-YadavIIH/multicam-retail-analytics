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
- [x] Tests: 134 passing (unit/integration/e2e), ~91% coverage on backend+domain
- [x] CI: ruff, black, pytest, docker builds, Trivy scan
- [x] Docs: README, ARCHITECTURE (mermaid: system/sequence/ER/UML/deployment),
      API, DEPLOYMENT, TRAINING, INFERENCE, DEVELOPER_GUIDE, CONTRIBUTING
- [x] MJPEG live video preview + snapshot (Redis frame cache), scoped short-lived
      stream tokens for `<img>`/WS auth, live preview panel on the Cameras page
- [x] Zone editor UI: plain-SVG polygon draw/edit/drag over the snapshot
      endpoint, zone list with edit/delete, PATCH /cameras/{id}/zones/{zone_id}
- [x] Cross-camera Re-ID service — design in `docs/REID.md` (transport-agnostic
      matcher, not Kafka-only; embeddings extracted on-worker, never raw crops).
      Session 1/3: `identities` table, `tracks.embedding`/`identity_id`,
      `POST /ingest/reid` + tests. Session 2/3: OSNet ONNX export script,
      on-worker extraction (best-crop heuristic, fail-soft), and the matcher
      wired inline into `/ingest/reid`. Session 3/3: `GET
      /reid/identities` + `GET /reid/identities/{id}/journey` + minimal
      "Identities" frontend page; real-model export (throwaway torch<2.6
      container - torch>=2.6 breaks torchreid's checkpoint loading, see
      `docs/REID.md`); `scripts/calibrate_reid.py` picked an initial
      `REID_MATCH_THRESHOLD` of 0.83 from real embeddings; **validated live**
      by running the real stack against the looping demo video for hours -
      one person correctly re-matched 36 times, two others 18 and 9 times,
      zero false merges across the 4 identities (see `docs/REID.md`). That's
      **same-camera** re-identification only, on the bundled single-camera
      demo video - the matcher itself has no camera-specific logic, so the
      architecture is cross-camera-ready, but cross-camera matching isn't
      demonstrated here. **Kafka fan-out for the matcher was descoped from
      this project** (see below) rather than shipped unverified.

## Next (great Claude Code sessions) 🚧
- [ ] Kafka fan-out for the Re-ID matcher (`docs/REID.md` "Transport" table,
      full-profile row) — descoped, not implemented. The matcher function
      (`backend/app/services/reid_matcher.py`) is already transport-agnostic
      by design specifically so this can be added later without changing
      matching logic: a consumer (or Celery task under the existing
      `celery-worker` container) would read a `reid-tracks` Kafka topic and
      call `match_or_create_identity` the same way `/ingest/reid` already
      does inline. Not built because the full profile can't be verified
      live on this project's 8 GB target machine, and unverified code paths
      don't ship here.
- [ ] Occupancy forecasting (Prophet/ARIMA on analytics_snapshots)
- [ ] Anomaly detection on traffic/queue series
- [ ] Heatmap gallery page + report PDF export
- [ ] k8s manifests in deployment/ (Helm chart)
