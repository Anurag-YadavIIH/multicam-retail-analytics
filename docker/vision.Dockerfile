# ---- Vision worker image (torch-cpu). For GPU, swap base for
#      nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 + torch cu124 wheels. ----
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY vision/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY vision /app/vision
COPY tracking /app/tracking
COPY analytics /app/analytics
COPY streaming /app/streaming
COPY configs /app/configs

# Pre-download the nano model into the image so first boot is instant
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

CMD ["python", "-m", "streaming.camera_worker"]
