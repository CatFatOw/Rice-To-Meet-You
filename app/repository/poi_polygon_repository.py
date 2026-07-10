from sqlalchemy.orm import Session
from models import dataset_tables

def get_all_poi(db:Session):
    """Function gets every single core poi and its metadata"""
    poi = db.query(dataset_tables.CorePoiGeometry).all()
    return poi

def create_pois(pois: list[dataset_tables.CorePoiGeometry], db:Session):
    """Function bulk creates core poi rows."""
    db.add_all(pois)
    db.commit()
    return pois

def get_poi_by_id(poi_id: int, db: Session):
    """Return one core POI row by database ID."""
    return (
        db.query(dataset_tables.CorePoiGeometry)
        .filter(dataset_tables.CorePoiGeometry.id == poi_id)
        .first()
    )

def get_all_poi_by_city(city:str, db:Session):
    """Function gets every single core poi from city and db and extra information"""
    poi = db.query(dataset_tables.CorePoiGeometry).filter(dataset_tables.CorePoiGeometry.city.ilike(city)).all()
    return poi 

def get_poi_polygons_for_city_state(
    city: str | None,
    state: str | None,
    db: Session,
    category: str | None = None,
    limit: int = 250,
):
    """Return core POIs with footprint polygons for a city/state frontend map."""
    query = db.query(dataset_tables.CorePoiGeometry).filter(
        dataset_tables.CorePoiGeometry.polygon_wkt.isnot(None)
    )

    if city:
        query = query.filter(dataset_tables.CorePoiGeometry.city.ilike(city))
    if state:
        query = query.filter(dataset_tables.CorePoiGeometry.region.ilike(state))
    if category:
        query = query.filter(
            dataset_tables.CorePoiGeometry.top_category.ilike(f"%{category}%")
            | dataset_tables.CorePoiGeometry.sub_category.ilike(f"%{category}%")
        )

    return (
        query.order_by(dataset_tables.CorePoiGeometry.wkt_area_sq_meters.desc())
        .limit(limit)
        .all()
    )

def get_poi_types(db:Session):
    """Returns a list of unique color poi categories"""
    types = db.query(dataset_tables.CorePoiGeometry.top_category).filter(dataset_tables.CorePoiGeometry.top_category.isnot(None)).distinct().all()
    return sorted([row[0] for row in types])
