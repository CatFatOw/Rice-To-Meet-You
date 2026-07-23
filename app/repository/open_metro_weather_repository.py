from sqlalchemy.orm import Session

from models.open_metro_tables import OpenMeteoForecast
from schemas.open_metro_weather_schemas import OpenMeteoForecastCreate


def get_all_values(db: Session) -> list[OpenMeteoForecast]:
    """Return all stored Open-Meteo forecasts."""
    return db.query(OpenMeteoForecast).order_by(OpenMeteoForecast.fetched_at.desc()).all()


def get_values_for_export(limit: int, db: Session) -> list[OpenMeteoForecast]:
    """Return the newest saved forecasts for a bounded CSV export."""
    return (
        db.query(OpenMeteoForecast)
        .order_by(OpenMeteoForecast.fetched_at.desc())
        .limit(limit)
        .all()
    )


def get_values_by_id(
    forecast_id: int,
    db: Session,
) -> OpenMeteoForecast | None:
    """Return one forecast by ID."""
    return (
        db.query(OpenMeteoForecast)
        .filter(OpenMeteoForecast.id == forecast_id)
        .first()
    )


def add_value(
    payload: OpenMeteoForecastCreate,
    db: Session,
) -> OpenMeteoForecast:
    """Create and save a forecast."""
    forecast = OpenMeteoForecast(**payload.model_dump())

    db.add(forecast)
    db.commit()
    db.refresh(forecast)

    return forecast


def update_value(
    old_payload: OpenMeteoForecast,
    new_payload: OpenMeteoForecastCreate,
    db: Session,
) -> OpenMeteoForecast:
    """Update an existing forecast."""
    update_data = new_payload.model_dump()

    for key, value in update_data.items():
        setattr(old_payload, key, value)

    db.commit()
    db.refresh(old_payload)

    return old_payload


def delete_value(
    forecast: OpenMeteoForecast,
    db: Session,
) -> None:
    """Delete an existing forecast."""
    db.delete(forecast)
    db.commit()
