# Cross-camera Re-ID

Links a person's tracks across different cameras into one global "identity" by
comparing appearance embeddings, so a customer who walks from the entrance
camera to the checkout camera is recognized as the same person without any
biometric ID system - just embedding similarity, time, and (later) geometry.

This is a multi-session build. **This document covers the full design**,
including the transport-agnostic Kafka fan-out path for `--profile full` -
but that path is **descoped from implementation** (see "Constraints" #1 and
"Transport" below): the design stays because it costs nothing to keep the
matcher decoupled from transport, but the actual Kafka producer/consumer code
was never written, because this project's 8 GB target machine can't run
`--profile full` well enough to verify it live, and unverified code doesn't
ship here.

Implemented: the data layer (session 1); on-worker OSNet extraction and the
matcher wired inline into `/ingest/reid` (session 2). Session 3 (in
progress): the `journeys`/list read endpoints, a calibration script, the
real exported model, and threshold calibration against it. See "Session
breakdown" for exactly what's done vs. pending as this session progresses.

## Constraints, and where this design departs from TASKS.md / INFERENCE.md

Two things in the existing task description don't fit this project's actual
hardware target (Windows, 8 GB RAM, CPU-only, lite profile by default) or its
current pipeline, so this design deliberately departs from them:

1. **TASKS.md: "OSNet embeddings over Kafka closed-track topic."** Kafka only
   exists under `--profile full`, which already barely fits in 8 GB. Making
   Re-ID *require* Kafka would mean the feature simply doesn't work in the
   default lite profile. This design splits the **matching algorithm** (a
   plain, transport-agnostic Python function) from **transport** (how a
   "track closed, embedding ready" event reaches it): lite mode calls it
   inline, synchronously, right after the ingest endpoint stores the
   embedding; full profile *could* additionally fan it out via Kafka to a
   consumer for horizontal scaling - same function either way, no Kafka
   dependency to unit-test matching. **That Kafka fan-out is designed but
   deliberately not implemented** (see "Transport" below and
   `TASKS.md`): this project's 8 GB target machine can't run `--profile
   full` well enough to verify it live, and this codebase doesn't ship
   unverified code paths. The matcher is already transport-agnostic
   specifically so this can be added later without touching matching logic.
2. **INFERENCE.md: "`Track.trajectory` + per-track crops give you the
   inputs."** Nothing in the pipeline stores per-track image crops anywhere
   today - the worker only ever sends metadata to the backend, plus an
   unrelated rolling live-preview JPEG with a 5s TTL. Shipping raw crops to a
   separate service would also cut against the existing "blur faces before a
   frame leaves the worker" privacy posture. Instead, the embedding is
   **extracted on the vision worker**, where the pixel data actually lives,
   and only the resulting vector - never a raw crop - is ever sent to the
   backend.
3. **TASKS.md's "a service that consumes..."** implies a new standalone
   microservice. Given full profile already barely fits, the matcher is a
   plain importable function, not a new always-on container: it runs inline
   in the ingest request (lite) or from a Celery task under the existing
   `celery-worker` container (full profile) - no new service to run or test.

## Architecture

```
vision worker                          backend
─────────────                          ───────
track closes
  │
  ├─ pick best crop(s) from the track's lifetime (highest detection
  │  confidence / largest bbox)
  │
  ├─ OSNet (osnet_x0_25, ONNX Runtime, CPU) → 512-dim embedding
  │
  ├─ POST /ingest/track  (existing - track summary, unchanged)
  │
  └─ POST /ingest/reid   ({camera_id, track_id, embedding})
                                          │
                                          ├─ store embedding on the Track row
                                          │
                                          └─ invoke match_or_create_identity(db, track, embedding)
                                             ├─ lite: called inline, same request (implemented)
                                             └─ full: designed to also publish to a Kafka
                                                topic for a consumer (or Celery task) to call
                                                the same matcher function - NOT implemented,
                                                see "Transport" and TASKS.md
```

