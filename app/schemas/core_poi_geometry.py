"""Input schema for creating a row in ``core_poi_geometry``.

Three field groups:

* **Core**      - required from the caller.
* **Optional**  - accepted, default ``None``.
* **Defaults**  - have a server-side meaning; overridable but rarely supplied.

Pairs with ``CorePoiGeometryRepository.create``::

    poi = CorePOICreate(
        polygon_wkt="POLYGON((-96.80 32.78, ...))",
        city="Dallas",
        location_name="Klyde Warren Park",
        region="TX",
        includes_parking_lot=False,
        latitude=32.7893,
        longitude=-96.8016,
        market="dallas",
        color="#22c55e",
    )
    repo.create(poi.to_row())
    db.commit()
"""

from __future__ import annotations

import json
import re
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = ["GeometryType", "PolygonClass", "MarketCode", "CorePOICreate"]


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class GeometryType(str, Enum):
    POLYGON = "POLYGON"
    MULTIPOLYGON = "MULTIPOLYGON"
    POINT = "POINT"


class PolygonClass(str, Enum):
    OWNED_POLYGON = "OWNED_POLYGON"
    SHARED_POLYGON = "SHARED_POLYGON"


class MarketCode(str, Enum):
    DALLAS = "dallas"
    KANSAS_CITY = "kansas_city"
    HOUSTON = "houston"
    MIAMI = "miami"
    LOS_ANGELES = "los_angeles"
    SAN_FRANCISCO = "san_francisco"
    NEW_YORK_NJ = "new_york_nj"
    PHILADELPHIA = "philadelphia"
    BOSTON = "boston"
    ATLANTA = "atlanta"
    SEATTLE = "seattle"


_WKT_PREFIXES = ("POLYGON", "MULTIPOLYGON")
_PLACEKEY_RE = re.compile(r"^(?:[2-9a-km-zA-KM-Z]{3}-[2-9a-km-zA-KM-Z]{3}@)?[2-9a-km-zA-Z]{3}-[2-9a-km-zA-Z]{3}-[2-9a-km-zA-Z]{3}$")


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


