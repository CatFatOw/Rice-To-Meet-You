from shapely import wkt
import hashlib
import csv
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from models.dataset_tables import CorePoiGeometry


CORE_POI_IMPORT_FIELDS = {
    "brands",
    "category_tags",
    "city",
    "closed_on",
    "domains",
    "enclosed",
    "geometry_type",
    "includes_parking_lot",
    "iso_country_code",
    "is_synthetic",
    "latitude",
    "location_name",
    "longitude",
    "market",
    "naics_code",
    "naics_code_2022",
    "opened_on",
    "open_hours",
    "parent_placekey",
    "phone_number",
    "placekey",
    "polygon_class",
    "polygon_wkt",
    "postal_code",
    "region",
    "safegraph_place_id",
    "store_id",
    "street_address",
    "sub_category",
    "sub_category_2022",
    "top_category",
    "top_category_2022",
    "tracking_closed_since",
    "website",
    "wkt_area_sq_meters",
}

JSON_FIELDS = {"brands", "category_tags", "domains", "open_hours"}
BOOL_FIELDS = {"enclosed", "includes_parking_lot", "is_synthetic"}
INT_FIELDS = {"naics_code", "naics_code_2022"}
FLOAT_FIELDS = {"latitude", "longitude", "wkt_area_sq_meters"}
DATE_FIELDS = {"closed_on", "opened_on", "tracking_closed_since"}
REQUIRED_FIELDS = {
    "city",
    "latitude",
    "location_name",
    "longitude",
    "polygon_wkt",
}

TEXT_DEFAULTS = {
    "geometry_type": "POLYGON",
    "iso_country_code": "US",
    "market": "Unknown",
    "placekey": "Unknown",
    "polygon_class": "Unknown",
    "postal_code": "Unknown",
    "region": "Unknown",
    "safegraph_place_id": "Unknown",
    "street_address": "Unknown",
    "sub_category": "Unknown",
    "sub_category_2022": "Unknown",
    "top_category": "Unknown",
    "top_category_2022": "Unknown",
}


def _normalize_header(header: str | None) -> str:
    return (header or "").strip().lower()


def _empty_to_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped != "" else None
    return value


def _parse_json_value(value):
    value = _empty_to_none(value)
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_bool(value):
    value = _empty_to_none(value)
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _parse_int(value):
    value = _empty_to_none(value)
    if value is None:
        return None
    return int(float(value))


def _parse_float(value):
    value = _empty_to_none(value)
    if value is None:
        return None
    return float(value)


def _parse_date(value):
    value = _empty_to_none(value)
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def _coerce_import_value(field: str, value):
    if field in JSON_FIELDS:
        return _parse_json_value(value)
    if field in BOOL_FIELDS:
        return _parse_bool(value)
    if field in INT_FIELDS:
        return _parse_int(value)
    if field in FLOAT_FIELDS:
        return _parse_float(value)
    if field in DATE_FIELDS:
        return _parse_date(value)
    return _empty_to_none(value)


def _rows_from_csv(file_bytes: bytes) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{_normalize_header(key): value for key, value in row.items()} for row in reader]


def _cell_text(cell: ET.Element, shared_strings: list[str], namespace: dict[str, str]):
    cell_type = cell.attrib.get("t")
    value = cell.find("x:v", namespace)
    if cell_type == "inlineStr":
        inline_text = cell.find("x:is/x:t", namespace)
        return inline_text.text if inline_text is not None else None
    if value is None:
        return None
    if cell_type == "s":
        idx = int(value.text or 0)
        return shared_strings[idx] if idx < len(shared_strings) else None
    return value.text


def _xlsx_column_index(cell_ref: str | None) -> int:
    if not cell_ref:
        return 0
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    total = 0
    for letter in letters:
        total = total * 26 + (ord(letter) - ord("A") + 1)
    return max(total - 1, 0)


def _xlsx_shared_strings(workbook: zipfile.ZipFile, namespace: dict[str, str]) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("x:si", namespace):
        text_parts = [node.text or "" for node in item.findall(".//x:t", namespace)]
        strings.append("".join(text_parts))
    return strings


