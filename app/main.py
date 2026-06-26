from fastapi import FastAPI, HTTPException, Depends, status 
from sqlalchemy.orm import Session 
import database 
import models
from routers import dataset, login, users



app = FastAPI()
app.include_router(dataset.router)
app.include_router(users.router)
app.include_router(login.router)

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically
