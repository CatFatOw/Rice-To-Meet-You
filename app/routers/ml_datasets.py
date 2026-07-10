from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.ml_schemas import MlInputResponse, MlPredictionPointRequest, MlTaskSummary
from services.ml_dataset_service import (
    get_visitor_prediction_input,
    get_weather_heat_input,
    ml_task_summaries,
)


router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/tasks", response_model=list[MlTaskSummary])
def get_ml_tasks():
    """Return the available ML-ready input endpoints."""
    return ml_task_summaries()


@router.get("/visitor-prediction/input", response_model=MlInputResponse)
def get_visitor_prediction_model_input(
    lat: float = Query(..., description="Prediction latitude."),
    lon: float = Query(..., description="Prediction longitude."),
    state: str = Query(..., description="State or state abbreviation for grid/context lookup."),
    city: str | None = Query(None, description="Optional city/market name."),
    grid_cell_id: int | None = Query(None, description="Optional grid cell id when prediction is for a known grid cell."),
    poi_id: int | None = Query(None, description="Optional Core POI database id when prediction is for a known POI."),
    source: str | None = Query(None, description="Optional frontend source label, such as grid_centroid or poi."),
    timestamp: datetime | None = Query(None, description="Prediction time. Defaults to current UTC time."),
    db: Session = Depends(get_db),
):
    """Return one click-based inference row used to predict visitor volume/metrics."""
    return get_visitor_prediction_input(
        db=db,
        lat=lat,
        lon=lon,
        state=state,
        city=city,
        grid_cell_id=grid_cell_id,
        poi_id=poi_id,
        source=source,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


@router.post("/visitor-prediction/input", response_model=MlInputResponse)
def post_visitor_prediction_model_input(
    request: MlPredictionPointRequest,
    db: Session = Depends(get_db),
):
    """Return one click-based inference row from a frontend grid/POI selection."""
    return get_visitor_prediction_input(
        db=db,
        lat=request.lat,
        lon=request.lon,
        state=request.state,
        city=request.city,
        grid_cell_id=request.grid_cell_id,
        poi_id=request.poi_id,
        source=request.source,
        timestamp=request.timestamp or datetime.now(timezone.utc),
    )


@router.get("/weather-heat/input", response_model=MlInputResponse)
def get_weather_heat_model_input(
    lat: float = Query(..., description="Prediction latitude."),
    lon: float = Query(..., description="Prediction longitude."),
    state: str = Query(..., description="State or state abbreviation for grid/context lookup."),
    city: str | None = Query(None, description="Optional city/market name."),
    grid_cell_id: int | None = Query(None, description="Optional grid cell id when prediction is for a known grid cell."),
    source: str | None = Query(None, description="Optional frontend source label, such as grid_centroid or poi."),
    timestamp: datetime | None = Query(None, description="Prediction time. Defaults to current UTC time."),
    db: Session = Depends(get_db),
):
    """Return one click-based inference row used to predict heat/weather metrics."""
    return get_weather_heat_input(
        db=db,
        lat=lat,
        lon=lon,
        state=state,
        city=city,
        grid_cell_id=grid_cell_id,
        source=source,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


@router.post("/weather-heat/input", response_model=MlInputResponse)
def post_weather_heat_model_input(
    request: MlPredictionPointRequest,
    db: Session = Depends(get_db),
):
    """Return one click-based inference row from a frontend grid/POI selection."""
    return get_weather_heat_input(
        db=db,
        lat=request.lat,
        lon=request.lon,
        state=request.state,
        city=request.city,
        grid_cell_id=request.grid_cell_id,
        source=request.source,
        timestamp=request.timestamp or datetime.now(timezone.utc),
    )
