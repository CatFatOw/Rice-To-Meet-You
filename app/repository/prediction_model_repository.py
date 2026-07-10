"""Core database querying logic for prediction-model data."""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from models.prediction_model_tables import HeatDataML, VisitorDataML
from schemas.prediction_model_schemas import HeatDataMLCreate, VisitorDataMLCreate


# =========================================================
# Heat querying logic
# =========================================================

def get_all_heat_data(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[HeatDataML]:
    """Return paginated heat-data records."""

    return (
        db.query(HeatDataML)
        .order_by(HeatDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_heat_data_by_id(
    heat_data_id: int,
    db: Session,
) -> HeatDataML | None:
    """Return one heat-data record by its primary key."""

    return (
        db.query(HeatDataML)
        .filter(HeatDataML.id == heat_data_id)
        .first()
    )


def get_heat_data_by_lat_lon(
    lat: float,
    lon: float,
    db: Session,
    tolerance: float = 0.0001,
    skip: int = 0,
    limit: int = 100,
) -> list[HeatDataML]:
    """Return heat-data records near the given coordinates."""

    return (
        db.query(HeatDataML)
        .filter(
            HeatDataML.latitude.between(
                lat - tolerance,
                lat + tolerance,
            ),
            HeatDataML.longitude.between(
                lon - tolerance,
                lon + tolerance,
            ),
        )
        .order_by(HeatDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_heat_data_by_date(
    target_date: date,
    db: Session,
    skip: int = 0,
    limit: int = 1000,
) -> list[HeatDataML]:
    """Return heat-data records from one UTC calendar date."""

    start_datetime = datetime.combine(
        target_date,
        time.min,
        tzinfo=UTC,
    )
    end_datetime = start_datetime + timedelta(days=1)

    return (
        db.query(HeatDataML)
        .filter(
            HeatDataML.date >= start_datetime,
            HeatDataML.date < end_datetime,
        )
        .order_by(HeatDataML.date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_heat_data(payload: HeatDataMLCreate, db: Session) -> HeatDataML:
    """Create one heat-data record."""
    row = HeatDataML(**payload.model_dump(exclude_none=True))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bulk_create_heat_data(payloads: list[HeatDataMLCreate], db: Session) -> list[HeatDataML]:
    """Create many heat-data records."""
    rows = [HeatDataML(**payload.model_dump(exclude_none=True)) for payload in payloads]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def update_heat_data(heat_data_id: int, payload: HeatDataMLCreate, db: Session) -> HeatDataML | None:
    """Replace one heat-data record."""
    row = get_heat_data_by_id(heat_data_id, db)
    if not row:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_heat_data(heat_data_id: int, db: Session) -> bool:
    """Delete one heat-data record."""
    row = get_heat_data_by_id(heat_data_id, db)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


# =========================================================
# Visitor querying logic
# =========================================================

def get_all_visitors(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[VisitorDataML]:
    """Return paginated visitor records."""

    return (
        db.query(VisitorDataML)
        .order_by(VisitorDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_visitor_by_id(
    visitor_id: int,
    db: Session,
) -> VisitorDataML | None:
    """Return one visitor record by its database ID."""

    return (
        db.query(VisitorDataML)
        .filter(VisitorDataML.id == visitor_id)
        .first()
    )


def get_visitors_by_date(
    target_date: date,
    db: Session,
    skip: int = 0,
    limit: int = 1000,
) -> list[VisitorDataML]:
    """Return visitor records from one UTC calendar date."""

    start_datetime = datetime.combine(
        target_date,
        time.min,
        tzinfo=UTC,
    )
    end_datetime = start_datetime + timedelta(days=1)

    return (
        db.query(VisitorDataML)
        .filter(
            VisitorDataML.date >= start_datetime,
            VisitorDataML.date < end_datetime,
        )
        .order_by(VisitorDataML.date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_visitors_by_market(
    market: str,
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[VisitorDataML]:
    """Return visitor records from the requested market."""

    return (
        db.query(VisitorDataML)
        .filter(VisitorDataML.market == market)
        .order_by(VisitorDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_visitor_by_foursquare_id(
    fsq_place_id: str,
    db: Session,
) -> VisitorDataML | None:
    """Return a visitor record by its Foursquare place ID."""

    return (
        db.query(VisitorDataML)
        .filter(VisitorDataML.fsq_place_id == fsq_place_id)
        .first()
    )


def get_visitors_by_lat_lon(
    lat: float,
    lon: float,
    db: Session,
    tolerance: float = 0.0001,
    skip: int = 0,
    limit: int = 100,
) -> list[VisitorDataML]:
    """Return visitor records near the given coordinates."""

    return (
        db.query(VisitorDataML)
        .filter(
            VisitorDataML.latitude.between(
                lat - tolerance,
                lat + tolerance,
            ),
            VisitorDataML.longitude.between(
                lon - tolerance,
                lon + tolerance,
            ),
        )
        .order_by(VisitorDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_visitors_by_category(
    category: str,
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> list[VisitorDataML]:
    """Return visitor records in the requested POI category."""

    return (
        db.query(VisitorDataML)
        .filter(VisitorDataML.category == category)
        .order_by(VisitorDataML.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_visitor_data(payload: VisitorDataMLCreate, db: Session) -> VisitorDataML:
    """Create one visitor-data record."""
    row = VisitorDataML(**payload.model_dump(exclude_none=True))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bulk_create_visitor_data(payloads: list[VisitorDataMLCreate], db: Session) -> list[VisitorDataML]:
    """Create many visitor-data records."""
    rows = [VisitorDataML(**payload.model_dump(exclude_none=True)) for payload in payloads]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def update_visitor_data(visitor_id: int, payload: VisitorDataMLCreate, db: Session) -> VisitorDataML | None:
    """Replace one visitor-data record."""
    row = get_visitor_by_id(visitor_id, db)
    if not row:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_visitor_data(visitor_id: int, db: Session) -> bool:
    """Delete one visitor-data record."""
    row = get_visitor_by_id(visitor_id, db)
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
