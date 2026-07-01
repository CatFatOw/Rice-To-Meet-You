"""Routes for fetching key National Weather Service API data."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session 
from requests.exceptions import RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import get_db
from models import grid_cell_tables, weather_tables
from schemas import weather_schemas
from fastapi.responses import Response
from datetime import datetime
from services.national_weather import get_hourly_forecast, get_grid_forecast, get_state_bbox, split_bbox_into_cell, get_detailed_weather_summary
from routers.grid_geometry import get_state_grid_cells


router = APIRouter(prefix="/weather", tags=["weather"])


def fetch_weather_observation_for_cell(cell_data: dict):
    """Fetch the current NWS weather data for one grid cell without using the DB session."""
    # NWS gives us the hourly URL from /points/{lat},{lon}; the service uses that URL directly.
    return {
        "grid_cell_id": cell_data["grid_cell_id"],
        "cell_id": cell_data["cell_id"],
        "observation_data": get_detailed_weather_summary(cell_data["lat"], cell_data["lon"]),
    }


def save_weather_observation_data(grid_cell_id: int, observation_data: dict, db: Session):
    """Create or update the latest NWS weather row after weather data has been fetched."""
    timestamp = datetime.fromisoformat(observation_data["time"])

    observation = (
        db.query(weather_tables.WeatherObservation)
        .filter(
            weather_tables.WeatherObservation.grid_cell_id == grid_cell_id,
            weather_tables.WeatherObservation.timestamp == timestamp,
            weather_tables.WeatherObservation.source == "NWS",
        )
        .first()
    )
    created = observation is None

    if created:
        observation = weather_tables.WeatherObservation(
            grid_cell_id=grid_cell_id,
            timestamp=timestamp,
            source="NWS",
        )
        db.add(observation)

    observation.temperature = observation_data["temperature"]["value"]
    observation.humidity = observation_data["humidity"]
    observation.dewpoint = observation_data["dewpoint_c"]
    observation.wind_direction = observation_data["wind"]["direction"]
    observation.precipitation_prob = observation_data["precipitation_probability"]
    observation.detailed_forecast = observation_data["forecast"]["detailed"]

    return observation, created


def save_weather_observation_for_cell(cell, db: Session):
    """Create or update the latest NWS weather row for one grid cell."""
    fetched = fetch_weather_observation_for_cell({
        "grid_cell_id": cell.id,
        "cell_id": cell.cell_id,
        "lat": cell.grid_centroid_lat,
        "lon": cell.grid_centroid_lon,
    })
    return save_weather_observation_data(fetched["grid_cell_id"], fetched["observation_data"], db)


def assign_weather_for_cells(cells, db: Session, max_workers: int, skip_existing: bool, limit: int | None):
    """Fetch NWS data concurrently, then save successful rows with the request DB session."""
    created_count = 0
    updated_count = 0
    failed = []
    skipped_existing = 0
    max_workers = max(1, min(max_workers, 20))

    if skip_existing:
        cell_ids = [cell.id for cell in cells]
        existing_cell_ids = {
            row[0]
            for row in (
                db.query(weather_tables.WeatherObservation.grid_cell_id)
                .filter(weather_tables.WeatherObservation.grid_cell_id.in_(cell_ids))
                .distinct()
                .all()
            )
        }
        skipped_existing = len(existing_cell_ids)
        cells = [cell for cell in cells if cell.id not in existing_cell_ids]

    if limit is not None:
        cells = cells[:max(0, limit)]

    cell_data = [
        {
            "grid_cell_id": cell.id,
            "cell_id": cell.cell_id,
            "lat": cell.grid_centroid_lat,
            "lon": cell.grid_centroid_lon,
        }
        for cell in cells
    ]

    # Network calls are the slow part, so fetch several cells at once.
    # Database writes stay in this request thread because SQLAlchemy sessions are not thread-safe.
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_weather_observation_for_cell, cell): cell
            for cell in cell_data
        }
        for future in as_completed(futures):
            cell = futures[future]
            try:
                fetched = future.result()
                _, created = save_weather_observation_data(
                    fetched["grid_cell_id"],
                    fetched["observation_data"],
                    db,
                )
            except RequestException as exc:
                failed.append({"grid_cell_id": cell["grid_cell_id"], "cell_id": cell["cell_id"], "error": str(exc)})
                continue

            if created:
                created_count += 1
            else:
                updated_count += 1

    db.commit()
    return {
        "created": created_count,
        "updated": updated_count,
        "skipped_existing": skipped_existing,
        "failed": len(failed),
        "failures": failed[:10],
        "count": created_count + updated_count,
        "requested": len(cell_data),
    }


# Get all weather data across all cell data 
@router.get("/fetch/all", response_model=list[weather_schemas.WeatherObservationResponse])
async def get_forecast_grid_all(db:Session=Depends(get_db)):
    """Function gets every single grid's weather data"""
    data = db.query(weather_tables.WeatherObservation).all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"WEATHER DATA NOT FOUND")
    return data

