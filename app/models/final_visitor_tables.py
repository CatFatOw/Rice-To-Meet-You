"""Table that stores data from: final_visitors_DF"""
from database import Base
from sqlalchemy import Column, Date, Float, Index, Integer, Text, TIMESTAMP
from sqlalchemy.sql import text

class VisitorData(Base):
    __tablename__ = "final_visitor_table"

    id = Column(Integer, primary_key=True, nullable=False)
    city = Column(Text, nullable=False)
    local_date = Column(Date, nullable=False)
    avg_daily_visits = Column(Float, nullable=False)
    location_name = Column(Text, nullable=False)
    brand = Column(Text, nullable=False)
    street_address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        Index("ix_final_visitor_table_city_local_date", "city", "local_date"),
    )
