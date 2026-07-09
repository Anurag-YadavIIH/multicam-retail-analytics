# Inference

## Pipeline
`VideoSource → YoloDetector → ByteTracker → AnalyticsEngine → ingest API`

Frames are resized to `FRAME_WIDTH` and throttled to `INFERENCE_FPS` before the
detector — this is the main knob trading accuracy vs CPU load.

## Backends
| Backend | How | When |
|---|---|---|
| PyTorch CPU | default (`DEVICE=cpu`) | laptops, ≤5 FPS/camera |
| PyTorch CUDA | `DEVICE=cuda:0` + compose `gpus: all` | any NVIDIA GPU |
| ONNX Runtime | `scripts/export_onnx.py`, set `YOLO_MODEL=models/yolo11n.onnx` | CPU speedup, edge |
| TensorRT | `--tensorrt` export on GPU host, `YOLO_MODEL=...engine` | max GPU throughput |

Batch inference: `YoloDetector.detect_batch()` runs one forward pass for N frames —
wire multiple camera threads into a shared batching queue for multi-GPU / high-density
deployments (each worker replica can also be pinned to a GPU via `CUDA_VISIBLE_DEVICES`
for multi-GPU scale-out).

## Benchmark your machine
```bash
python -m scripts.benchmark_inference --model yolo11n.pt --device cpu
```
Typical: yolo11n @960px ≈ 8–15 FPS on a modern laptop CPU; ≈150+ FPS on an RTX GPU.

## Cross-camera re-identification (extension point)
`Track.trajectory` + per-track crops give you the inputs for an OSNet/embedding-based
Re-ID matcher; add a service that consumes closed tracks from Kafka and links IDs
across cameras by embedding distance + time/geometry constraints.