# Get the specific weather data in that cell region 
@router.get("/fetch/{id}", response_model=weather_schemas.WeatherObservationResponse)
async def get_forecast_grid_id(id:int, db:Session=Depends(get_db)):
    """function gets the speicifc nws weather from a specific grid"""
    data = db.query(weather_tables.WeatherObservation).filter(weather_tables.WeatherObservation.grid_cell_id == id).first()

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"WEATHER DATA NOT FOUND")
    return data

# Create or assign weather metrics to a cell
@router.post(f"/fetch/create/{{grid_cell_id}}", response_model=weather_schemas.WeatherObservationResponse)
async def add_weather_data_grid(grid_cell_id:int, db:Session=Depends(get_db)):
    """Function creates an entry in the db"""
    # Get the specific lat, lon
    cell = db.query(grid_cell_tables.GridCellGeometry).filter(grid_cell_tables.GridCellGeometry.id == grid_cell_id).first()
    if not cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"GRID NOT FOUND")

    existing_observation = (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.grid_cell_id == cell.id)
        .first()
    )
    if existing_observation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"ALREADY CREATED. CANNOT CREATE")
    # otherwise data doesn't exist 
    try:
        new_data, _ = save_weather_observation_for_cell(cell, db)
    except RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"NWS weather request failed for grid cell {cell.id}: {exc}",
        )
    db.commit()
    db.refresh(new_data)
    return new_data

# Update weather data 
@router.put("/fetch/update/{id}", response_model=weather_schemas.WeatherObservationResponse)
async def _update_weather_data_grid(id:int,observation:weather_schemas.WeatherObservationCreate, db:Session=Depends(get_db)):
    """Function updates weather data for a grid cell id"""
    data = db.query(weather_tables.WeatherObservation).filter(weather_tables.WeatherObservation.grid_cell_id == id).first()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID NOT FOUND")
    # Update 
    for key, value in observation.model_dump().items():
        setattr(data, key, value)
    db.commit()
    db.refresh(data)
    return data

@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weather_data_grid(id:int, db:Session = Depends(get_db)):
    """Function deletes specificed cell/etc"""
    data = db.query(weather_tables.WeatherObservation).filter(weather_tables.WeatherObservation.id == id).first()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID NOT FOUND")
    db.delete(data)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)



# Get the latest metrics for the grid cell 
@router.get("/grid/{grid_cell_id}/latest", response_model=weather_schemas.WeatherObservationResponse)
async def get_latest_weather_grid(grid_cell_id:int, db:Session=Depends(get_db)):
    """Function gets the latest weather metrics for each grid"""
    data = (
        db.query(weather_tables.WeatherObservation)
        .filter(weather_tables.WeatherObservation.grid_cell_id == grid_cell_id)
        .order_by(weather_tables.WeatherObservation.timestamp.desc())
        .first()
    )
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID NOT FOUND")
    return data

# Get specific weather history
@router.get("/grid/{grid_cell_id}", response_model=list[weather_schemas.WeatherObservationResponse])
async def get_weather_history_grid(grid_cell_id:int, db:Session = Depends(get_db)):
    """function gets entire weather history of a grid cell"""

    data = db.query(weather_tables.WeatherObservation).filter(weather_tables.WeatherObservation.grid_cell_id == grid_cell_id).all()
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID NOT FOUND")
    return data


# Assign weather for every single cell
@router.post("/assign_all")
async def assign_weather_all(
    max_workers:int=12,
    skip_existing:bool=True,
    limit:int | None=None,
    db:Session=Depends(get_db)
):
    """Function assigns weather values to all cells (even if it already has previous values)"""
    all_cells = db.query(grid_cell_tables.GridCellGeometry).all()
    if not all_cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NOT FOUND")

    result = assign_weather_for_cells(all_cells, db, max_workers, skip_existing, limit)
    return {
        "message": "Successfully assigned weather.",
        "max_workers": max(1, min(max_workers, 20)),
        "skip_existing": skip_existing,
        "limit": limit,
        **result,
    }
    



# Assign weather for each cell in state
@router.post("/assign_state")
async def assign_weather_state(
    state:str,
    max_workers:int=12,
    skip_existing:bool=True,
    limit:int | None=None,
    db:Session=Depends(get_db)
):
    """Function assigns weather (or updates) the cells in the selected state"""
    all_cells = get_state_grid_cells(state, db)

    result = assign_weather_for_cells(all_cells, db, max_workers, skip_existing, limit)
    return {
        "message": "Successfully assigned weather.",
        "max_workers": max(1, min(max_workers, 20)),
        "skip_existing": skip_existing,
        "limit": limit,
        **result,
        "state": state,
    }
    
                                                                   

 