class CorePOICreate(BaseModel):
    """Validated payload for inserting one POI."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
        validate_assignment=True,
    )

    # ------------------------------------------------------------------ #
    # Core inputs (required)
    # ------------------------------------------------------------------ #

    polygon_wkt: str = Field(
        ..., min_length=10, description="POLYGON or MULTIPOLYGON WKT string."
    )
    city: str = Field(..., min_length=1, max_length=128)
    location_name: str = Field(..., min_length=1, max_length=512)
    region: str = Field(
        ..., min_length=2, max_length=2, description="Two-letter state/region code."
    )
    includes_parking_lot: bool
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    market: MarketCode
    market_code: Optional[MarketCode] = None
    color: str = Field(..., min_length=1, description="Color hex or rgb string.")

    # ------------------------------------------------------------------ #
    # Optional inputs
    # ------------------------------------------------------------------ #

    brands: Optional[List[str]] = None
    category_tags: Optional[List[str]] = None
    domains: Optional[List[str]] = None
    enclosed: Optional[bool] = None
    naics_code: Optional[int] = Field(default=None, ge=100000, le=999999)
    naics_code_2022: Optional[int] = Field(default=None, ge=100000, le=999999)
    opened_on: Optional[date] = None
    open_hours: Optional[Dict[str, List[List[str]]]] = Field(
        default=None,
        description='e.g. {"Mon": [["9:00", "17:00"]], "Tue": [["9:00", "17:00"]]}',
    )
    phone_number: Optional[str] = Field(default=None, max_length=32)
    postal_code: Optional[str] = Field(default=None, max_length=16)
    street_address: Optional[str] = Field(default=None, max_length=512)
    sub_category: Optional[str] = Field(default=None, max_length=256)
    sub_category_2022: Optional[str] = Field(default=None, max_length=256)
    top_category: Optional[str] = Field(default=None, max_length=256)
    top_category_2022: Optional[str] = Field(default=None, max_length=256)
    website: Optional[str] = Field(default=None, max_length=512)
    wkt_area_sq_meters: Optional[float] = Field(default=None, ge=0.0)

    # ------------------------------------------------------------------ #
    # Defaulted fields
    # ------------------------------------------------------------------ #

    geometry_type: GeometryType = GeometryType.POLYGON
    iso_country_code: str = Field(default="US", min_length=2, max_length=2)
    is_synthetic: bool = False
    parent_placekey: Optional[str] = None
    placekey: Optional[str] = None
    polygon_class: PolygonClass = PolygonClass.OWNED_POLYGON
    safegraph_place_id: Optional[str] = None
    tracking_closed_since: Optional[date] = None
    user_id: Optional[str] = None
    provided: Optional[bool] = False

    # ------------------------------------------------------------------ #
    # Field validators
    # ------------------------------------------------------------------ #

    @field_validator("polygon_wkt")
    @classmethod
    def _check_wkt(cls, value: str) -> str:
        head = value.lstrip().upper()
        if not head.startswith(_WKT_PREFIXES):
            raise ValueError(
                f"polygon_wkt must start with one of {_WKT_PREFIXES}, got: {value[:24]!r}"
            )
        if value.count("(") != value.count(")"):
            raise ValueError("polygon_wkt has unbalanced parentheses.")
        return value.strip()

    @field_validator("region", "iso_country_code")
    @classmethod
    def _upper_code(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError(f"Expected letters only, got {value!r}.")
        return value.upper()

    @field_validator("market", "market_code", mode="before")
    @classmethod
    def _normalize_market(cls, value: Any) -> Any:
        """Accept 'Dallas', 'DALLAS', or 'new york nj'."""
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_").replace("-", "_")
        return value

    @field_validator("brands", "category_tags", "domains", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> Any:
        """Accept a comma-separated string or a JSON array for list fields."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return [part.strip() for part in text.split(",") if part.strip()]
        return value

    @field_validator("brands", "category_tags", "domains")
    @classmethod
    def _clean_list(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        """Drop blanks and duplicates while preserving order."""
        if value is None:
            return None
        seen, cleaned = set(), []
        for item in value:
            item = str(item).strip()
            if item and item not in seen:
                seen.add(item)
                cleaned.append(item)
        return cleaned or None

    @field_validator("open_hours", mode="before")
    @classmethod
    def _parse_open_hours(cls, value: Any) -> Any:
        """SafeGraph ships open_hours as a JSON string; accept either form."""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                raise ValueError("open_hours must be valid JSON.") from None
        return value

    @field_validator("phone_number")
    @classmethod
    def _normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        """Keep digits and a leading '+'; reject anything implausible."""
        if value is None:
            return None
        cleaned = re.sub(r"[^\d+]", "", value)
        digits = cleaned.lstrip("+")
        if not 7 <= len(digits) <= 15:
            raise ValueError(f"phone_number has {len(digits)} digits; expected 7-15.")
        return cleaned

    @field_validator("website")
    @classmethod
    def _normalize_website(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value if value.startswith(("http://", "https://")) else f"https://{value}"

    @field_validator("placekey", "parent_placekey")
    @classmethod
    def _check_placekey(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not _PLACEKEY_RE.match(value):
            raise ValueError(f"Malformed placekey: {value!r}")
        return value

    # ------------------------------------------------------------------ #
    # Cross-field validation
    # ------------------------------------------------------------------ #

    @model_validator(mode="after")
    def _check_consistency(self) -> "CorePOICreate":
        if self.market_code is None and self.market is not None:
            self.market_code = self.market
        elif self.market is None and self.market_code is not None:
            self.market = self.market_code

        head = self.polygon_wkt.lstrip().upper()
        declared = str(self.geometry_type)
        if declared in ("POLYGON", "MULTIPOLYGON") and not head.startswith(declared):
            raise ValueError(
                f"geometry_type is {declared} but polygon_wkt starts with "
                f"{head.split('(')[0].strip()!r}."
            )
        if self.tracking_closed_since and self.opened_on:
            if self.tracking_closed_since < self.opened_on:
                raise ValueError("tracking_closed_since precedes opened_on.")
        if self.parent_placekey and self.parent_placekey == self.placekey:
            raise ValueError("parent_placekey must differ from placekey.")
        return self

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #

    def to_row(self) -> Dict[str, Any]:
        """Column dict for ``CorePoiGeometryRepository.create``.

        Nulls are kept so defaulted columns are written explicitly.
        """
        return self.model_dump(mode="json", exclude_none=False)