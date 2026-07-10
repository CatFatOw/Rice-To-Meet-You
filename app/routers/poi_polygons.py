from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import poi_polygon_schemas
from repository.poi_polygon_repository import (
    get_all_poi,
    get_all_poi_by_city,
    create_pois,
    get_poi_by_id,
    get_poi_types,
)
from services.poi_polygon_services import (
    core_pois_from_upload,
    poi_to_frontend_polygon,
)


router = APIRouter(prefix="/core_poi_polygons", tags=["core_poi_polygons"])

@router.post("/import", response_model=poi_polygon_schemas.PoiImportResponse)
async def import_core_poi_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import core POI geometry rows from a CSV or XLSX upload."""
    file_bytes = await file.read()
    try:
        pois, total_rows, errors = core_pois_from_upload(file.filename or "upload", file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if pois:
        create_pois(pois, db)

    return {
        "filename": file.filename or "upload",
        "imported_count": len(pois),
        "skipped_count": len(errors),
        "total_rows": total_rows,
        "errors": errors[:25],
    }

@router.get("/")
async def get_all_data(db: Session = Depends(get_db)):
    """Function gets all core poi data from the database"""
    poi = get_all_poi(db)
    if not poi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return poi 

@router.get("/read_polygons", response_model=list[poi_polygon_schemas.PoiPolygonResponse])
async def get_all_polygons(db: Session = Depends(get_db)):
    """Function only gets the wkt polygon and presents them into front-end friendly format"""
    pois = get_all_poi(db)
    if not pois:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    polygons = [poi_to_frontend_polygon(poi) for poi in pois]
    return polygons
    
@router.get("/polygons/{poi_id}", response_model=poi_polygon_schemas.PoiPolygonResponse)
async def get_poi_polygon_by_id(poi_id:int, db:Session=Depends(get_db)):
    """Function gets specific polygon by id"""
    poi = get_poi_by_id(poi_id, db)
    if not poi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="POI not found",
        )
    
    if not poi.polygon_wkt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="POI has no polygon",
        )
    return poi_to_frontend_polygon(poi)


@router.get("/polygon/city/{city_name}", response_model=list[poi_polygon_schemas.PoiPolygonResponse])
async def get_poi_by_city(city_name:str, db:Session=Depends(get_db)):
    """Function gets the all core poi by city name :)"""
    pois = get_all_poi_by_city(city_name, db)
    if not pois:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return [poi_to_frontend_polygon(poi) for poi in pois]


@router.get("/types", response_model=list[str])
async def read_poi_types(db: Session = Depends(get_db)):
    """Return the distinct POI categories used for frontend filters/colors."""
    return get_poi_types(db)


