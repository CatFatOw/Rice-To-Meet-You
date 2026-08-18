from datetime import date
import logging

from celery_workers.celery_app import celery_app
from database import SessionLocal
from repository.final_visitor_repository import VisitorRepository

logger = logging.getLogger(__name__)


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)

def warm_visitor_cache(city: str, date_string: str) -> dict:
    db = SessionLocal()

    try:
        repository = VisitorRepository(db)
        visitor_rows = repository.getVisitorDataByCityDate(
            city,
            date.fromisoformat(date_string),
        )

        logger.info(
            "Visitor cache warm complete: city=%s date=%s datapoints=%s",
            city,
            date_string,
            len(visitor_rows),
        )

        return {
            "city": city,
            "date": date_string,
            "rows_cached": len(visitor_rows),
        }
    finally:
        db.close()
