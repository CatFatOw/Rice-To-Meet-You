"""Frontend/ML-facing routes for heat and visitor training data."""

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from database import get_db
from repository.prediction_model_repository import (
    create_heat_data,
    create_visitor_data,
    delete_heat_data,
    delete_visitor_data,
    get_all_heat_data,
    get_all_visitors,
    get_heat_data_by_date,
    get_heat_data_by_id,
    get_heat_data_by_lat_lon,
    get_visitor_by_foursquare_id,
    get_visitor_by_id,
    get_visitors_by_category,
    get_visitors_by_date,
    get_visitors_by_lat_lon,
    get_visitors_by_market,
    update_heat_data,
    update_visitor_data,
)
from schemas.prediction_model_schemas import (
    HeatDataMLCreate,
    HeatDataMLResponse,
    PredictionModelCsvImportResponse,
    VisitorDataMLCreate,
    VisitorDataMLResponse,
)
from services.prediction_model_service import (
    PredictionModelCsvError,
    import_heat_csv_records,
    import_visitor_csv_records,
)

router = APIRouter(prefix="/prediction-model-ml", tags=["prediction-model-ml"])


def _not_found(detail: str = "No prediction-model records found"):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# =========================================================
# Heat data routes
# =========================================================

@router.get("/heat", response_model=list[HeatDataMLResponse])
def list_heat_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return paginated heat records for model training or inspection."""
    rows = get_all_heat_data(db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.post("/heat", response_model=HeatDataMLResponse, status_code=status.HTTP_201_CREATED)
def create_heat_record(payload: HeatDataMLCreate, db: Session = Depends(get_db)):
    """Create one heat record."""
    return create_heat_data(payload, db)


@router.post("/heat/import-csv", response_model=PredictionModelCsvImportResponse, status_code=status.HTTP_201_CREATED)
async def import_heat_csv(
    file: UploadFile = File(...),
    row_limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Bulk-create heat records from CSV upload."""
    try:
        return import_heat_csv_records(file.filename, await file.read(), db, row_limit=row_limit)
    except PredictionModelCsvError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.args[0])


@router.get("/heat/by-id/{heat_data_id}", response_model=HeatDataMLResponse)
def read_heat_data_by_id(heat_data_id: int, db: Session = Depends(get_db)):
    """Return one heat record by database ID."""
    row = get_heat_data_by_id(heat_data_id, db)
    if not row:
        _not_found("Heat record not found")
    return row


@router.put("/heat/by-id/{heat_data_id}", response_model=HeatDataMLResponse)
def replace_heat_record(heat_data_id: int, payload: HeatDataMLCreate, db: Session = Depends(get_db)):
    """Replace one heat record."""
    row = update_heat_data(heat_data_id, payload, db)
    if not row:
        _not_found("Heat record not found")
    return row


@router.delete("/heat/by-id/{heat_data_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_heat_record(heat_data_id: int, db: Session = Depends(get_db)):
    """Delete one heat record."""
    if not delete_heat_data(heat_data_id, db):
        _not_found("Heat record not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/heat/by-coordinate", response_model=list[HeatDataMLResponse])
def read_heat_data_by_coordinate(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    tolerance: float = Query(0.0001, gt=0, le=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return heat records near a coordinate."""
    rows = get_heat_data_by_lat_lon(lat, lon, db, tolerance=tolerance, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.get("/heat/by-date/{target_date}", response_model=list[HeatDataMLResponse])
def read_heat_data_by_date(
    target_date: date,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Return heat records for one calendar date."""
    rows = get_heat_data_by_date(target_date, db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


# =========================================================
# Visitor data routes
# =========================================================

@router.get("/visitors", response_model=list[VisitorDataMLResponse])
def list_visitor_data(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return paginated visitor/POI records for visitor models."""
    rows = get_all_visitors(db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.post("/visitors", response_model=VisitorDataMLResponse, status_code=status.HTTP_201_CREATED)
def create_visitor_record(payload: VisitorDataMLCreate, db: Session = Depends(get_db)):
    """Create one visitor record."""
    return create_visitor_data(payload, db)


@router.post("/visitors/import-csv", response_model=PredictionModelCsvImportResponse, status_code=status.HTTP_201_CREATED)
async def import_visitor_csv(
    file: UploadFile = File(...),
    row_limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Bulk-create visitor records from CSV upload."""
    try:
        return import_visitor_csv_records(file.filename, await file.read(), db, row_limit=row_limit)
    except PredictionModelCsvError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.args[0])


@router.get("/visitors/by-id/{visitor_id}", response_model=VisitorDataMLResponse)
def read_visitor_data_by_id(visitor_id: int, db: Session = Depends(get_db)):
    """Return one visitor record by database ID."""
    row = get_visitor_by_id(visitor_id, db)
    if not row:
        _not_found("Visitor record not found")
    return row


@router.put("/visitors/by-id/{visitor_id}", response_model=VisitorDataMLResponse)
def replace_visitor_record(visitor_id: int, payload: VisitorDataMLCreate, db: Session = Depends(get_db)):
    """Replace one visitor record."""
    row = update_visitor_data(visitor_id, payload, db)
    if not row:
        _not_found("Visitor record not found")
    return row


@router.delete("/visitors/by-id/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visitor_record(visitor_id: int, db: Session = Depends(get_db)):
    """Delete one visitor record."""
    if not delete_visitor_data(visitor_id, db):
        _not_found("Visitor record not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/visitors/by-foursquare/{fsq_place_id}", response_model=VisitorDataMLResponse)
def read_visitor_data_by_foursquare_id(fsq_place_id: str, db: Session = Depends(get_db)):
    """Return one visitor record by Foursquare place ID."""
    row = get_visitor_by_foursquare_id(fsq_place_id, db)
    if not row:
        _not_found("Visitor record not found for this Foursquare place")
    return row


@router.get("/visitors/by-coordinate", response_model=list[VisitorDataMLResponse])
def read_visitor_data_by_coordinate(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    tolerance: float = Query(0.0001, gt=0, le=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return visitor records near a coordinate."""
    rows = get_visitors_by_lat_lon(lat, lon, db, tolerance=tolerance, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.get("/visitors/by-date/{target_date}", response_model=list[VisitorDataMLResponse])
def read_visitor_data_by_date(
    target_date: date,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Return visitor records for one calendar date."""
    rows = get_visitors_by_date(target_date, db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.get("/visitors/by-market/{market}", response_model=list[VisitorDataMLResponse])
def read_visitor_data_by_market(
    market: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return visitor records in a market/city."""
    rows = get_visitors_by_market(market, db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows


@router.get("/visitors/by-category/{category}", response_model=list[VisitorDataMLResponse])
def read_visitor_data_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return visitor records in a POI category."""
    rows = get_visitors_by_category(category, db, skip=skip, limit=limit)
    if not rows:
        _not_found()
    return rows
