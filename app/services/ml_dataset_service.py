from datetime import date, datetime
from math import inf
from typing import Any

from sqlalchemy.orm import Session

from models.dataset_tables import CorePoiGeometry
from models.grid_cell_tables import GridCellGeometry


VISITOR_FEATURE_COLUMNS = [
    "timestamp",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "latitude",
    "longitude",
    "state",
    "city",
    "market",
    "source",
    "grid_cell_id",
    "grid_cell_cell_id",
    "grid_row",
    "grid_col",
    "grid_centroid_lat",
    "grid_centroid_lon",
    "poi_id",
    "placekey",
    "safegraph_place_id",
    "location_name",
    "street_address",
    "naics_code",
    "top_category",
    "sub_category",
    "wkt_area_sq_meters",
    "includes_parking_lot",
    "enclosed",
]


WEATHER_HEAT_FEATURE_COLUMNS = [
    "timestamp",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "latitude",
    "longitude",
    "state",
    "city",
    "market",
    "source",
    "grid_cell_id",
    "grid_cell_cell_id",
    "grid_row",
    "grid_col",
    "grid_centroid_lat",
    "grid_centroid_lon",
]


def serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _time_features(timestamp: datetime) -> dict[str, Any]:
    return {
        "timestamp": serialize_value(timestamp),
        "hour_of_day": timestamp.hour,
        "day_of_week": timestamp.weekday(),
        "month": timestamp.month,
        "is_weekend": timestamp.weekday() >= 5,
    }


def _distance_sq(lat: float, lon: float, row_lat: float | None, row_lon: float | None) -> float:
    if row_lat is None or row_lon is None:
        return inf
    return ((row_lat - lat) ** 2) + ((row_lon - lon) ** 2)


def _grid_cell_by_id(db: Session, grid_cell_id: int | None):
    if not grid_cell_id:
        return None
    return db.query(GridCellGeometry).filter(GridCellGeometry.id == grid_cell_id).first()


def _nearest_grid_cell(db: Session, lat: float, lon: float, state: str | None):
    query = db.query(GridCellGeometry)
    if state:
        query = query.filter(GridCellGeometry.state.ilike(state))
    cells = query.limit(10000).all()
    if not cells:
        return None
    return min(
        cells,
        key=lambda cell: _distance_sq(lat, lon, cell.grid_centroid_lat, cell.grid_centroid_lon),
    )


def _grid_cell_for_request(db: Session, lat: float, lon: float, state: str | None, grid_cell_id: int | None):
    return _grid_cell_by_id(db, grid_cell_id) or _nearest_grid_cell(db, lat, lon, state)


def _nearest_poi(db: Session, lat: float, lon: float, state: str | None, city: str | None, poi_id: int | None):
    if poi_id:
        return db.query(CorePoiGeometry).filter(CorePoiGeometry.id == poi_id).first()

    query = db.query(CorePoiGeometry)
    if state:
        query = query.filter(CorePoiGeometry.region.ilike(state))
    if city:
        query = query.filter(CorePoiGeometry.city.ilike(city))
    pois = query.limit(5000).all()
    if not pois:
        return None
    return min(pois, key=lambda poi: _distance_sq(lat, lon, poi.latitude, poi.longitude))


def _grid_payload(grid_cell: GridCellGeometry | None) -> dict[str, Any] | None:
    if not grid_cell:
        return None
    return {
        "id": grid_cell.id,
        "cell_id": grid_cell.cell_id,
        "row": grid_cell.row,
        "col": grid_cell.col,
        "grid_centroid_lat": grid_cell.grid_centroid_lat,
        "grid_centroid_lon": grid_cell.grid_centroid_lon,
        "state": grid_cell.state,
    }


def _poi_payload(poi: CorePoiGeometry | None) -> dict[str, Any] | None:
    if not poi:
        return None
    return {
        "id": poi.id,
        "placekey": poi.placekey,
        "safegraph_place_id": poi.safegraph_place_id,
        "location_name": poi.location_name,
        "latitude": poi.latitude,
        "longitude": poi.longitude,
        "market": poi.market,
        "city": poi.city,
        "state": poi.region,
        "postal_code": poi.postal_code,
        "street_address": poi.street_address,
        "naics_code": poi.naics_code,
        "top_category": poi.top_category,
        "sub_category": poi.sub_category,
        "polygon_wkt": poi.polygon_wkt,
        "wkt_area_sq_meters": poi.wkt_area_sq_meters,
        "includes_parking_lot": poi.includes_parking_lot,
        "enclosed": poi.enclosed,
    }


