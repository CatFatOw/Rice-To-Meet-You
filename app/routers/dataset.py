"""File contains basic CRUD operations for the provided dataset tables"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from database import get_db
import models 
from schemas import dataset_schemas
from typing import Type
from pydantic import BaseModel
from security import oauth2
from repository.dataset_repository import (
    delete_data,
    get_all_dataset,
    get_specific_data,
    post_data,
    update_data,
)


router = APIRouter(prefix="/dataset", tags=["dataset"])


def create_crud_routes(
    router: APIRouter,
    path: str,
    model,
    create_schema: Type[BaseModel],
    response_schema: Type[BaseModel],
):
    """Main function for creating the CRUD applications for all 6 tables"""


    # Get all datasets
    @router.get(f"/{path}", response_model=list[response_schema])
    async def get_all(
        db:Session = Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        data = get_all_dataset(model, db, curr_user)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DATASET NOT FOUND")
        return data


    # Get specific database id 
    @router.get(f"/{path}/{{id}}", response_model=response_schema)
    async def get_by_id(
        id:int,
        db:Session = Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        """Function gets specific row by row id"""
        data = get_specific_data(id, model, db, curr_user)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
        return data


    # Posting row in the dataset 
    @router.post(f"/{path}", response_model=response_schema)
    async def create_row(
        payload:create_schema,
        db:Session=Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        """Function adds new data into the table"""
        return post_data(payload, model, db, curr_user)


    # Updating the DB
    @router.put(f"/{path}/{{id}}", response_model=response_schema)
    async def update_row(
        id:int,
        payload:create_schema,
        db:Session=Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        """Function updates a row in the dataset"""
        data = update_data(payload, id, model, db, curr_user)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
        return data
    

    # Delete a row of the DB
    @router.delete(f"/{path}/{{id}}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_row(
        id:int,
        db:Session = Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        """Function deletes a row on the dataset"""
        deleted = delete_data(id, model, db, curr_user)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NOT FOUND")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    

# Create the routes for the core_poi_table
create_crud_routes(router, "core_poi_geometry_table", models.CorePoiGeometry, dataset_schemas.CorePoiGeometryCreate, dataset_schemas.CorePoiGeometryResponse)
# Create the routes for the dailyspendbrandstate table 
create_crud_routes(router, "daily_spend_brand_state", models.DailySpendBrandState, dataset_schemas.DailySpendBrandStateCreate, dataset_schemas.DailySpendBrandStateResponse)
# Create the routes for daily weather 
create_crud_routes(router, "daily_weather", models.DailyWeatherRice, dataset_schemas.DailyWeatherRiceCreate, dataset_schemas.DailyWeatherRiceResponse)
# Create the routes for spending patterns 
create_crud_routes(router, "spending_patterns", models.SpendPatternsRice, dataset_schemas.SpendPatternsRiceCreate, dataset_schemas.SpendPatternsRiceResponse)
# Create the route for store visists 
create_crud_routes(router, "store_visits", models.StoreVisits, dataset_schemas.StoreVisitsCreate, dataset_schemas.StoreVisitsResponse)
# create the route for urban heat index
create_crud_routes(router, "urban_heat_index", models.UrbanHeatIndex, dataset_schemas.UrbanHeatIndexCreate, dataset_schemas.UrbanHeatIndexResponse)
