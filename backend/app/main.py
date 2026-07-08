"""FastAPI application factory."""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from backend.app.api.v1 import alerts, analytics, auth, cameras, ingest, reid, reports, users, ws
from backend.app.core.config import get_settings
from backend.app.services.metrics import API_LATENCY

settings = get_settings()
logging.basicConfig(level=settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Multi-Camera Retail Analytics API",
        version="1.0.0",
        description=(
            "Production-grade retail computer-vision analytics: cameras, detections, "
            "tracking, queue/shelf analytics, alerts, and real-time WebSocket streams."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def latency_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        API_LATENCY.labels(path=request.url.path, method=request.method).observe(
            time.perf_counter() - start
        )
        return response

    api = "/api/v1"
    app.include_router(auth.router, prefix=api)
    app.include_router(users.router, prefix=api)
    app.include_router(cameras.router, prefix=api)
    app.include_router(analytics.router, prefix=api)
    app.include_router(alerts.router, prefix=api)
    app.include_router(reports.router, prefix=api)
    app.include_router(ingest.router, prefix=api)
    app.include_router(reid.router, prefix=api)
    app.include_router(ws.router)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/metrics", tags=["ops"])
    def metrics_endpoint() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