### Extraction (vision worker) - implemented

- Model: **osnet_x0_25** (the lightest OSNet width variant), exported to ONNX
  once, offline (`scripts/export_reid_onnx.py`). `onnxruntime` is already a
  runtime dependency (used for the detector's optional ONNX path) - Re-ID
  adds no new runtime dependency. `torchreid`/`torch` are only ever used by
  the offline export script, never installed in the vision-worker image.
- **Getting the .onnx file into the container:** neither of the two options
  originally floated (export at Docker build time, or download a
  pre-exported artifact at build time) is what shipped. Both would add a
  network dependency to `docker compose build` - `torchreid`'s pretrained
  weights come from Google Drive via `gdown`, which is well known to be
  flaky/rate-limited, and a hosted "pre-exported artifact" URL is just
  another external dependency the build would fail without. Instead: the
  vision-worker service already bind-mounts `./models:/app/models` in
  `docker-compose.yml` (used today for heatmap PNGs), so
  `models/reid/osnet_x0_25.onnx` just needs to exist on the host - produced
  once by running the export script locally, never during a build. Zero
  Dockerfile changes, zero build-time network dependency, and it's exactly
  as reliable as the build already was. If the file is absent,
  `ReidExtractor` fails soft (`.enabled = False`) and the rest of the
  pipeline is unaffected. See `models/reid/README.md`.
- **Best-crop heuristic:** for each active person track, the worker keeps the
  single frame with the **largest bbox area among frames where detection
  confidence clears `MIN_CROP_CONFIDENCE` (0.5)** - a cheap proxy for "the
  subject is closest/most front-on to the camera," recomputed every frame in
  `CameraPipeline._update_best_crops` and consumed once when the track
  closes. The crop is copied out **before** face blur is drawn onto the
  frame (see Privacy considerations), and is discarded (whether or not
  extraction/ingest succeeds) as soon as the track closes - crops for
  in-progress tracks are the only ones ever held in memory.
- Input: the best crop, resized to OSNet's expected `256×128`,
  ImageNet-normalized (`vision/reid.py:preprocess`).
- Output: a **512-dim** float vector, L2-normalized before it's sent
  (`vision/reid.py:ReidExtractor.extract`).
- Extraction happens once per closed track (not per frame) - cheap enough on
  CPU at that rate even on this hardware. Fails soft throughout: a missing
  model, a broken crop, or an inference error all just skip that one track's
  Re-ID (logged), never the tracking pipeline itself.

### Matching (pure function) - implemented, wired inline

`match_or_create_identity(db, track, embedding, *, ttl_hours, threshold) ->
Identity` (`backend/app/services/reid_matcher.py`) - takes a DB session, a
track, and its embedding; does the following, with no knowledge of Kafka,
Redis, or HTTP:

1. Load the **active gallery**: all `identities` with
   `last_seen > now() - ttl_hours` (default 24h - configurable). Rows older
   than that are excluded from matching but never deleted (kept for
   historical journeys / audit); a separate retention task can hard-delete
   very old ones later, matching the existing Celery retention-purge pattern.
2. Cosine similarity between the track's embedding and every active
   identity's representative embedding.
3. Best match above the similarity threshold (**0.65** by default, tunable
   via `REID_MATCH_THRESHOLD` - not yet calibrated against real embeddings;
   that's session 3, once there's real camera footage to tune against) →
   link the track to that identity, update its `last_seen`/`track_count`.
   No match above threshold → create a new identity from this track's
   embedding.

It's wired inline into `/ingest/reid`, immediately after the embedding is
stored - this **is** the lite-mode transport path described below, not a
placeholder for it.

**Scale assumption, stated explicitly:** this is `O(gallery size)` cosine
comparisons per closed track, run inline in the request path in lite mode.
That's fine up to roughly **10k active identities** in the TTL window on a
CPU-only 8 GB box (a few milliseconds of vector math). Beyond that order of
magnitude, the fix is either (a) move matching off the request path via
Kafka/Celery so ingest latency doesn't depend on gallery size, and/or (b) an
indexed similarity search (pgvector, or an in-memory ANN index rebuilt
periodically) instead of a linear scan. Neither is needed at this project's
target scale (a handful of store cameras), so neither is built now.

### Transport

| Profile | How a closed track's embedding reaches the matcher |
|---|---|
| lite (default) | `POST /ingest/reid` stores the embedding, then calls the matcher function inline in the same request - **implemented** |
| full | same inline call, **plus** the ingest handler would publish to a `reid-tracks` Kafka topic; a consumer (or Celery task) would call the identical matcher function for decoupled/scaled processing - **designed, not implemented; see TASKS.md.** Not needed at this project's scale (a handful of store cameras, verified fine running inline - see the scale assumption above), and this project's hardware can't verify a full-profile code path live, so it isn't built. Add it later exactly as designed here if a real multi-store, high-throughput deployment needs it. |

### Gallery storage & TTL

The gallery *is* the `identities` table - no separate cache or index. TTL is
enforced at query time by the matcher (`WHERE last_seen > now() - ttl_hours`),
not by deleting rows, so identity history remains available for journeys and
audit indefinitely. The TTL window is configurable
(`REID_GALLERY_TTL_HOURS`, default 24) precisely because the right value
depends on the deployment (a 24h default suits daily-shopper re-identification;
a multi-day retail environment might want longer).

## Privacy considerations

Re-ID embeddings are **biometric-adjacent data** - not raw biometrics (a face
photo, a fingerprint) but a derived vector that exists specifically to
re-identify the same person across cameras, so it deserves the same care:

- **No PII linkage.** An `identities` row carries only an embedding vector and
  timestamps - no name, no employee/customer ID, nothing that maps it to a
  real-world identity. It answers "have we seen this appearance before,"
  never "who is this."
- **Bounded matching lifetime.** After the TTL window, an identity is excluded
  from *active* matching (see above) - a person's appearance stops being
  linkable to new sightings once they've been out of frame long enough. Rows
  aren't deleted at TTL expiry (kept for historical journeys), but that
  retention window is itself configurable, and a future hard-delete task
  (mirroring the existing retention-purge Celery job) is the natural place to
  enforce a hard data-lifetime policy if required.
- **Tension with face-blur, acknowledged rather than hidden.** This project
  blurs faces before a frame ever leaves the worker (`vision/privacy.py`) as
  a default-privacy posture. Re-ID embeddings are a deliberate, narrow
  exception to "don't extract anything identifying": the OSNet crop used for
  embedding extraction is the *whole-body* crop, extracted **before** face
  blurring is drawn onto the frame used for the live preview - the embedding
  model doesn't need the face at all (OSNet is a body-appearance re-id
  model, not a face-recognition one), but it's still appearance data whose
  entire purpose is cross-camera re-identification, which is in tension with
  a "blur identifying features" default. Operators deploying this feature
  should treat it like any other re-identification capability under their
  applicable privacy/retail-surveillance regulations - this document doesn't
  make that tension disappear, just states it plainly.