def _base_click_row(
    *,
    lat: float,
    lon: float,
    state: str,
    city: str | None,
    source: str | None,
    timestamp: datetime,
    grid_cell: GridCellGeometry | None,
) -> dict[str, Any]:
    time_features = _time_features(timestamp)
    market = city or state
    return {
        "request": {
            "latitude": lat,
            "longitude": lon,
            "state": state,
            "city": city,
            "source": source,
            **time_features,
        },
        "grid": _grid_payload(grid_cell),
        **time_features,
        "latitude": lat,
        "longitude": lon,
        "state": state,
        "city": city,
        "market": market,
        "source": source,
        "grid_cell_id": grid_cell.id if grid_cell else None,
        "grid_cell_cell_id": grid_cell.cell_id if grid_cell else None,
        "grid_row": grid_cell.row if grid_cell else None,
        "grid_col": grid_cell.col if grid_cell else None,
        "grid_centroid_lat": grid_cell.grid_centroid_lat if grid_cell else None,
        "grid_centroid_lon": grid_cell.grid_centroid_lon if grid_cell else None,
    }


def get_visitor_prediction_input(
    db: Session,
    lat: float,
    lon: float,
    state: str,
    timestamp: datetime,
    city: str | None = None,
    grid_cell_id: int | None = None,
    poi_id: int | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    grid_cell = _grid_cell_for_request(db, lat, lon, state, grid_cell_id)
    poi = _nearest_poi(db, lat, lon, state, city, poi_id) if poi_id or source == "poi" else None
    poi_context = _poi_payload(poi)
    row = {
        **_base_click_row(
            lat=lat,
            lon=lon,
            state=state,
            city=city,
            source=source or ("poi" if poi else "grid_centroid"),
            timestamp=timestamp,
            grid_cell=grid_cell,
        ),
        "poi": poi_context,
        "poi_id": poi.id if poi else None,
        "placekey": poi.placekey if poi else None,
        "safegraph_place_id": poi.safegraph_place_id if poi else None,
        "location_name": poi.location_name if poi else None,
        "street_address": poi.street_address if poi else None,
        "naics_code": poi.naics_code if poi else None,
        "top_category": poi.top_category if poi else None,
        "sub_category": poi.sub_category if poi else None,
        "wkt_area_sq_meters": poi.wkt_area_sq_meters if poi else None,
        "includes_parking_lot": poi.includes_parking_lot if poi else None,
        "enclosed": poi.enclosed if poi else None,
    }

    return {
        "task": "visitor_prediction",
        "dataset": None,
        "grain": "one frontend click row for a grid centroid or POI",
        "description": "Inference input for visitor models. The row is built only from the frontend click, time features, selected/nearest grid identity, and optional static POI metadata. It does not include previous visitor, spend, weather, heat, or grid metric observations.",
        "row_count": 1,
        "join_keys": ["latitude", "longitude", "state", "timestamp", "poi_id", "grid_cell_id"],
        "feature_columns": VISITOR_FEATURE_COLUMNS,
        "target_columns": ["predicted_daily_visits", "predicted_crowd_density", "predicted_population"],
        "rows": [row],
    }


def get_weather_heat_input(
    db: Session,
    lat: float,
    lon: float,
    state: str,
    timestamp: datetime,
    city: str | None = None,
    grid_cell_id: int | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    grid_cell = _grid_cell_for_request(db, lat, lon, state, grid_cell_id)
    row = _base_click_row(
        lat=lat,
        lon=lon,
        state=state,
        city=city,
        source=source or "grid_centroid",
        timestamp=timestamp,
        grid_cell=grid_cell,
    )
    return {
        "task": "weather_heat",
        "dataset": None,
        "grain": "one frontend click row for a grid centroid or POI",
        "description": "Inference input for heat/weather models. The row is built only from the frontend click, time features, and selected/nearest grid identity. It does not include previous weather, heat, or grid metric observations.",
        "row_count": 1,
        "join_keys": ["latitude", "longitude", "state", "timestamp", "grid_cell_id"],
        "feature_columns": WEATHER_HEAT_FEATURE_COLUMNS,
        "target_columns": ["predicted_heat_index", "predicted_heat_risk", "predicted_temperature", "predicted_precipitation_prob"],
        "rows": [row],
    }


def ml_task_summaries() -> list[dict[str, Any]]:
    return [
        {
            "name": "visitor_prediction",
            "path": "/ml/visitor-prediction/input",
            "description": "POST a clicked grid centroid or POI to build a visitor-model inference row without previous observed metrics.",
            "target_columns": ["predicted_daily_visits", "predicted_crowd_density", "predicted_population"],
        },
        {
            "name": "weather_heat",
            "path": "/ml/weather-heat/input",
            "description": "POST a clicked grid centroid or POI to build a heat/weather-model inference row without previous observed metrics.",
            "target_columns": [
                "predicted_heat_index",
                "predicted_heat_risk",
                "predicted_temperature",
                "predicted_precipitation_prob",
            ],
        },
    ]
