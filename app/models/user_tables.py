"""File is the creation logic for a user table"""
from database import Base 
from sqlalchemy import Integer, TIMESTAMP, Column, Text
from sqlalchemy.sql.expression import text

class User(Base):
    """Creates the user table"""
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(Text, nullable=False, unique=True, index=True)
    password = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
