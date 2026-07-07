# Architecture

Clean Architecture layering: domain logic (`analytics/`, `tracking/`) has zero framework
dependencies; adapters (`vision/`, `streaming/`, `backend/app/api`) sit at the edges;
FastAPI is the delivery mechanism, not the core. SOLID notes at the bottom.

## System diagram

```mermaid
flowchart LR
    subgraph Sources
        RTSP[RTSP cameras]
        USB[USB cameras]
        FILE[Video files]
    end

    subgraph VisionWorker["Vision worker (per-camera thread)"]
        VS[VideoSource<br/>auto-reconnect] --> DET[YOLO11 detector]
        DET --> BT[ByteTrack]
        BT --> AE[Analytics engine<br/>zones · queues · shelves · dwell]
        AE --> HB[Heatmap accumulator]
        AE --> FB[Face blur]
    end

    RTSP & USB & FILE --> VS
    AE -->|HTTP ingest| API[FastAPI backend]
    AE -.->|optional| KAFKA[(Kafka)]

    API --> PG[(PostgreSQL)]
    API --> REDIS[(Redis)]
    API --> WS[/WebSockets/]
    API --> AL[Alert engine] --> SLACK[Slack / email / webhook]
    API --> PROM[Prometheus /metrics]

    WS --> UI[React dashboard]
    API --> UI
    PROM --> GRAF[Grafana]

    CEL[Celery worker + beat] --> PG
    CEL --> AL
    MLF[MLflow] -.-> TRAIN[scripts/train.py]
    MINIO[(MinIO)] -.-> API
```

## Sequence: one frame through the pipeline

```mermaid
sequenceDiagram
    participant C as Camera
    participant W as Vision worker
    participant B as FastAPI
    participant P as PostgreSQL
    participant S as WebSocket clients
    participant A as Alert channels

    C->>W: frame (BGR)
    W->>W: YOLO detect → ByteTrack update
    W->>W: AnalyticsEngine.process (zones, queue, dwell, events)
    W->>W: blur faces, update heatmaps
    W->>B: POST /api/v1/ingest/frame (X-Worker-Key)
    B->>P: insert detections + snapshot
    B->>B: evaluate alert thresholds (dedup 5 min)
    alt threshold crossed
        B->>P: insert alert
        B->>A: Slack / email / webhook
        B-->>S: ws broadcast "alerts"
    end
    B-->>S: ws broadcast "detections:{camera_id}"
    W->>B: POST /ingest/track (when a track closes)
```

## ER diagram

```mermaid
erDiagram
    USERS ||--o{ AUDIT_LOGS : performs
    CAMERAS ||--o{ ZONES : has
    CAMERAS ||--o{ FRAMES : produces
    CAMERAS ||--o{ DETECTIONS : produces
    CAMERAS ||--o{ TRACKS : produces
    CAMERAS ||--o{ EVENTS : produces
    CAMERAS ||--o{ ALERTS : triggers
    CAMERAS ||--o{ ANALYTICS_SNAPSHOTS : aggregates
    CAMERAS ||--o{ REPORTS : summarizes
    ZONES ||--o{ EVENTS : located_in

    USERS { int id PK, string email UK, string hashed_password, enum role, bool is_active }
    CAMERAS { int id PK, string name UK, string source, enum type, enum status, float measured_fps, datetime last_heartbeat }
    ZONES { int id PK, int camera_id FK, string name, enum type, json polygon }
    DETECTIONS { int id PK, int camera_id FK, datetime ts, string class_name, float confidence, float x1y1x2y2, int track_id }
    TRACKS { int id PK, int camera_id FK, int track_id, datetime first_seen, datetime last_seen, float duration_s, float avg_speed_px_s, json trajectory, json zones_visited }
    EVENTS { int id PK, int camera_id FK, int zone_id FK, enum type, int track_id, json payload }
    ALERTS { int id PK, int camera_id FK, enum type, enum severity, text message, bool acknowledged }
    ANALYTICS_SNAPSHOTS { int id PK, int camera_id FK, datetime ts, int people_count, int unique_visitors, float avg_dwell_s, int queue_length, json zone_occupancy }
    REPORTS { int id PK, string kind, int camera_id FK, json summary, string object_key }
    AUDIT_LOGS { int id PK, int user_id FK, string action, string resource, json detail }
    FRAMES { int id PK, int camera_id FK, datetime ts, string object_key }
```

## UML: vision pipeline classes

```mermaid
classDiagram
    class VideoSource {
        +source: str
        +read() ndarray|None
        -_open() bool
        -_sleep_backoff()
    }
    class YoloDetector {
        +detect(frame) list~DetectionResult~
        +detect_batch(frames) list
        +export_onnx() str
    }
    class DetectionResult { +class_name +confidence +bbox }
    class ByteTracker { +update(detections) list~TrackedObject~ }
    class TrackedObject { +track_id +bbox +foot_point }
    class TrackStore {
        +update(...) TrackState
        +expire(now) list~TrackState~
        +dwell_times() list~float~
    }
    class AnalyticsEngine {
        +process(tracked, now) EngineOutput
        -_snapshot() dict
    }
    class HeatmapAccumulator { +add_point(x,y) +render_png(path) }
    class CameraPipeline { +run() }

    CameraPipeline --> VideoSource
    CameraPipeline --> YoloDetector
    CameraPipeline --> ByteTracker
    CameraPipeline --> AnalyticsEngine
    YoloDetector --> DetectionResult
    ByteTracker --> TrackedObject
    AnalyticsEngine --> TrackStore
    AnalyticsEngine --> HeatmapAccumulator
```

## Deployment diagram

```mermaid
flowchart TB
    subgraph Edge["Store / edge box (optional)"]
        VW2[vision-worker container<br/>ONNX / TensorRT]
    end
    subgraph Host["Docker host (laptop / VM / k8s node)"]
        FE[frontend nginx :5173]
        BE[backend uvicorn :8000]
        VW[vision-worker]
        PG[(postgres :5432)]
        RD[(redis :6379)]
        subgraph full["--profile full"]
            KF[(kafka :9092)]
            MI[(minio :9000)]
            ML[mlflow :5000]
            PR[prometheus :9090]
            GF[grafana :3001]
            CW[celery worker/beat]
        end
    end
    Browser --> FE --> BE
    VW --> BE
    VW2 -->|HTTPS ingest only| BE
    BE --> PG & RD
    PR --> BE
    GF --> PR
```

## Design decisions

- **Single writer:** vision workers never touch the DB; they POST to `/ingest/*`. Keeps
  alert evaluation, WebSocket fan-out and metrics in one consistent place, and lets edge
  workers run with outbound HTTP only.
- **Normalized coordinates** everywhere past the detector, so zone polygons survive
  resolution changes.
- **CPU-first defaults** (yolo11n @ 5 FPS, 960 px) with GPU as a config flip
  (`DEVICE=cuda:0`, uncomment `gpus: all`).
- **SOLID:** detector/tracker behind small interfaces (swap YOLO↔ONNX, ByteTrack↔BoT-SORT
  without touching analytics); `AnalyticsEngine` depends on abstractions
  (`ZoneDef`, `TrackedObject`), not on FastAPI or torch; RBAC via a composable
  `RoleChecker` dependency.
