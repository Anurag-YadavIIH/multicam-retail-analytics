# Demo: watching the pipeline fire, end to end

`make demo` (or the equivalent commands below) brings up a stack where you can
watch detection → zone → threshold → alert happen live, not just read about
it. This doc is the honest account of how that demo was built, why it uses
the video it does, and exactly what to watch for and when.

## Why a second camera, and why this clip

The original `demo-entrance` camera (`retail_demo.mp4`) is genuinely sparse:
measured, frame-by-frame, over its full 596 frames, it never has more than
**3 concurrent people** on screen. Tuning `queue_length_threshold` down to
fire on that footage would mean setting it at the literal ceiling of what the
clip ever shows - a threshold that only "works" because it's equal to the
maximum, not because it reflects a real queue. That's the cheaty outcome this
demo is built to avoid.

The obvious alternative - a genuinely crowded MOT20/CrowdHuman clip - didn't
hold up on inspection:

- **MOT20** is licensed **CC BY-NC-SA** (non-commercial) - a bad fit for a
  public portfolio repo - and is only distributed as one ~5 GB all-sequences
  zip (no lighter per-sequence download), at roughly 150 people/frame:
  wildly oversized for what's needed here.
- **CrowdHuman** requires accepting a license manually on their site - it
  can't be fetched by an unattended script.

Instead, `queue_demo.mp4` (`classroom.mp4` from
[intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos),
the same already-vetted, **CC BY 4.0** source as the original demo clip -
attribution: intel-iot-devkit, unmodified) was measured the same way: a real,
steady **4 people for all 984 frames**, not a manufactured spike. That's not
"crowding" at mall scale, so `crowding_people_threshold` (25) is left
untouched and deliberately does **not** fire in this demo - raising it to
match 4 people would itself be the absurd threshold this exercise is meant
to avoid. What it does support, honestly, is a **queue** alert:
`queue_length_threshold` is set to **3** (`configs/app.yaml`) - a small-store
queue of 3+ is a defensible real trigger, arguably more realistic than the
original default of 6 for a small store - and the new camera's queue zone
covers the bottom half of the frame, where these four seated people's
foot-points (bbox bottom-center, per `Track.foot_point`) actually land.

`configs/app.yaml`'s `alerts:` section used to be dead: `alert_service.py`'s
own docstring claimed thresholds were loaded from it, but nothing ever read
the file - the real values were a hardcoded Python dict. Fixed as part of
this: `load_thresholds()` (mirroring `vision/detector.py`'s `load_class_map`)
now actually reads it, fail-soft to the same defaults if the file is
missing.

## What gets seeded

`scripts/seed_db.py` (idempotent, runs automatically on every backend
startup) now creates, if they don't already exist:

| Camera | Source | Zones | Purpose |
|---|---|---|---|
| `demo-entrance` | `retail_demo.mp4` | entrance, checkout-queue, aisle-A | general pipeline, Re-ID (see docs/REID.md) |
| `checkout-queue-demo` | `queue_demo.mp4` | checkout-queue (bottom half of frame) | reliably crosses the queue alert threshold |

`configs/cameras.example.yaml` (used only by `scripts/register_cameras.py`,
a separate, optional bulk-registration demo - not part of the seeded path
above) had two placeholder entries, `entrance-1` (rtsp) and `usb-test`
(usb), that register successfully but sit permanently offline since nothing
real is at those addresses - not a bug, just unlabeled example data that
looked broken. Both are now explicitly named and located as
"example / not connected."

## Running it

```bash
make demo
# or, equivalently:
python scripts/download_sample_video.py
docker compose up -d --build postgres redis backend vision-worker frontend
```

To also watch alert **dispatch** leave the system (not just appear in the
DB/dashboard feed), before or after bringing up the stack:

```bash
python scripts/dev_webhook_receiver.py     # separate terminal, stdlib only
```

Then set in `.env` and restart backend to pick it up (`Settings` is cached
per-process):

```bash
ALERT_WEBHOOK_URL=http://host.docker.internal:8099/webhook
SLACK_WEBHOOK_URL=http://host.docker.internal:8099/slack
docker compose up -d backend
```

## What to watch for, and when

Measured on a real run (vision-worker container start to first alert):

| T+ | What happens | Where to look |
|---|---|---|
| 0s | Containers start; YOLO model loads once, then each camera's thread opens its video and starts its analytics engine | `docker compose logs -f vision-worker` - `pipeline started for camera N` |
| ~15-50s | Model load + sequential per-camera startup overhead (varies by machine; measured ~49s on this one) | - |
| ~60s after a camera's *first frame* | That camera's analytics engine takes its first snapshot (`snapshot_interval_s: 60`, `configs/app.yaml`) | Dashboard traffic chart gets its first point |
| **~110s from container start** (measured) | `checkout-queue-demo`'s snapshot shows `queue_length: 4` (≥ threshold of 3) → alert created, broadcast over `/ws/alerts`, dispatched to any configured webhook/Slack | Dashboard "Live alert feed"; `GET /alerts`; the webhook receiver's terminal |
| every 5 minutes after that | Same alert type+camera is deduped (`DEDUP_WINDOW`) but still dispatched on every distinct alert - confirmed over a full hour of continuous running: alerts at 12:10, 12:15, 12:20, 12:25, 12:30, 12:35, 12:40 (UTC), one webhook POST each | Webhook receiver terminal keeps printing |

~110s, not a clean "60 seconds" - the extra time is real one-time model-load
and thread-startup overhead common to every camera in this stack, not
specific to the new one. Reported as measured rather than rounded down to
match a nicer-sounding number.

## Dashboard liveliness

KPIs and the 24h traffic chart go from flat-zero to real numbers once
`checkout-queue-demo` is running - `current_occupancy`, `max_queue_length`,
and the traffic chart's per-minute counts all reflect real detections, not
placeholders. One honest caveat: "total visitors today" accumulates across
*however long the stack has been running that day* - a number like 346 on a
dev machine mid-session reflects hours of accumulated runtime, not what a
single fresh 60-second run shows. A brand-new `make demo` run starts that
counter at 0 and builds up gradually from real detections, same as any of
the other per-snapshot metrics.

If you want the traffic chart to look busy over a longer window (a full
day's shape, not just a rising line from zero), the input that actually
gets you there is a longer-running or higher-traffic video source, not a
config change - the pipeline itself already computes and stores everything
correctly at whatever traffic the source actually shows.
