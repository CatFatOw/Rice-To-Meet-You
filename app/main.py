from fastapi import FastAPI, HTTPException, Depends, status 
from sqlalchemy.orm import Session 
import database 
import models
from routers import (
    core_poi,
    dataset,
    grid_geometry,
    grid_interpolation,
    grid_metrics,
    heatmap,
    login,
    nws_weather,
    polygon,
    urban_intervention,
    users,
)



app = FastAPI()
app.include_router(dataset.router)
app.include_router(users.router)
app.include_router(login.router)
app.include_router(nws_weather.router)
app.include_router(grid_geometry.router)
app.include_router(grid_metrics.router)
app.include_router(grid_interpolation.router)
app.include_router(heatmap.router)
app.include_router(core_poi.router)
app.include_router(polygon.router)
app.include_router(urban_intervention.router)

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically
