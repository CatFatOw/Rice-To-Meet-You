"""File handles the querying logic for the db"""
from sqlalchemy.orm import Session
from schemas import polygon_schemas
from models import polygon_tables
from services.polygon_services import find_impact_grids


def get_all_polygon_points(db: Session):
    """Function gets every single possible polygon points"""
    data = db.query(polygon_tables.PolygonGeometry).all()
    return data 


def get_polygons_for_city_state(city: str | None, state: str | None, db: Session):
    """Return saved polygons, optionally scoped to city and state.

    These rows back frontend POI overlays, so city/state filtering uses the
    display metadata stored with each polygon rather than geometry containment.
    """
    query = db.query(polygon_tables.PolygonGeometry)
    if city:
        query = query.filter(polygon_tables.PolygonGeometry.city_name.ilike(city))
    if state:
        query = query.filter(polygon_tables.PolygonGeometry.state_name.ilike(state))
    return query.order_by(polygon_tables.PolygonGeometry.id).all()


def get_polygons_for_city(city: str | None, db: Session):
    """Return saved polygons, optionally scoped to one city."""
    return get_polygons_for_city_state(city=city, state=None, db=db)


def get_key_pois(city: str | None, state: str | None, db: Session):
    """Return POI polygons used by frontend statistics panels.

    This is intentionally a thin alias over the polygon lookup so route code can
    read in domain language: statistics consume key POIs, map overlays consume
    polygons.
    """
    return get_polygons_for_city_state(city=city, state=state, db=db)

def get_polygon_by_id(id: int, db: Session):
    """Function gets specific polygon by id"""
    data = db.query(polygon_tables.PolygonGeometry).filter(polygon_tables.PolygonGeometry.id == id).first()
    return data 

def create_new_polygon(polygon_points: polygon_schemas.PolygonGeometryCreate, db: Session):
    """function creates a new polygon from a series of points that the user has """
    new_data = polygon_tables.PolygonGeometry(**polygon_points.model_dump())
    db.add(new_data)
    db.commit()
    db.refresh(new_data)
    return new_data 


def update_polygon_geometry(
    polygon: polygon_tables.PolygonGeometry,
    polygon_points: polygon_schemas.PolygonGeometryUpdate,
    db: Session,
):
    """Update a saved polygon geometry."""
    for key, value in polygon_points.model_dump(exclude_unset=True).items():
        setattr(polygon, key, value)

    db.commit()
    db.refresh(polygon)
    return polygon


def get_all_impacted_grids(db: Session):
    """Function gets every single grid that the polygon impacts"""
    grids = db.query(polygon_tables.PolygonImpactGrids).all()
    return grids 

def create_impact_grids(
    polygon_id: int,
    polygon_points: polygon_schemas.PolygonGeometryCreate,
    db: Session,
    city: str = None,
    state: str = None,
    replace_existing: bool = True,
):
    """Function finds all grid centroids that are inside the polygon points and updates it"""
    if replace_existing:
        delete_impacted_grids_by_polygon_id(polygon_id, db)

    impacted_grids = find_impact_grids(
        polygon_id=polygon_id,
        polygon=polygon_points,
        db=db,
        city=city,
        state=state,
    )

    if impacted_grids:
        db.add_all(impacted_grids)

    db.commit()

    for impacted_grid in impacted_grids:
        db.refresh(impacted_grid)

    return impacted_grids

def get_impacted_grid_by_polygon_id(id: int, db: Session):
    """Function gets specific impacted grid id"""
    grid = (
        db.query(polygon_tables.PolygonImpactGrids)
        .filter(polygon_tables.PolygonImpactGrids.polygon_geometry_id == id)
        .all()
    )
    return grid 


def get_impacted_grid_cell_ids_by_polygon_id(id: int, db: Session):
    """Return only grid cell IDs impacted by one polygon."""
    rows = (
        db.query(polygon_tables.PolygonImpactGrids.grid_cell_id)
        .filter(polygon_tables.PolygonImpactGrids.polygon_geometry_id == id)
        .order_by(polygon_tables.PolygonImpactGrids.grid_cell_id)
        .all()
    )
    return [grid_cell_id for (grid_cell_id,) in rows]


# Delete polygon impacts
def delete_impacted_grids_by_polygon_id(polygon_id: int, db: Session):
    return (
        db.query(polygon_tables.PolygonImpactGrids)
        .filter(polygon_tables.PolygonImpactGrids.polygon_geometry_id == polygon_id)
        .delete(synchronize_session=False)
    )


# Delete polygon
def delete_polygon_by_id(polygon_id: int, db: Session):
    delete_impacted_grids_by_polygon_id(polygon_id, db)

    polygon = get_polygon_by_id(polygon_id, db)

    if not polygon:
        return None

    db.delete(polygon)
    db.commit()
    return polygon
