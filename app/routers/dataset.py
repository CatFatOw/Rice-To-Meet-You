"""File contains basic CRUD operations for the provided dataset tables"""
import csv
import io
import json
from datetime import date
from types import UnionType
from typing import Type, Union, get_args, get_origin

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from database import get_db
import models 
from schemas import dataset_schemas
from security import oauth2
from repository.dataset_repository import (
    bulk_post_data,
    delete_data,
    get_all_dataset,
    get_all_dataset_unscoped,
    get_specific_data,
    post_data,
    update_data,
)


router = APIRouter(prefix="/dataset", tags=["dataset"])


CATEGORY_TEXT_FIELDS = {
    "sub_category",
    "sub_category_2022",
    "top_category",
    "top_category_2022",
}


NULL_TEXT_VALUES = {"", "na", "n/a", "nan", "none", "null", "\\n", "\\N"}


def _normalize_csv_header(header: str | None) -> str:
    """Normalize incoming CSV headers to the schema field naming style."""
    if header is None:
        return ""
    return header.strip().replace(" ", "_").replace("-", "_").lower()


def _empty_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in NULL_TEXT_VALUES or stripped in NULL_TEXT_VALUES:
            return None
    return value


def _annotation_contains(annotation, expected_origin) -> bool:
    origin = get_origin(annotation)
    if origin is expected_origin:
        return True
    if origin in (Union, UnionType):
        return any(
            _annotation_contains(arg, expected_origin)
            for arg in get_args(annotation)
            if arg is not type(None)
        )
    return False


def _annotation_allows_none(annotation) -> bool:
    if annotation is type(None):
        return True
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(arg is type(None) for arg in get_args(annotation))
    return False


def _csv_reader(decoded: str):
    header = decoded.splitlines()[0] if decoded.splitlines() else ""
    delimiter_counts = {delimiter: header.count(delimiter) for delimiter in ("\t", ",", ";", "|")}
    delimiter, count = max(delimiter_counts.items(), key=lambda item: item[1])
    if count > 0:
        return csv.DictReader(io.StringIO(decoded), delimiter=delimiter)

    sample = decoded[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    return csv.DictReader(io.StringIO(decoded), dialect=dialect)


def _coerce_csv_value(field_name: str, value, create_schema: Type[BaseModel]):
    value = _empty_to_none(value)
    if value is None and field_name in CATEGORY_TEXT_FIELDS:
        return "Unknown"
    annotation = create_schema.model_fields[field_name].annotation
    if value is None and not _annotation_allows_none(annotation):
        if _annotation_contains(annotation, dict):
            return {}
        if _annotation_contains(annotation, list):
            return []
    if value is None:
        return None

    if _annotation_contains(annotation, date):
        return value.strip()[:10] if isinstance(value, str) else value
    if _annotation_contains(annotation, dict) or _annotation_contains(annotation, list):
        if not isinstance(value, str):
            return value
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be valid JSON") from exc
        if parsed_value is None and not _annotation_allows_none(annotation):
            if _annotation_contains(annotation, dict):
                return {}
            if _annotation_contains(annotation, list):
                return []
        return parsed_value

    return value.strip() if isinstance(value, str) else value


def _csv_payloads_from_upload(file_bytes: bytes, create_schema: Type[BaseModel]):
    decoded = file_bytes.decode("utf-8-sig")
    reader = _csv_reader(decoded)
    if not reader.fieldnames:
        raise ValueError("CSV file must include a header row.")

    schema_fields = set(create_schema.model_fields.keys())
    payloads = []
    errors = []

    for row_number, row in enumerate(reader, start=2):
        normalized_row = {
            _normalize_csv_header(header): value
            for header, value in row.items()
            if header is not None
        }
        values = {}
        for field_name in schema_fields:
            if field_name in normalized_row:
                try:
                    values[field_name] = _coerce_csv_value(field_name, normalized_row[field_name], create_schema)
                except ValueError as exc:
                    errors.append(f"row {row_number}: {exc}")

        try:
            payloads.append(create_schema(**values))
        except ValidationError as exc:
            errors.append(f"row {row_number}: {exc.errors()}")

    return payloads, errors


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


    # Get all datasets across all users
    @router.get(f"/{path}/all", response_model=list[response_schema])
    async def get_all_unscoped(db: Session = Depends(get_db)):
        data = get_all_dataset_unscoped(model, db)
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DATASET NOT FOUND")
        return data


    # Import a CSV into the dataset
    @router.post(f"/{path}/import_csv", response_model=dataset_schemas.DatasetCsvImportResponse)
    async def import_csv(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        curr_user: models.User = Depends(oauth2.get_current_user),
    ):
        lower_filename = (file.filename or "").lower()
        if not lower_filename.endswith((".csv", ".tsv", ".txt")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a .csv, .tsv, or tab-delimited .txt file.")

        try:
            payloads, errors = _csv_payloads_from_upload(await file.read(), create_schema)
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file must be UTF-8 encoded.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if errors:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors[:25])
        if not payloads:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file did not contain any rows.")

        inserted = bulk_post_data(payloads, model, db, curr_user)
        return {
            "dataset": path,
            "inserted_count": len(inserted),
            "errors": [],
        }


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
