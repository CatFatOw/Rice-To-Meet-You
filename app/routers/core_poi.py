from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from repository.core_poi_geometry_respository import CorePoiGeometryRepository
from schemas.core_poi_geometry import CorePOICreate

router = APIRouter(prefix="/core_poi", tags=["core_poi"])


@router.post("/create-poi", status_code=201)
def create_poi(
    payload: CorePOICreate,
    db: Session = Depends(get_db),
) -> dict:
    poi = CorePoiGeometryRepository(db).create(payload.model_dump())
    db.commit()
    return poi


@router.get("/get-pois-by-city", status_code=200)
def get_pois_by_city(
    city: str,
    limit: int | None = None,
    offset: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    pois = CorePoiGeometryRepository(db).getAllByMarketCode(
        market_code=city,
        limit=limit,
        offset=offset,
    )
    return pois


@router.get("/get-all-pois", status_code=200)
def get_all_pois(db: Session = Depends(get_db)) -> list[dict]:
    pois = CorePoiGeometryRepository(db).getAll()
    return pois