## DB schema

New table `identities` (the gallery):

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| embedding | JSON | 512-dim float vector, the representative embedding |
| first_seen | timestamptz, indexed | |
| last_seen | timestamptz, indexed | TTL filtering uses this |
| track_count | int | how many tracks have linked to this identity |
| created_at | timestamptz | |

`tracks` gets two new nullable columns:

| Column | Type | Notes |
|---|---|---|
| embedding | JSON | this track's own 512-dim vector, set by `/ingest/reid`; `NULL` until then |
| identity_id | FK → identities.id, `ON DELETE SET NULL`, indexed | set by the matcher inline in the same `/ingest/reid` request; `NULL` for tracks with no embedding yet |

No pgvector - plain JSON like every other vector-ish column in this schema
(`trajectory`, `zones_visited`, `zone_occupancy`). Worth revisiting only if
the gallery ever approaches the scale note above.

## API surface

### `POST /api/v1/ingest/reid` (internal, `X-Worker-Key`) - implemented, now with inline matching

```json
{"camera_id": 1, "track_id": 42, "embedding": [0.0123, -0.0456, ...]}
```

Response: `{"ok": true, "identity_id": 7}` - the identity this track was
linked to (existing match) or the new one created for it.

`embedding` must be exactly **512** floats - wrong length is a 422, not a
silent truncation/pad, since a dimension mismatch almost always means the
worker is running the wrong model version.

