"""Service helpers for prediction-model data routes."""

import csv
import io
from typing import Type

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from repository.prediction_model_repository import bulk_create_heat_data, bulk_create_visitor_data
from schemas.prediction_model_schemas import HeatDataMLCreate, VisitorDataMLCreate


class PredictionModelCsvError(ValueError):
    """Raised when a prediction-model CSV upload cannot be processed."""


CSV_FIELD_ALIASES = {
    "lat": "latitude",
    "lng": "longitude",
    "lon": "longitude",
    "temp": "avg_temp_c",
    "temperature": "avg_temp_c",
    "temperature_c": "avg_temp_c",
    "average_temperature_c": "avg_temp_c",
    "avg_temperature_c": "avg_temp_c",
    "humidity": "relative_humidity",
    "average_relative_humidity": "relative_humidity",
    "wind_speed": "wind_speed_knots",
    "average_wind_speed_knots": "wind_speed_knots",
    "uhi": "urban_heat_idx",
    "urban_heat_index": "urban_heat_idx",
    "heat_index": "urban_heat_idx",
    "date_time": "date",
    "timestamp": "date",
    "datetime": "date",
    "passed_heat_threshold": "passed_threshold",
}


def normalize_csv_header(header: str | None) -> str:
    normalized = (header or "").strip().lower().replace(" ", "_").replace("-", "_")
    return CSV_FIELD_ALIASES.get(normalized, normalized)


def csv_reader(decoded: str):
    sample = decoded[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    return csv.DictReader(io.StringIO(decoded), dialect=dialect)


def coerce_csv_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        if stripped.lower() in {"true", "false"}:
            return stripped.lower() == "true"
        return stripped
    return value


DEFAULT_IMPORT_ROW_LIMIT = 100


def csv_payloads_from_upload(
    file_bytes: bytes,
    create_schema: Type[BaseModel],
    row_limit: int = DEFAULT_IMPORT_ROW_LIMIT,
):
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PredictionModelCsvError(f"Could not decode CSV as UTF-8: {exc}") from exc

    reader = csv_reader(decoded)
    if not reader.fieldnames:
        raise PredictionModelCsvError("CSV file has no header row.")

    schema_fields = set(create_schema.model_fields)
    payloads = []
    errors = []

    for index, row in enumerate(reader, start=1):
        if index > row_limit:
            errors.append(f"row limit reached: only the first {row_limit} data rows were processed")
            break
        row_number = index + 1
        normalized_row = {
            normalize_csv_header(header): coerce_csv_value(value)
            for header, value in row.items()
            if normalize_csv_header(header)
        }
        values = {
            field_name: normalized_row[field_name]
            for field_name in schema_fields
            if field_name in normalized_row and normalized_row[field_name] is not None
        }
        try:
            payloads.append(create_schema.model_validate(values))
        except ValidationError as exc:
            errors.append(f"row {row_number}: {exc.errors()}")

    return payloads, errors


def validate_csv_filename(filename: str | None):
    lower_filename = (filename or "").lower()
    if not lower_filename.endswith((".csv", ".tsv", ".txt")):
        raise PredictionModelCsvError("Upload a .csv, .tsv, or tab-delimited .txt file.")


def import_heat_csv_records(
    filename: str | None,
    file_bytes: bytes,
    db: Session,
    row_limit: int = DEFAULT_IMPORT_ROW_LIMIT,
) -> dict:
    validate_csv_filename(filename)
    payloads, errors = csv_payloads_from_upload(file_bytes, HeatDataMLCreate, row_limit=row_limit)
    if not payloads:
        raise PredictionModelCsvError({"message": "No valid rows found in CSV.", "errors": errors})

    try:
        inserted = bulk_create_heat_data(payloads, db)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PredictionModelCsvError(f"Could not insert heat CSV rows: {exc}") from exc
    return {
        "filename": filename or "upload",
        "imported_count": len(inserted),
        "error_count": len(errors),
        "errors": errors[:25],
    }


def import_visitor_csv_records(
    filename: str | None,
    file_bytes: bytes,
    db: Session,
    row_limit: int = DEFAULT_IMPORT_ROW_LIMIT,
) -> dict:
    validate_csv_filename(filename)
    payloads, errors = csv_payloads_from_upload(file_bytes, VisitorDataMLCreate, row_limit=row_limit)
    if not payloads:
        raise PredictionModelCsvError({"message": "No valid rows found in CSV.", "errors": errors})

    try:
        inserted = bulk_create_visitor_data(payloads, db)
    except SQLAlchemyError as exc:
        db.rollback()
        raise PredictionModelCsvError(f"Could not insert visitor CSV rows: {exc}") from exc
    return {
        "filename": filename or "upload",
        "imported_count": len(inserted),
        "error_count": len(errors),
        "errors": errors[:25],
    }
