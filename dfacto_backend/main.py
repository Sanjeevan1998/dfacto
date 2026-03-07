"""
Dfacto Backend — FastAPI entry point.
Phase 2: Live Audit real-time fact-checking pipeline.
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("dfacto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Dfacto backend starting up…")
    yield
    logger.info("🛑 Dfacto backend shutting down…")


app = FastAPI(
    title="Dfacto API",
    description="Real-time fact-checking backend for the Live Audit pipeline.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe — confirms the server is running."""
    return {"status": "ok", "version": app.version}


# ── WebSocket endpoint (stub — filled in MT-3) ────────────────────────────────
# from routers.live_audit import router as live_audit_router
# app.include_router(live_audit_router)