**Ordering contract, implemented:** the worker calls `POST /ingest/track` for
a track before calling `/ingest/reid` for it
(`CameraPipeline._ship`/`_ship_reid_embedding` in
`streaming/camera_worker.py`). If `/ingest/reid` arrives for a `(camera_id,
track_id)` pair with no matching `Track` row, it returns **404** rather than
creating a bare row - a track's required fields (`first_seen`, `duration_s`,
etc.) come from `/ingest/track`, not from the Re-ID payload. On a 404, the
worker retries once after a **1 second** delay (`REID_RETRY_DELAY_S`) to
absorb ordinary request-ordering/network jitter between the two calls, then
gives up and logs a warning rather than retrying indefinitely or blocking the
pipeline on it.

### `GET /api/v1/reid/identities?min_track_count=2&limit=50` (viewer+) - implemented

Recently re-identified visitors: identities linked to `min_track_count` or
more tracks (default 2 - "matched more than once"), most recently seen
first. `{id, first_seen, last_seen, track_count}` per identity - no
embeddings in the response, this is a read API for humans, not a gallery
dump.

### `GET /api/v1/reid/identities/{id}/journey` (viewer+) - implemented

Returns one identity's path: the identity plus its linked tracks ordered by
`first_seen`, each with `camera_id`, `track_id`, `first_seen`, `last_seen`,
`trajectory`, `zones_visited` - literally "everywhere this appearance was
seen, in order." 404 if the identity doesn't exist. Backed by
`get_identity_journey` (implemented and unit-tested since session 1).

Both endpoints are plain read-only routes in `backend/app/api/v1/reid.py` -
no new auth pattern, just the existing `require_viewer` dependency every
other viewer+ route already uses.

## Session breakdown

1. **Session 1 (done):** design doc, `identities` table, `tracks.embedding` /
   `tracks.identity_id`, `POST /ingest/reid` (embedding storage only), CRUD,
   tests.
2. **Session 2 (done):** OSNet ONNX export script; on-worker extraction
   (best-crop heuristic, preprocessing, ONNX Runtime inference, fail-soft
   throughout); the worker sends `/ingest/reid` with the retry-once-on-404
   behavior; **and** the matcher function, wired inline into `/ingest/reid` -
   originally scoped for session 3, moved up because lite-mode matching has
   no transport dependency to build first. Mocked-model/pure-function tests
   throughout; no real inference run anywhere in this session.
3. **Session 3 (in progress):** `GET /reid/identities` + `.../journey` and
   the "Identities" frontend page (done); `scripts/calibrate_reid.py`
   (done - a two-phase extract-then-calibrate harness, pure-function
   distribution math manually verified since `scripts/` isn't
   unit-tested anywhere in this project); exporting the real ONNX model,
   running calibration against it, and confirming same-camera
   re-identification works end-to-end on the demo video (pending - blocked
   on the export, which runs in a throwaway Docker container on the
   operator's machine, not in CI or this session). **Kafka fan-out under `--profile
   full` was descoped from this session** (and this project) rather than
   shipped unverified - see "Constraints" #1, "Transport" above, and
   `TASKS.md`.
