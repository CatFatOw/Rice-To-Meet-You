from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from repository.heatmap_repository import HeatmapRepository
from repository.core_poi_geometry_respository import CorePoiGeometryRepository

import redis.asyncio as redis
from sqlalchemy.orm import Session
import database
import asyncio
import models
from database import engine
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
)


import logging
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reflection only - cheap, and it lets the first request skip it.
    HeatmapRepository.initialize_metadata(engine)

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

    tasks = [
        asyncio.create_task(preload_heatmap(), name="preload-heatmap"),
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

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically