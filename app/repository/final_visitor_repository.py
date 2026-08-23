"""File handling core logic that interacts w/ the database"""
import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker

from models.final_visitor_tables import VisitorData


class VisitorRepository:
    _cache = {}

    # keep <= the connection pool size (pool_size + max_overflow)
    N_WORKERS = int(os.getenv("VISITOR_LOAD_WORKERS", "8"))
    YIELD_PER = 50_000
    CHUNKS_PER_WORKER = 4  # oversubscribe so uneven id gaps even out

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def _id_ranges(cls, db: Session):
        """Split the pk space into contiguous [lo, hi] windows."""
        lo, hi = db.query(func.min(VisitorData.id), func.max(VisitorData.id)).one()
        if lo is None:
            return []

        n_chunks = cls.N_WORKERS * cls.CHUNKS_PER_WORKER
        step = max(1, math.ceil((hi - lo + 1) / n_chunks))
        return [(start, min(start + step - 1, hi)) for start in range(lo, hi + 1, step)]

    @classmethod
    def _load_range(cls, session_factory, lo, hi):
        """Runs in a worker thread with its own session/connection."""
        local = defaultdict(list)

        with session_factory() as session:
            rows = (
                session.query(
                    VisitorData.id,
                    VisitorData.city,
                    VisitorData.brand,
                    VisitorData.avg_daily_visits,
                    VisitorData.latitude,
                    VisitorData.longitude,
                    VisitorData.local_date,
                )
                .filter(VisitorData.id >= lo, VisitorData.id <= hi)
                .yield_per(cls.YIELD_PER)
            )

            for row in rows:
                key = (row.city.strip().lower(), row.local_date)
                local[key].append({
                    "id": row.id,
                    "city": row.city,
                    "brand": row.brand,
                    "avg_daily_visits": row.avg_daily_visits,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                })

        return local

    @classmethod
    def initialize_table(cls, db: Session):
        """Fetch every point value in parallel and cache it in memory."""
        ranges = cls._id_ranges(db)
        if not ranges:
            cls._cache = {}
            return

        session_factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
        cache = defaultdict(list)
        total = 0

        with ThreadPoolExecutor(max_workers=cls.N_WORKERS) as pool:
            futures = [
                pool.submit(cls._load_range, session_factory, lo, hi)
                for lo, hi in ranges
            ]
            for future in futures:
                partial = future.result()  # re-raises worker exceptions here
                for key, values in partial.items():
                    cache[key].extend(values)
                    total += len(values)
                print(f"Pre-loaded {total:,} visitor rows...")

        cls._cache = dict(cache)

    def getVisitorDataByCityDate(self, city, date):
        """Method gets/filters data given a city and date. For example
        ("kansas city", date(2026, 8, 16))
        """
        key = (city.strip().lower(), date)
        return self._cache.get(key, [])