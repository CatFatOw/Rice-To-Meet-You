from fastapi import FastAPI, HTTPException, Depends, status 
from sqlalchemy.orm import Session 
import database 
import models 



app = FastAPI()

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically