"""Route handles the polygon backend logic. Users can use the polygon tool and create 'simulation region' where 
there code impacts :)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas import polygon_schemas
from repository.polygon_repository import (
    create_impact_grids,
    create_new_polygon as create_new_polygon_row,
    delete_polygon_by_id as delete_polygon_row_by_id,
    get_all_impacted_grids as get_all_impacted_grid_rows,
    get_all_polygon_points,
    get_impacted_grid_cell_ids_by_polygon_id,
    get_impacted_grid_by_polygon_id,
    get_polygon_by_id,
    update_polygon_geometry,
)
from services.polygon_services import polygon_from_geojson
from fastapi.responses import Response

router = APIRouter(prefix="/polygon", tags=["polygons"])



@router.get("/", response_model=list[polygon_schemas.PolygonGeometryResponse])
async def get_all_polygons(db: Session = Depends(get_db)):
    """Function gets every single polygon"""
    data = get_all_polygon_points(db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return data


@router.post("/create_new_polygon", response_model=polygon_schemas.PolygonGeometryResponse)
async def create_new_polygon(
    new_polygon: polygon_schemas.PolygonGeometryCreate,
    db: Session = Depends(get_db),
):
    """Function creates new polygon"""
    try:
        polygon_from_geojson(new_polygon.geometry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    new_polygons = create_new_polygon_row(new_polygon, db)
    return new_polygons


@router.put("/update_polygon/{polygon_id}", response_model=polygon_schemas.PolygonGeometryResponse)
async def update_polygon(
    polygon_id: int,
    new_polygon: polygon_schemas.PolygonGeometryUpdate,
    recompute_impacts: bool = True,
    city: str = None,
    state: str = None,
    db: Session = Depends(get_db),
):
    """Function updates exisitng polygon (ie if user moves or edits it etc )"""
    polygon = get_polygon_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")

    try:
        polygon_from_geojson(new_polygon.geometry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    updated_polygon = update_polygon_geometry(polygon, new_polygon, db)

    if recompute_impacts:
        create_impact_grids(
            polygon_id=updated_polygon.id,
            polygon_points=polygon_schemas.PolygonGeometryCreate(geometry=updated_polygon.geometry),
            db=db,
            city=city,
            state=state,
            replace_existing=True,
        )

    return updated_polygon


@router.delete("/delete/{polygon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polygon_by_id_route(polygon_id: int, db: Session = Depends(get_db)):
    """Function deletes a polygon by id"""
    polygon = delete_polygon_row_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/impacted_grids", response_model=list[polygon_schemas.PolygonImpactGridsResponse])
async def get_all_impacted_grids(db: Session = Depends(get_db)):
    """Functino gets all impacted grids"""
    grids = get_all_impacted_grid_rows(db)
    if not grids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return grids


@router.post(
    "/{polygon_id}/compute_impact_grids",
    response_model=polygon_schemas.PolygonImpactComputeResponse,
)
async def compute_impact_grids(
    polygon_id: int,
    city: str = None,
    state: str = None,
    replace_existing: bool = True,
    db: Session = Depends(get_db),
):
    """Function computes the impact grids"""
    polygon = get_polygon_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")

    grids = create_impact_grids(
        polygon_id=polygon.id,
        polygon_points=polygon_schemas.PolygonGeometryCreate(geometry=polygon.geometry),
        db=db,
        city=city,
        state=state,
        replace_existing=replace_existing,
    )
    return {
        "polygon_id": polygon.id,
        "impacted_grid_count": len(grids),
        "impacted_grids": grids,
    }


@router.post("/compute_impact_grids", response_model=polygon_schemas.PolygonImpactComputeResponse)
async def compute_impact_grids_from_payload(
    polygon: polygon_schemas.PolygonGeometryCreate,
    city: str = None,
    state: str = None,
    db: Session = Depends(get_db),
):
    """Create a polygon and compute impacted grids in one request."""
    try:
        polygon_from_geojson(polygon.geometry)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    saved_polygon = create_new_polygon_row(polygon, db)
    grids = create_impact_grids(
        polygon_id=saved_polygon.id,
        polygon_points=polygon,
        db=db,
        city=city,
        state=state,
        replace_existing=True,
    )
    return {
        "polygon_id": saved_polygon.id,
        "impacted_grid_count": len(grids),
        "impacted_grids": grids,
    }


@router.get(
    "/{polygon_id}/impacted_grids/summary",
    response_model=polygon_schemas.PolygonImpactSummaryResponse,
)
async def get_impact_grid_summary_by_polygon_id(
    polygon_id: int,
    db: Session = Depends(get_db),
):
    """Return a frontend-friendly impacted grid summary for one polygon."""
    polygon = get_polygon_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")

    impacted_grid_cell_ids = get_impacted_grid_cell_ids_by_polygon_id(polygon_id, db)
    return {
        "polygon_geometry_id": polygon_id,
        "impacted_count": len(impacted_grid_cell_ids),
        "impacted_grid_cell_ids": impacted_grid_cell_ids,
    }


@router.get("/{polygon_id}/impacted_grids", response_model=list[polygon_schemas.PolygonImpactGridsResponse])
async def get_impact_grids_by_polygon_id(polygon_id: int, db: Session = Depends(get_db)):
    """Function gets the desired impact grids by the ID etc"""
    impact_grids = get_impacted_grid_by_polygon_id(polygon_id, db)
    if not impact_grids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return impact_grids


@router.get("/{polygon_id}", response_model=polygon_schemas.PolygonGeometryResponse)
async def get_polygon_by_id_route(polygon_id: int, db: Session = Depends(get_db)):
    """Function gets specific polygon by its id"""
    polygon = get_polygon_by_id(polygon_id, db)
    if not polygon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")
    return polygon
