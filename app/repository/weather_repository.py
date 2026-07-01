"""Database access helpers for weather observation routes."""
from datetime import datetime

from sqlalchemy.orm import Session

from models import grid_cell_tables, weather_tables


def get_all_observations(db: Session):
    """Get every saved weather observation."""
    return db.query(weather_tables.WeatherObservation).all()


def get_grid_cell_by_id(grid_cell_id: int, db: Session):
    """Get one grid cell by primary key."""
    return (
        db.query(grid_cell_tables.GridCellGeometry)
        .filter(grid_cell_tables.GridCellGeometry.id == grid_cell_id)
        .first()
    )


def get_all_grid_cells(db: Session):
    """Get every grid cell."""
    return db.query(grid_cell_tables.GridCellGeometry).all()


def get_first_observation_for_grid_cell(grid_cell_id: int, db: Session):
    """Get one weather observation for a grid cell."""
    return (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.grid_cell_id == grid_cell_id)
        .first()
    )


def get_observation_by_id(id: int, db: Session):
    """Get one weather observation by primary key."""
    return (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.id == id)
        .first()
    )


def get_latest_observation_for_grid_cell(grid_cell_id: int, db: Session):
    """Get latest weather observation for one grid cell."""
    return (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.grid_cell_id == grid_cell_id)
        .order_by(weather_tables.WeatherObservation.timestamp.desc())
        .first()
    )


def get_observation_history_for_grid_cell(grid_cell_id: int, db: Session):
    """Get all weather observations for one grid cell."""
    return (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.grid_cell_id == grid_cell_id)
        .all()
    )


def get_existing_observation_cell_ids(grid_cell_ids, db: Session):
    """Get grid cell IDs that already have at least one weather observation."""
    return {
        row[0]
        for row in (
            db.query(weather_tables.WeatherObservation.grid_cell_id)
            .filter(weather_tables.WeatherObservation.grid_cell_id.in_(grid_cell_ids))
            .distinct()
            .all()
        )
    }


def upsert_nws_observation(grid_cell_id: int, observation_data: dict, db: Session):
    """Create or update one NWS weather observation from fetched NWS data."""
    timestamp = datetime.fromisoformat(observation_data["time"])

    observation = (
        db.query(weather_tables.WeatherObservation)
        .filter(
            weather_tables.WeatherObservation.grid_cell_id == grid_cell_id,
            weather_tables.WeatherObservation.timestamp == timestamp,
            weather_tables.WeatherObservation.source == "NWS",
        )
        .first()
    )
    created = observation is None

    if created:
        observation = weather_tables.WeatherObservation(
            grid_cell_id=grid_cell_id,
            timestamp=timestamp,
            source="NWS",
        )
        db.add(observation)

    observation.temperature = observation_data["temperature"]["value"]
    observation.humidity = observation_data["humidity"]
    observation.dewpoint = observation_data["dewpoint_c"]
    observation.wind_direction = observation_data["wind"]["direction"]
    observation.precipitation_prob = observation_data["precipitation_probability"]
    observation.detailed_forecast = observation_data["forecast"]["detailed"]

    return observation, created


def update_weather_observation(observation_row, payload, db: Session):
    """Update one weather observation from a Pydantic payload."""
    for key, value in payload.model_dump().items():
        setattr(observation_row, key, value)

    db.commit()
    db.refresh(observation_row)
    return observation_row


def delete_weather_observation(observation_row, db: Session):
    """Delete one weather observation row."""
    db.delete(observation_row)
    db.commit()
    return True
