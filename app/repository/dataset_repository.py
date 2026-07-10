"""File contains core query logic for the dataset router """
from typing import Union

from sqlalchemy.orm import Session

from schemas import dataset_schemas


DatasetCreateSchema = Union[
    dataset_schemas.CorePoiGeometryCreate,
    dataset_schemas.DailySpendBrandStateCreate,
    dataset_schemas.DailyWeatherRiceCreate,
    dataset_schemas.SpendPatternsRiceCreate,
    dataset_schemas.UrbanHeatIndexCreate,
    dataset_schemas.StoreVisitsCreate,
]


def get_all_dataset(model, db: Session, curr_user):
    """Function contains the db querying logic and gets all rows/cols from the table"""
    return db.query(model).filter(model.user_id == curr_user.id).all()


def get_all_dataset_unscoped(model, db: Session):
    """Function gets all rows/cols from the table across every user."""
    return db.query(model).all()


def get_specific_data(id: int, model, db: Session, curr_user):
    """Function contains the db querying logic to get specific row by row ID"""
    return db.query(model).filter(model.id == id, model.user_id == curr_user.id).first()


def post_data(payload: DatasetCreateSchema, model, db: Session, curr_user):
    """Function posts the db querying logic """
    content = model(**payload.model_dump(), user_id=curr_user.id)
    db.add(content)
    db.commit()
    db.refresh(content)
    return content 


def bulk_post_data(payloads: list[DatasetCreateSchema], model, db: Session, curr_user):
    """Function bulk inserts dataset rows for the current user."""
    rows = [model(**payload.model_dump(), user_id=curr_user.id) for payload in payloads]
    db.add_all(rows)
    db.commit()
    return rows


def update_data(payload: DatasetCreateSchema, id: int, model, db: Session, curr_user):
    """Function handles the db udpating logic """
    id_content = db.query(model).filter(model.id == id, model.user_id == curr_user.id).first()
    if not id_content:
        return None

    # Update the row with the new information
    for key, value in payload.model_dump().items():
        setattr(id_content, key, value)
    db.commit()
    db.refresh(id_content)
    return id_content


def delete_data(id: int, model, db: Session, curr_user):
    """Function handles data deletion logic"""
    id_content = db.query(model).filter(model.id == id, model.user_id == curr_user.id).first()

    if not id_content:
        return False

    db.delete(id_content)
    db.commit()
    return True
