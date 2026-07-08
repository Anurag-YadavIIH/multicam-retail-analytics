# Cross-camera Re-ID

Links a person's tracks across different cameras into one global "identity" by
comparing appearance embeddings, so a customer who walks from the entrance
camera to the checkout camera is recognized as the same person without any
biometric ID system - just embedding similarity, time, and (later) geometry.

This is a multi-session build. **This document covers the full design; only
the data layer (models, migration, schemas, CRUD, the ingest endpoint) is
implemented so far.** Embedding extraction and matching are session 2/3.

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
   embedding; full profile can additionally fan it out via Kafka to a
   consumer for horizontal scaling. Same function either way - no Kafka
   dependency to unit-test matching.
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
  └─ POST /ingest/reid   (new, this session - {camera_id, track_id, embedding})
                                          │
                                          ├─ store embedding on the Track row
                                          │  (session 1 - this is where it stops today)
                                          │
                                          └─ [session 2/3] invoke matcher(db, track)
                                             ├─ lite: called inline, same request
                                             └─ full: also published to a Kafka
                                                topic; a consumer (or Celery task)
                                                calls the same matcher function
```

### Extraction (vision worker, session 2)

- Model: **osnet_x0_25** (the lightest OSNet width variant), exported to ONNX
  once, offline. `onnxruntime` is already a runtime dependency (used for the
  detector's optional ONNX path) - Re-ID adds no new runtime dependency.
  `torchreid`/`torch` are only ever used by the offline export script, never
  installed in the vision-worker image.
- Input: the person crop from the track's best frame, resized to OSNet's
  expected `256×128`, ImageNet-normalized.
- Output: a **512-dim** float vector, L2-normalized before it's sent.
- Extraction happens once per closed track (not per frame) - cheap enough on
  CPU at that rate even on this hardware.

### Matching (pure function, session 3)

`match_or_create_identity(db, track, embedding, *, ttl_hours, threshold) ->
Identity` - takes a DB session, a track, and its embedding; does the
following, with no knowledge of Kafka, Redis, or HTTP:

1. Load the **active gallery**: all `identities` with
   `last_seen > now() - ttl_hours` (default 24h - configurable). Rows older
   than that are excluded from matching but never deleted (kept for
   historical journeys / audit); a separate retention task can hard-delete
   very old ones later, matching the existing Celery retention-purge pattern.
2. Cosine similarity between the track's embedding and every active
   identity's representative embedding.
3. Best match above the similarity threshold (tunable; a starting point
   around 0.6 is typical for OSNet-family embeddings, but the real value
   needs tuning against this deployment's actual cameras/lighting once
   session 2 produces real embeddings - not committed to code yet) →
   link the track to that identity, update its `last_seen`/`track_count`.
   No match above threshold → create a new identity from this track's
   embedding.

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
| lite (default) | `POST /ingest/reid` stores the embedding, then calls the matcher function inline in the same request |
| full | same inline call, **plus** the ingest handler publishes to a `reid-tracks` Kafka topic; a consumer (or Celery task) calls the identical matcher function for decoupled/scaled processing |

### Gallery storage & TTL

The gallery *is* the `identities` table - no separate cache or index. TTL is
enforced at query time by the matcher (`WHERE last_seen > now() - ttl_hours`),
not by deleting rows, so identity history remains available for journeys and
audit indefinitely. The TTL window is configurable (a settings value, added
when the matcher is built in session 3) precisely because the right value
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
| identity_id | FK → identities.id, `ON DELETE SET NULL`, indexed | `NULL` until the matcher links it (session 3) |

No pgvector - plain JSON like every other vector-ish column in this schema
(`trajectory`, `zones_visited`, `zone_occupancy`). Worth revisiting only if
the gallery ever approaches the scale note above.

## API surface

### `POST /api/v1/ingest/reid` (internal, `X-Worker-Key`) - implemented this session

```json
{"camera_id": 1, "track_id": 42, "embedding": [0.0123, -0.0456, ...]}
```

`embedding` must be exactly **512** floats - wrong length is a 422, not a
silent truncation/pad, since a dimension mismatch almost always means the
worker is running the wrong model version.

**Ordering contract:** the worker must call `POST /ingest/track` for a track
*before* (or, transitionally while both are being added to the worker in
session 2, at the same point in the close sequence as) calling
`/ingest/reid` for it. If `/ingest/reid` arrives for a `(camera_id,
track_id)` pair with no matching `Track` row, it returns **404** rather than
creating a bare row - a track's required fields (`first_seen`, `duration_s`,
etc.) come from `/ingest/track`, not from the Re-ID payload. On a 404, the
**worker** (session 2 code, not implemented yet - this is a contract for that
future work) should retry once after a short delay rather than drop the
embedding, to absorb ordinary request-ordering/network jitter between the two
calls; it should not retry indefinitely or block the pipeline on it.

### `GET /api/v1/reid/identities/{id}/journey` (viewer+) - designed, not yet implemented

Returns one identity's cross-camera path: the identity plus its linked tracks
ordered by `first_seen`, each with `camera_id`, `track_id`, `first_seen`,
`last_seen`, `trajectory`, `zones_visited` - literally "everywhere this
appearance was seen, in order." Not implemented yet because until the
matcher (session 3) links any tracks to identities, there's nothing for it to
return. The backing query (`get_identity_journey`) is already implemented and
unit-tested this session, ready for this endpoint to call in a later session.

## Session breakdown

1. **This session:** design doc, `identities` table, `tracks.embedding` /
   `tracks.identity_id`, `POST /ingest/reid`, CRUD, tests.
2. **Session 2:** OSNet ONNX export script, on-worker extraction, worker
   sends `/ingest/reid` (with the retry-once-on-404 behavior above).
3. **Session 3:** the matcher function, inline invocation from
   `/ingest/reid`, the `journeys` endpoint, Kafka fan-out under
   `--profile full`.
