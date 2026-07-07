# Deployment

## Local (Windows, 8 GB RAM) — lite mode
1. Install Docker Desktop (WSL2 backend) and give it ~6 GB in Settings → Resources.
2. `copy .env.example .env`
3. `python scripts/download_sample_video.py`
4. `docker compose up -d --build postgres redis backend vision-worker frontend`
5. Dashboard: http://localhost:5173 (admin@retail.local / admin12345)

Tips for small machines: keep `YOLO_MODEL=yolo11n.pt`, `INFERENCE_FPS=5`,
`FRAME_WIDTH=960`. Close the browser tab of Grafana/MLflow (full profile) if unused.

## Full profile
`docker compose --profile full up -d` adds Kafka, MinIO, MLflow, Prometheus, Grafana,
Celery worker+beat. Budget ~12 GB RAM.

## GPU (NVIDIA)
- Install the NVIDIA container toolkit; in `docker-compose.yml` uncomment `gpus: all`
  on `vision-worker`; set `DEVICE=cuda:0`, bump `INFERENCE_FPS`/model size.
- TensorRT: `python scripts/export_onnx.py --model yolo11s.pt --tensorrt` on the GPU
  host, then set `YOLO_MODEL=models/yolo11s.engine`.

## Edge deployment
The worker only needs outbound HTTP to the backend: build `docker/vision.Dockerfile`
on the edge box (Jetson: use an l4t-pytorch base), set `BACKEND_URL` and `SECRET_KEY`.
Offline mode: the worker keeps processing and retries ingest; heartbeats resume when
the link returns.

## Cloud (single VM)
Any 4 vCPU / 16 GB VM: install docker, clone, `.env` with strong `SECRET_KEY` and DB
password, `docker compose --profile full up -d`, put Caddy/nginx with TLS in front of
:5173 and :8000.

## Production checklist
- [ ] Rotate `SECRET_KEY`, DB, MinIO, Grafana credentials
- [ ] Restrict CORS origins
- [ ] Postgres volume backups (`pg_dump` cron)
- [ ] Keep `ENABLE_FACE_BLUR=true` unless you have explicit legal grounds
- [ ] Alert channels configured (Slack webhook is the 2-minute option)
