"""FastAPI application entrypoint.

Wires together the three layers: API routers (agents/workflows/runs/monitoring),
the agent runtime, and persistence. On startup it creates tables, seeds the two
template workflows, and (if configured) starts the Telegram channel — all inside
the app lifespan so everything shares one event loop.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents, monitoring, runs, workflows
from app.channels.telegram import start_telegram, stop_telegram
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.runtime.templates import seed_templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────
    init_db()
    with SessionLocal() as db:
        seed_templates(db)
    logger.info("Database ready, templates seeded.")
    await start_telegram()
    yield
    # ── shutdown ─────────────────────────────────────────────────────
    await stop_telegram()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Yuno Agent Orchestration Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(agents.router)
    app.include_router(workflows.router)
    app.include_router(runs.router)
    app.include_router(monitoring.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
