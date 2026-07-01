"""Routes for fetching key National Weather Service API data."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from database import get_db
from repository.weather_repository import (
    delete_weather_observation,
    get_all_grid_cells,
    get_all_observations,
    get_first_observation_for_grid_cell,
    get_grid_cell_by_id,
    get_latest_observation_for_grid_cell,
    get_observation_by_id,
    get_observation_history_for_grid_cell,
    update_weather_observation,
)
from routers.grid_geometry import get_state_grid_cells
from schemas import weather_schemas
from services.nws_weather_service import (
    assign_weather_for_cells,
    save_weather_observation_for_cell,
)

router = APIRouter(prefix="/weather", tags=["weather"])


def assignment_response(result, max_workers: int, skip_existing: bool, limit: int | None, **extra):
    """Return a consistent assign-weather response payload."""
    return {
        "message": "Successfully assigned weather.",
        "max_workers": max(1, min(max_workers, 20)),
        "skip_existing": skip_existing,
        "limit": limit,
        **result,
        **extra,
    }


# Get all weather data across all cell data
@router.get("/fetch/all", response_model=list[weather_schemas.WeatherObservationResponse])
async def get_forecast_grid_all(db: Session = Depends(get_db)):
    """Get every grid's weather data."""
    data = get_all_observations(db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WEATHER DATA NOT FOUND")
    return data


# Get the specific weather data in that cell region
@router.get("/fetch/{id}", response_model=weather_schemas.WeatherObservationResponse)
async def get_forecast_grid_id(id: int, db: Session = Depends(get_db)):
    """Get one weather observation for a grid cell."""
    data = get_first_observation_for_grid_cell(id, db)

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WEATHER DATA NOT FOUND")
    return data


# Create or assign weather metrics to a cell
@router.post("/fetch/create/{grid_cell_id}", response_model=weather_schemas.WeatherObservationResponse)
async def add_weather_data_grid(grid_cell_id: int, db: Session = Depends(get_db)):
    """Create a weather observation for one grid cell."""
    cell = get_grid_cell_by_id(grid_cell_id, db)
    if not cell:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GRID NOT FOUND")

    existing_observation = get_first_observation_for_grid_cell(cell.id, db)
    if existing_observation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ALREADY CREATED. CANNOT CREATE")

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
async def update_weather_data_grid(
    id: int,
    observation: weather_schemas.WeatherObservationCreate,
    db: Session = Depends(get_db),
):
    """Update weather data for a grid cell id."""
    data = get_first_observation_for_grid_cell(id, db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ID NOT FOUND")

    return update_weather_observation(data, observation, db)


@router.delete("/delete/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weather_data_grid(id: int, db: Session = Depends(get_db)):
    """Delete a specific weather observation."""
    data = get_observation_by_id(id, db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ID NOT FOUND")

    delete_weather_observation(data, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Get the latest metrics for the grid cell
@router.get("/grid/{grid_cell_id}/latest", response_model=weather_schemas.WeatherObservationResponse)
async def get_latest_weather_grid(grid_cell_id: int, db: Session = Depends(get_db)):
    """Get the latest weather metrics for one grid cell."""
    data = get_latest_observation_for_grid_cell(grid_cell_id, db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ID NOT FOUND")
    return data


# Get specific weather history
@router.get("/grid/{grid_cell_id}", response_model=list[weather_schemas.WeatherObservationResponse])
async def get_weather_history_grid(grid_cell_id: int, db: Session = Depends(get_db)):
    """Get the weather history of a grid cell."""
    data = get_observation_history_for_grid_cell(grid_cell_id, db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ID NOT FOUND")
    return data


# Assign weather for every single cell
@router.post("/assign_all")
async def assign_weather_all(
    max_workers: int = 12,
    skip_existing: bool = True,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    """Assign weather values to all cells."""
    all_cells = get_all_grid_cells(db)
    if not all_cells:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")

    result = assign_weather_for_cells(all_cells, db, max_workers, skip_existing, limit)
    return assignment_response(result, max_workers, skip_existing, limit)


# Assign weather for each cell in state
@router.post("/assign_state")
async def assign_weather_state(
    state: str,
    max_workers: int = 12,
    skip_existing: bool = True,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    """Assign weather values to cells in the selected state."""
    all_cells = get_state_grid_cells(state, db)

    result = assign_weather_for_cells(all_cells, db, max_workers, skip_existing, limit)
    return assignment_response(result, max_workers, skip_existing, limit, state=state)
