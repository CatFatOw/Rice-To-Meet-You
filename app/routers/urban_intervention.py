from dataclasses import asdict
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from database import SessionLocal
from repository.urban_internvetion_repository import UrbanInterventionRepository
from schemas.urban_intervention import InterventionStatus, UrbanInterventionCreate

router = APIRouter(prefix="/urban_intervention", tags=["urban_intervention"])


@router.post("/create-urban-intervention", status_code=201)
def create_urban_intervention(payload: UrbanInterventionCreate) -> dict:
    db = SessionLocal()
    intervention = UrbanInterventionRepository(db).create(payload)
    db.commit()
    return asdict(intervention)


@router.get("/get-urban-interventions-by-city-date", status_code=200)
def get_urban_interventions_by_city_date(city: str, as_of: date) -> list[dict]:
    db = SessionLocal()
    interventions = UrbanInterventionRepository(db).get_many_by_city_and_date(
        city=city,
        as_of=as_of,
    )
    return [asdict(intervention) for intervention in interventions]


@router.get("/get-urban-interventions-by-city-between-dates", status_code=200)
def get_urban_interventions_by_city_between_dates(
    city: str,
    from_date: date,
    to_date: date,
    statuses: Optional[List[InterventionStatus]] = Query(None),
) -> list[dict]:
    """Return every intervention in a city active at any point in a date range."""
    db = SessionLocal()
    # When called directly in Python, default QueryParam is not resolved by FastAPI dependency injection
    resolved_statuses = None if not isinstance(statuses, list) else statuses
    try:
        interventions = UrbanInterventionRepository(db).get_all_by_city_between_date(
            city=city,
            from_date=from_date,
            to_date=to_date,
            statuses=resolved_statuses,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return [asdict(intervention) for intervention in interventions]
