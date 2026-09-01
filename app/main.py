from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from database import engine, SessionLocal
from routers import (
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
from threading import Lock
from time import perf_counter
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

_startup_lock = Lock()
_startup_state = {
    "status": "starting",
    "phase": "initializing",
    "completed": 0,
    "total": 0,
    "detail": None,
    "eta_seconds": None,
    "phase_started_at": perf_counter(),
}


def _format_eta(seconds: float | None) -> str:
    if seconds is None:
        return "ETA calculating"
    minutes, remaining_seconds = divmod(max(0, round(seconds)), 60)
    return f"ETA {minutes}m {remaining_seconds:02d}s" if minutes else f"ETA {remaining_seconds}s"


def _begin_preload(phase: str, total: int) -> None:
    with _startup_lock:
        _startup_state.update(
            status="loading",
            phase=phase,
            completed=0,
            total=total,
            detail=None,
            eta_seconds=None,
            phase_started_at=perf_counter(),
        )
    logger.info("Startup preload | %s | [....................] 0/%s (0%%) | ETA calculating", phase, total)


def _report_preload_progress(completed: int, total: int, detail: str, *, rows: int | None = None) -> None:
    with _startup_lock:
        elapsed = perf_counter() - _startup_state["phase_started_at"]
        eta = (elapsed / completed) * (total - completed) if completed and total else None
        _startup_state.update(
            completed=completed,
            total=total,
            detail=detail,
            eta_seconds=round(eta) if eta is not None else None,
        )
    percent = round((completed / total) * 100) if total else 100
    filled = round((completed / total) * 20) if total else 20
    bar = "#" * filled + "." * (20 - filled)
    suffix = f" | {rows:,} rows" if rows is not None else ""
    logger.info(
        "Startup preload | %s | [%s] %s/%s (%s%%) | %s%s",
        _startup_state["phase"], bar, completed, total, percent, _format_eta(eta), suffix,
    )


def _mark_startup_ready() -> None:
    with _startup_lock:
        _startup_state.update(status="ready", phase="ready", eta_seconds=0, detail=None)
    logger.info("Startup preload complete | API ready to serve requests")


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
            total_steps = 1 + len(HeatmapRepository.SUPPORTED_MARKET_CODES)
            _begin_preload("heatmap cache", total_steps)
            await asyncio.to_thread(
                HeatmapRepository.initialize_tables,
                engine,
                progress_callback=lambda completed, total, detail: _report_preload_progress(
                    completed, total, detail
                ),
            )
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

    def preload_visitors() -> None:
        """Create a startup-only session and fill the shared visitor cache."""
        _begin_preload("visitor cache", VisitorRepository.N_WORKERS * VisitorRepository.CHUNKS_PER_WORKER)
        db = SessionLocal()
        try:
            VisitorRepository.initialize_table(
                db,
                progress_callback=lambda completed, total, rows: _report_preload_progress(
                    completed, total, f"batch {completed}/{total}", rows=rows
                ),
            )
        finally:
            try:
                db.close()
            except OperationalError:
                # The provider may close an idle SSL connection before the
                # session's final rollback. The preload itself can succeed.
                logger.warning("Startup database connection was already closed")

    async def preload_required_caches() -> None:
        """Warm required caches while `/health` remains available for progress."""
        try:
            await preload_heatmap()
            await asyncio.to_thread(preload_visitors)
            logger.info("Visitor cache ready")
            _mark_startup_ready()
        except Exception:
            with _startup_lock:
                _startup_state.update(status="failed", phase="startup failed", eta_seconds=None)
            logger.exception("Required cache preload failed")

    tasks = [
        asyncio.create_task(preload_required_caches(), name="preload-required-caches"),
        asyncio.create_task(preload_core_poi(), name="preload-core-poi"),
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


@app.get("/health")
def health():
    """Report API readiness and the current startup-cache preload progress."""
    with _startup_lock:
        return {key: value for key, value in _startup_state.items() if key != "phase_started_at"}


@app.middleware("http")
async def cache_readiness_gate(request: Request, call_next):
    """Keep data routes unavailable until their startup caches are complete."""
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)
    with _startup_lock:
        status_value = _startup_state["status"]
        eta_seconds = _startup_state["eta_seconds"]
    if status_value != "ready":
        return JSONResponse(
            status_code=503,
            content={"detail": "Data services are preloading", "eta_seconds": eta_seconds},
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dataset.router)
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
