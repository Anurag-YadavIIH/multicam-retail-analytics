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

## Testing with a phone as an RTSP camera

Every camera in this repo's demos so far is a looping video file - genuine
live detection, and the `VideoSource` reconnect path for a real,
occasionally-flaky stream, has never actually been exercised. A phone
running an IP-camera app is a real RTSP source and the fastest way to do
that without buying hardware.

**Android - [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)
(free):**

1. Install it, open it, scroll down and tap **Start server**.
2. It shows an IP:port, e.g. `192.168.1.57:8080` - that's the phone's address
   on your LAN, not a public one.
3. RTSP URL: `rtsp://192.168.1.57:8080/h264_ulaw.sdp` (or `h264_pcm.sdp` -
   both are exposed out of the box).

**iOS - [OctoStream RTSP Streamer](https://apps.apple.com/us/app/octostream-rtsp-streamer/id6474928937)
(free):**

1. Install it, open it, select your camera feed.
2. It displays the RTSP URL directly in the app - use that as-is.

**Register it** (phone and the machine running `docker compose` must be on
the same Wi-Fi/LAN):

- Dashboard → Cameras → Add camera → `type: rtsp`, `source:` the URL above, or
- `configs/cameras.example.yaml` + `python scripts/register_cameras.py`
  (see the file for the exact entry shape - the RTSP example there is a
  placeholder; put your phone's real URL in its `source` field).

No Docker network changes needed: the vision-worker container reaches the
phone the same way any outbound connection from the container reaches your
LAN, on the default bridge network.

**What this actually tests that the demo video can't:** walk out of Wi-Fi
range, lock the phone's screen, or force-close the app, and watch
`vision/video_source.py`'s reconnect logic in `docker compose logs -f
vision-worker` (`stream lost (...), reconnecting`) - then bring the stream
back and confirm it picks back up without restarting the worker.

## Production checklist
- [ ] Rotate `SECRET_KEY`, DB, MinIO, Grafana credentials
- [ ] Restrict CORS origins
- [ ] Postgres volume backups (`pg_dump` cron)
- [ ] Keep `ENABLE_FACE_BLUR=true` unless you have explicit legal grounds
- [ ] Alert channels configured (Slack webhook is the 2-minute option)
