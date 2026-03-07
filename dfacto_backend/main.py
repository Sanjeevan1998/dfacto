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
from routers.live_audit import router as live_audit_router
from routers.debug import router as debug_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("dfacto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Dfacto backend starting up…")
    # Pre-warm the LangGraph compilation (avoids cold-start on first WS frame)
    try:
        from agents.supervisor import _graph  # noqa: F401
        logger.info("✅ LangGraph supervisor compiled and ready.")
    except Exception as exc:
        logger.exception("❌ LangGraph failed to compile: %s", exc)
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


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(live_audit_router)
app.include_router(debug_router)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe — confirms the server is running."""
    return {"status": "ok", "version": app.version}


