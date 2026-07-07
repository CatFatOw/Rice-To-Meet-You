from fastapi import FastAPI, HTTPException, Depends, status 
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session 
import database 
import models
from routers import dataset, grid_geometry, grid_interpolation, grid_metrics, login, nws_weather, poi_polygons, polygon, traffic_prediction, users
from routers.front_end_routes import heatmap



app = FastAPI()

# Allow the local Vite frontend to call the API while you are developing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dataset.router)
app.include_router(users.router)
app.include_router(login.router)
app.include_router(nws_weather.router)
app.include_router(grid_geometry.router)
app.include_router(grid_metrics.router)
app.include_router(grid_interpolation.router)
app.include_router(poi_polygons.router)
app.include_router(polygon.router)
app.include_router(heatmap.router)
app.include_router(traffic_prediction.router)

# Show which tables are gonna be created
print(database.Base.metadata.tables.keys())

# No need to bind engine as alembic handles that automatically
