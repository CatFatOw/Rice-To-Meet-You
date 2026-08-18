"""File handling core logic that interacts w/ the database"""
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from models.final_visitor_tables import VisitorData
from services.final_visitor_services import load_data
from collections import defaultdict

class VisitorRepository:
    _cache = {}
    def __init__(self, db:Session):
        self.db = db
    # cache all point values
    @classmethod
    def initialize_table(cls, db:Session):
        """method gets every single point values and caches them)"""
        cache = defaultdict(list)
        datapoints = db.query(VisitorData).yield_per(100_000)

        for count, row in enumerate(datapoints, start=1):
            # key is in the format of: ("kansas city", date(2026, 8, 16))
            key = (row.city.strip().lower(), row.local_date)
            values = {"id":row.id, "city":row.city, "brand":row.brand, "avg_daily_visits":row.avg_daily_visits, "latitude":row.latitude, "longitude": row.longitude}
            cache[key].append(values)

            if count % 100_000 == 0:
                print(f"Pre-loaded {count:,} visitor rows...")

        # shared in memory dictionary
        cls._cache = dict(cache)

    def getVisitorDataByCityDate(self, city, date):
        """Method gets/filters data given a city and date. For example
        ("kansas city", date(2026, 8, 16))
        """
        key = (city.strip().lower(), date)
        return self._cache.get(key, [])


# # function to update the database entirely.
# def update_table(file_path, db:Session):
#     """Function updates the database with new data"""
#     BATCH_SIZE = 10_000
#     records = load_data(file_path)
#     if not records:
#         raise HTTPException(status.HTTP_404_NOT_FOUND)
#     # populate the table
#     for start in range(0, len(records), BATCH_SIZE):
#         batch = records[start: start + BATCH_SIZE]
#
#         db.bulk_save_objects(batch)
#         db.commit()
#     return f"Finished adding all data to the table: {len(records)}"
#



