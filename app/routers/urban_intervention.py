from dataclasses import asdict
from datetime import date

from fastapi import APIRouter

from database import SessionLocal
from repository.urban_internvetion_repository import UrbanInterventionRepository
from schemas.urban_intervention import UrbanInterventionCreate

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
