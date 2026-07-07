# API reference

Interactive docs: **http://localhost:8000/docs** (Swagger) · `/openapi.json`.
All endpoints are under `/api/v1`. Auth is OAuth2 password flow → JWT bearer.

## Auth
| Method | Path | Role | Notes |
|---|---|---|---|
| POST | /auth/login | — | form fields `username`, `password` → access+refresh tokens |
| POST | /auth/refresh | — | body `{refresh_token}` |
| GET | /auth/me | any | current user |

## Users (admin)
| POST | /users | create user (role: admin/manager/viewer) |
| GET | /users | list |
| PATCH | /users/{id} | update role/password/active |

## Cameras
| GET | /cameras | viewer+ |
| POST | /cameras | manager+ · `{name, source, type: rtsp|usb|file, location, fps_target}` |
| GET/PATCH/DELETE | /cameras/{id} | viewer+/manager+/manager+ |
| POST | /cameras/{id}/stream-token | viewer+ · mints a ~60s camera-scoped token (see below) |
| GET | /cameras/{id}/snapshot | viewer+ · single latest JPEG (404 if the worker hasn't pushed one yet) |
| GET | /cameras/{id}/stream | viewer+ · live `multipart/x-mixed-replace` MJPEG preview (~2-3 FPS) |
| POST | /cameras/{id}/zones | manager+ · polygon of normalized `[x,y]` points |
| DELETE | /cameras/{id}/zones/{zone_id} | manager+ |

### Live preview auth

`snapshot` and `stream` are meant to be embedded directly in an `<img>`/`<video>`
tag, which can't set an `Authorization` header, so they also accept a token via
`?token=`. That query-param path only accepts a **stream token** — never the
full access token — so a leaked/logged URL can't grant broader API access:

1. `POST /cameras/{id}/stream-token` with a normal `Authorization: Bearer
   <access_token>` header → `{"token": "...", "expires_in": 60}`. The token is
   a JWT (`type: "stream"`) encoding that one `camera_id` and expiring in ~60s.
2. `GET /cameras/{id}/snapshot?token=<stream_token>` or
   `.../stream?token=<stream_token>` — valid only for the `camera_id` it was
   minted for, and rejected everywhere else (any other endpoint, or the same
   endpoint for a different camera). Fetch a fresh one before every
   (re)connect; don't reuse one across connections.

Direct API/curl use is unaffected — the full access token via the
`Authorization` header still works on `snapshot`/`stream` exactly like every
other endpoint.

## Analytics (viewer+)
| GET | /analytics/overview | today's KPIs |
| GET | /analytics/traffic?hours=24&camera_id= | traffic trend points |
| GET | /analytics/snapshots?camera_id=&hours= | raw per-minute snapshots |
| GET | /analytics/peak-hours?days=7 | avg occupancy by hour-of-day |
| GET | /analytics/dwell?camera_id=&hours= | dwell stats from tracks |

## Alerts
| GET | /alerts?hours=&unacknowledged_only= | viewer+ |
| POST | /alerts/{id}/ack | manager+ |

## Reports
| GET | /reports?kind=daily | viewer+ |

## Internal (vision workers, header `X-Worker-Key: <SECRET_KEY>`)
| POST | /ingest/frame | detections + optional snapshot |
| POST | /ingest/track | upsert closed track |
| POST | /cameras/{id}/heartbeat?fps= | health |

## WebSockets (`?token=<access_token>`)
| /ws/detections/{camera_id} | live boxes + track IDs (normalized bboxes) |
| /ws/alerts | alert stream |
| /ws/analytics | snapshot stream |

`/ws/detections/{camera_id}` also accepts a stream token scoped to that same
`camera_id` (see above) in place of the access token. `/ws/alerts` and
`/ws/analytics` are global channels with no `camera_id` to scope against, so
they only accept the full access token.

Example:
```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -d 'username=admin@retail.local&password=admin12345' | jq -r .access_token)
curl -s localhost:8000/api/v1/analytics/overview -H "Authorization: Bearer $TOKEN" | jq
```
