from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from repository.heatmap_repository import HeatmapRepository
from repository.core_poi_geometry_respository import CorePoiGeometryRepository
from repository.final_visitor_repository import VisitorRepository

import redis.asyncio as redis
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import database
import asyncio
import models
import os
from database import engine, SessionLocal
from routers import (
    chatbot,
    core_poi,
    dataset,
    grid_geometry,
    grid_interpolation,
    grid_metrics,
    heatmap,
    login,
    nws_weather,
    polygon,
    urban_intervention,
    users,
    final_visitor

)

import logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reflection only - cheap, and it lets the first request skip it.
    try:
        HeatmapRepository.initialize_metadata(engine)
    except Exception:
        # Heatmap source tables are optional in a fresh or partial database.
        # Keep unrelated API routes available while the background preload logs
        # the missing-table detail.
        logger.exception("Heatmap metadata initialization skipped")

    async def preload_heatmap() -> None:
        try:
            await asyncio.to_thread(HeatmapRepository.initialize_tables, engine)
            logger.info("Heatmap cache ready: %s", HeatmapRepository.cache_stats())
        except Exception:
            logger.exception("Heatmap preload failed; falling back to queries")

    async def preload_core_poi() -> None:
        # Reflection happens inside the thread so a missing/misplaced POI table
        # degrades to per-request loading instead of blocking startup.
        try:
            await asyncio.to_thread(CorePoiGeometryRepository.initialize_tables, engine)
            logger.info(
                "Core POI cache ready: %s", CorePoiGeometryRepository.cache_stats()
            )
        except Exception:
            logger.exception("Core POI preload failed; falling back to queries")

    # The simulation endpoint needs this cache to build baseline points. Wait
    # here so its first request does not block behind a full cache preload.
    await preload_heatmap()

    async def preload_visitors() -> None:
        """Create a startup-only session and fill the shared visitor cache."""

        def _load() -> None:
            print("Pre-loading visitor information...")
            db = SessionLocal()
            try:
                VisitorRepository.initialize_table(db)
                print("Visitor information pre-loading complete.")
            finally:
                try:
                    db.close()
                except OperationalError:
                    # The provider may close an idle SSL connection before the
                    # session's final rollback. The preload itself can succeed.
                    logger.warning("Startup database connection was already closed")

        try:
            await asyncio.to_thread(_load)
            logger.info("Visitor cache ready")
        except Exception:
            # Cache-backed visitor routes fall back to querying the DB
            # directly (queryVisitorRowsWithGeometryByCityDate) while empty.
            logger.exception("Visitor preload failed; cached lookups return empty")

    # Core POI preload must finish before requests are accepted: otherwise an
    # early /core_poi request falls back to a schema-dependent lazy query while
    # the shared cache is still warming.
    await preload_core_poi()

    # Visitor data remains backgrounded because its cache is independent of the
    # core map and can safely fall back while it warms.
    tasks = [
        asyncio.create_task(preload_visitors(), name="preload-visitors"),
    ]

    yield

    # Cancellation cannot interrupt the worker threads; wait them out instead.
    pending = [task for task in tasks if not task.done()]
    if pending:
        logger.info(
            "Waiting for %d preload task(s) to finish before shutdown", len(pending)
        )
        await asyncio.gather(*pending, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

# The local Vite dev server is always allowed; deployed frontends are added per
# environment via ALLOWED_ORIGINS (comma-separated) so a new deploy is a config
# change rather than a code change.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Trailing slashes are stripped because the CORS spec compares origins exactly,
# and "https://example.com/" would silently never match a browser's Origin header.
configured_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS + configured_origins,
    # Vercel mints a fresh hostname for every preview deployment, so match them by
    # pattern instead of pinning each one and watching it go stale.
    allow_origin_regex=r"https://[\w.-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    """Liveness probe for the platform healthcheck."""
    return {"status": "ok"}


@app.get("/", tags=["health"])
async def root():
    """Keeps the bare domain from returning a 404."""
    return {"service": "rice-to-meet-you", "docs": "/docs"}


app.include_router(dataset.router)
app.include_router(chatbot.router)
app.include_router(users.router)
app.include_router(login.router)
app.include_router(nws_weather.router)
app.include_router(grid_geometry.router)
app.include_router(grid_metrics.router)
app.include_router(grid_interpolation.router)
app.include_router(heatmap.router)
app.include_router(core_poi.router)
app.include_router(polygon.router)
app.include_router(urban_intervention.router)

app.include_router(final_visitor.router)

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically
