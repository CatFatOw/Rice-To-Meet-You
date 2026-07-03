from database import Base 
from sqlalchemy import Integer, Text, TIMESTAMP, Column, JSON, Float
from sqlalchemy.sql.expression import text


# ----------------------------Tables in databasee used to store predictions ----------------------------

class PredictionTable(Base):
    """Example prediction table and column values we could store"""
    __tablename__ = "prediction_table"
    id = Column(Integer, primary_key=True, nullable=False)
    pred_longitude = Column(Float, nullable=False, index=True)
    pred_latitude = Column(Float, nullable=False, index=True)
    pred_model_name = Column(Text, nullable=False, index=True)
    pred_metrics = Column(JSON, nullable=False)
    pred_color = Column(Text, nullable=False)
    pred_polygon_grid = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