def _rows_from_xlsx(file_bytes: bytes) -> list[dict]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as workbook:
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in workbook.namelist():
            raise ValueError("Could not find the first worksheet in the uploaded workbook.")
        shared_strings = _xlsx_shared_strings(workbook, namespace)
        root = ET.fromstring(workbook.read(sheet_path))
        raw_rows = []
        for row in root.findall(".//x:sheetData/x:row", namespace):
            values = []
            for cell in row.findall("x:c", namespace):
                column_index = _xlsx_column_index(cell.attrib.get("r"))
                while len(values) <= column_index:
                    values.append(None)
                values[column_index] = _cell_text(cell, shared_strings, namespace)
            raw_rows.append(values)

    if not raw_rows:
        return []
    headers = [_normalize_header(header) for header in raw_rows[0]]
    return [
        {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
        for row in raw_rows[1:]
    ]


def rows_from_core_poi_upload(filename: str, file_bytes: bytes) -> list[dict]:
    lower_name = filename.lower()
    if lower_name.endswith(".csv"):
        return _rows_from_csv(file_bytes)
    if lower_name.endswith(".xlsx"):
        return _rows_from_xlsx(file_bytes)
    raise ValueError("Upload a .csv or .xlsx file.")


def core_poi_from_import_row(row: dict, row_number: int) -> CorePoiGeometry:
    values = {}
    for field in CORE_POI_IMPORT_FIELDS:
        values[field] = _coerce_import_value(field, row.get(field))

    if values.get("market") is None:
        values["market"] = values.get("city") or "Unknown"
    for field, default in TEXT_DEFAULTS.items():
        if values.get(field) is None:
            values[field] = default
    for field in BOOL_FIELDS:
        if values.get(field) is None:
            values[field] = False
    if values.get("wkt_area_sq_meters") is None:
        values["wkt_area_sq_meters"] = 0.0

    missing = [
        field
        for field in REQUIRED_FIELDS
        if values.get(field) is None
    ]
    if missing:
        raise ValueError(f"row {row_number}: missing required fields {', '.join(sorted(missing))}")

    try:
        wkt.loads(values["polygon_wkt"])
    except Exception as exc:
        raise ValueError(f"row {row_number}: invalid polygon_wkt") from exc

    return CorePoiGeometry(**values)


def core_pois_from_upload(filename: str, file_bytes: bytes):
    rows = rows_from_core_poi_upload(filename, file_bytes)
    pois = []
    errors = []
    for index, row in enumerate(rows, start=2):
        try:
            pois.append(core_poi_from_import_row(row, index))
        except Exception as exc:
            errors.append(str(exc))
    return pois, len(rows), errors


def convert_wkt_to_lon_lat(polygon_wkt: str) -> list[list[float]]:
    """Function acceptns a string of wkt format coordinates and converts it into 
    lat,lon points that backend/frontend can use to render the polygons"""

    geometry = wkt.loads(polygon_wkt)

    # If single polygon
    if geometry.geom_type == "Polygon":
        return [[lon, lat] for lon, lat in geometry.exterior.coords]
    # If multiple disjoint polygons, return the coords of largest polygon 
    elif geometry.geom_type == "MultiPolygon":
        largest = max(geometry.geoms, key=lambda geom: geom.area)
        return [[lon, lat] for lon, lat in largest.exterior.coords]
    return []


def poi_type_to_color(poi_type: str) -> list[int]:
    if not poi_type:
        poi_type = "Unknown"

    hash_value = hashlib.md5(poi_type.encode()).hexdigest()

    r = int(hash_value[0:2], 16)
    g = int(hash_value[2:4], 16)
    b = int(hash_value[4:6], 16)

    # brighten colors for frontend visibility
    r = int((r + 255) / 2)
    g = int((g + 255) / 2)
    b = int((b + 255) / 2)

    return [r, g, b, 160]


def poi_click_statistics(poi) -> dict:
    """Build frontend details for a clicked core POI polygon."""
    return {
        "address": poi.street_address,
        "city": poi.city,
        "region": poi.region,
        "postal_code": poi.postal_code,
        "top_category": poi.top_category,
        "sub_category": poi.sub_category,
        "naics_code": poi.naics_code,
        "includes_parking_lot": poi.includes_parking_lot,
        "enclosed": poi.enclosed,
        "wkt_area_sq_meters": poi.wkt_area_sq_meters,
        "opened_on": poi.opened_on.isoformat() if poi.opened_on else None,
        "closed_on": poi.closed_on.isoformat() if poi.closed_on else None,
        "website": poi.website,
        "phone_number": poi.phone_number,
    }


def poi_to_frontend_polygon(poi):
    category = poi.sub_category or poi.top_category
    return {
        "id": f"poi-{poi.id}",
        "poi_id": poi.id,
        "name": poi.location_name,
        "cityName": poi.city,
        "stateName": poi.region,
        "category": category,
        "color": poi_type_to_color(category),
        "polygon": convert_wkt_to_lon_lat(poi.polygon_wkt),
        "properties": {
            "placekey": poi.placekey,
            "safegraph_place_id": poi.safegraph_place_id,
            "street_address": poi.street_address,
            "region": poi.region,
            "postal_code": poi.postal_code,
            "top_category": poi.top_category,
            "sub_category": poi.sub_category,
            "naics_code": poi.naics_code,
            "brands": poi.brands,
            "statistics": poi_click_statistics(poi),
        },
    }
