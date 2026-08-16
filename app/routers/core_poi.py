from fastapi import APIRouter

from database import SessionLocal
from repository.core_poi_geometry_respository import CorePoiGeometryRepository
from schemas.core_poi_geometry import CorePOICreate

router = APIRouter(prefix="/core_poi", tags=["core_poi"])


@router.post("/create-poi", status_code=201)
def create_poi(
    payload: CorePOICreate,
) -> dict:
    db = SessionLocal()
    poi = CorePoiGeometryRepository(db).create(payload.model_dump())
    db.commit()
    return poi


@router.get("/get-pois-by-city", status_code=200)
def get_pois_by_city(
    city: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    db = SessionLocal()
    pois = CorePoiGeometryRepository(db).getAllByMarketCode(
        market_code=city,
        limit=limit,
        offset=offset,
    )
    return pois


@router.get("/get-all-pois", status_code=200)
def get_all_pois() -> list[dict]:
    db = SessionLocal()
    pois = CorePoiGeometryRepository(db).getAll()
    return pois