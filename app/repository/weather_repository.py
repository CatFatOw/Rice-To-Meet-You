"""Database access helpers for weather observation routes."""
from datetime import datetime

from sqlalchemy import tuple_
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

    apply_nws_observation_data(observation, observation_data)
    return observation, created


def apply_nws_observation_data(observation, observation_data: dict):
    """Apply normalized NWS summary data to a weather observation row."""
    observation.temperature = observation_data["temperature"]["value"]
    observation.humidity = observation_data["humidity"]
    observation.dewpoint = observation_data["dewpoint_c"]
    observation.wind_direction = observation_data["wind"]["direction"]
    observation.precipitation_prob = observation_data["precipitation_probability"]
    observation.detailed_forecast = observation_data["forecast"]["detailed"]
    return observation


def bulk_upsert_nws_observations(observation_assignments, db: Session):
    """Create or update many NWS weather observations with one existing-row lookup."""
    if not observation_assignments:
        return 0, 0

    normalized_assignments = [
        (
            grid_cell_id,
            datetime.fromisoformat(observation_data["time"]),
            observation_data,
        )
        for grid_cell_id, observation_data in observation_assignments
    ]
    lookup_keys = {
        (grid_cell_id, timestamp)
        for grid_cell_id, timestamp, _ in normalized_assignments
    }

    existing_rows = []
    lookup_key_list = list(lookup_keys)
    for start in range(0, len(lookup_key_list), 500):
        chunk = lookup_key_list[start:start + 500]
        existing_rows.extend(
            db.query(weather_tables.WeatherObservation)
            .filter(weather_tables.WeatherObservation.source == "NWS")
            .filter(
                tuple_(
                    weather_tables.WeatherObservation.grid_cell_id,
                    weather_tables.WeatherObservation.timestamp,
                ).in_(chunk)
            )
            .all()
        )

    existing_by_key = {
        (row.grid_cell_id, row.timestamp): row
        for row in existing_rows
    }

    created_count = 0
    updated_count = 0

    for grid_cell_id, timestamp, observation_data in normalized_assignments:
        key = (grid_cell_id, timestamp)
        observation = existing_by_key.get(key)

        if observation is None:
            observation = weather_tables.WeatherObservation(
                grid_cell_id=grid_cell_id,
                timestamp=timestamp,
                source="NWS",
            )
            db.add(observation)
            existing_by_key[key] = observation
            created_count += 1
        else:
            updated_count += 1

        apply_nws_observation_data(observation, observation_data)

    return created_count, updated_count


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
