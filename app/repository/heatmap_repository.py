"""Repository for building heatmap data points from weather + urban heat index data.

Mirrors the TypeScript contract:

    export interface HeatmapPointsByDate {
      [date: string]: HeatmapMetricValue[];
    }

    export interface HeatmapMetricValue {
      location_coordinates: [number, number]; // [lon, lat]
      individual_metrics?: Record<string, string>;
    }
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

# --- Type aliases matching the TS interfaces -------------------------------

HeatmapMetricValue = Dict[str, Any]   # {"location_coordinates": [lon, lat],
                                      #  "individual_metrics": {str: str}}
HeatmapPointsByDate = Dict[str, List[HeatmapMetricValue]]

DateLike = Union[str, dt.date, dt.datetime]


class HeatmapRepository:
    """Reads market weather + urban heat index rows and shapes them for the map."""

    SUPPORTED_MARKET_CODES: Tuple[str, ...] = (
        "dallas",
        "kansas_city",
        "houston",
        "miami",
        "los_angeles",
        "san_francisco",
        "new_york_nj",
        "philadelphia",
        "boston",
        "atlanta",
        "seattle",
    )

    WEATHER_TABLE = "market_daily_weather"
    HEAT_INDEX_TABLE = "urban_heat_index_updated"

    # Structural columns (join keys, coordinates, bookkeeping) never emitted
    # inside `individual_metrics`.
    EXCLUDED_METRIC_COLUMNS = {
        "id",
        "market_code",
        "weather_date",
        "longitude",
        "latitude",
        "lon",
        "lat",
        "lng",
        "long",
        "created_at",
        "updated_at",
        "inserted_at",
    }

    # Candidate coordinate column names, in priority order.
    LONGITUDE_CANDIDATES = ("longitude", "lon", "lng", "long")
    LATITUDE_CANDIDATES = ("latitude", "lat")

    # Suffix appended to a numeric metric based on its column name. First match wins.
    UNIT_HINTS: Sequence[Tuple[str, str]] = (
        ("humidity", "%"),
        ("cloud_cover", "%"),
        ("precip", " in"),
        ("rainfall", " in"),
        ("snow", " in"),
        ("wind_speed", " mph"),
        ("wind_gust", " mph"),
        ("pressure", " hPa"),
        ("visibility", " mi"),
        ("uv_index", ""),
        ("heat_index", " / 100"),
        ("_score", " / 100"),
        ("_index", " / 100"),
        ("temp", "\u00b0F"),
        ("feels_like", "\u00b0F"),
        ("dew_point", "\u00b0F"),
    )

    def __init__(self, session: Session) -> None:
        self.session = session
        self._metadata = MetaData()
        self._weather_table: Optional[Table] = None
        self._heat_index_table: Optional[Table] = None

    # -- public API ---------------------------------------------------------

    def getDataPointsForCityAndDate(
        self,
        weather_date: DateLike,
        market_code: Optional[Union[str, Iterable[str]]] = None,
    ) -> HeatmapPointsByDate:
        """Return heatmap points for the given date, keyed by date string.

        Args:
            weather_date: the day to pull, as a `date`/`datetime` or ISO string.
            market_code: a single market code or an iterable of them. Defaults to
                all supported markets.

        Returns:
            HeatmapPointsByDate, e.g.
            {"2026-08-10": [{"location_coordinates": [...], "individual_metrics": {...}}]}
        """
        target_date = self._coerce_date(weather_date)
        markets = self._resolve_markets(market_code)
        if not markets:
            return {}

        weather = self._get_table(self.WEATHER_TABLE)
        heat_index = self._get_table(self.HEAT_INDEX_TABLE)

        lon_col = self._resolve_column(heat_index, self.LONGITUDE_CANDIDATES)
        lat_col = self._resolve_column(heat_index, self.LATITUDE_CANDIDATES)

        # Prefix every column so identically-named columns on the two tables
        # (market_code, timestamps, ...) don't collide in the result mapping.
        selected = [c.label("w__" + c.name) for c in weather.columns]
        selected += [c.label("h__" + c.name) for c in heat_index.columns]

        stmt = (
            select(*selected)
            .select_from(
                weather.join(
                    heat_index,
                    weather.c.market_code == heat_index.c.market_code,
                )
            )
            .where(weather.c.weather_date == target_date)
            .where(weather.c.market_code.in_(markets))
        )

        results: HeatmapPointsByDate = {}
        for row in self.session.execute(stmt).mappings():
            longitude = self._to_float(row.get("h__" + lon_col))
            latitude = self._to_float(row.get("h__" + lat_col))
            if longitude is None or latitude is None:
                continue  # a point without coordinates can't be placed on the map

            date_key = self._to_date_key(row.get("w__weather_date"), target_date)
            point: HeatmapMetricValue = {
                "location_coordinates": [longitude, latitude],
                "individual_metrics": self._build_metrics(row),
            }
            results.setdefault(date_key, []).append(point)

        return results

    def getDataPointsForCityDateMetric(
        self,
        weather_date: DateLike,
        metric: str,
        market_code: Optional[Union[str, Iterable[str]]] = None,
        additional_metrics: Optional[Iterable[str]] = None,
    ) -> HeatmapPointsByDate:
        """Return heatmap points weighted by a single metric, keyed by date string.

        Matches the TS `HeatmapPointsByDate` / `HeatmapMetricValue` contract:
        `value` carries the chosen metric as a number, and `individual_metrics`
        carries the accompanying metrics as formatted strings.

        Args:
            weather_date: the day to pull, as a `date`/`datetime` or ISO string.
            metric: column name to weight by, on either table.
            market_code: a single market code or an iterable of them. Defaults to
                all supported markets.
            additional_metrics: column names to include in `individual_metrics`.
                `None` (the default) includes every other metric column; an empty
                list includes none. `metric` itself is always excluded, since it
                is reported as `value`.

        Raises:
            ValueError: if `metric` is not a readable column on either table.
        """
        target_date = self._coerce_date(weather_date)
        markets = self._resolve_markets(market_code)
        if not markets:
            return {}

        weather = self._get_table(self.WEATHER_TABLE)
        heat_index = self._get_table(self.HEAT_INDEX_TABLE)

        lon_col = self._resolve_column(heat_index, self.LONGITUDE_CANDIDATES)
        lat_col = self._resolve_column(heat_index, self.LATITUDE_CANDIDATES)
        metric_column, metric_prefix = self._resolve_metric_column(
            metric, weather, heat_index
        )
        metric_key = metric_column.name
        metric_label = metric_prefix + metric_key

        allowed: Optional[set] = None
        if additional_metrics is not None:
            allowed = {str(m).strip() for m in additional_metrics}
            allowed.discard(metric_key)  # it's reported as `value`

        selected = [c.label("w__" + c.name) for c in weather.columns]
        selected += [c.label("h__" + c.name) for c in heat_index.columns]

        stmt = (
            select(*selected)
            .select_from(
                weather.join(
                    heat_index,
                    weather.c.market_code == heat_index.c.market_code,
                )
            )
            .where(weather.c.weather_date == target_date)
            .where(weather.c.market_code.in_(markets))
        )

        results: HeatmapPointsByDate = {}
        for row in self.session.execute(stmt).mappings():
            longitude = self._to_float(row.get("h__" + lon_col))
            latitude = self._to_float(row.get("h__" + lat_col))
            if longitude is None or latitude is None:
                continue  # a point without coordinates can't be placed on the map

            value = self._to_weight(row.get(metric_label))
            if value is None:
                continue  # nothing to weight this point by

            metrics = self._build_metrics(row, allowed=allowed)
            metrics.pop(metric_key, None)  # the chosen metric lives in `value`

            date_key = self._to_date_key(row.get("w__weather_date"), target_date)
            point: HeatmapMetricValue = {
                "value": value,
                "location_coordinates": [longitude, latitude],
                "individual_metrics": metrics,
            }
            results.setdefault(date_key, []).append(point)

        return results

    # -- schema helpers -----------------------------------------------------
    def _build_metrics(
        self, row: Any, allowed: Optional[set] = None
    ) -> Dict[str, str]:
        """Everything that isn't a join key or a coordinate, stringified with units.

        `allowed`, when given, restricts the output to that set of column names.
        """
        metrics: Dict[str, str] = {}
        for prefixed_key, value in row.items():
            column = prefixed_key.split("__", 1)[1]
            if column in self.EXCLUDED_METRIC_COLUMNS or value is None:
                continue
            if allowed is not None and column not in allowed:
                continue
            metrics[column] = self._format_value(column, value)
        return metrics

    @staticmethod
    def _to_weight(value: Any) -> Optional[float]:
        """Coerce a metric to a number for heatmap weighting. Bools -> 1.0/0.0."""
        if value is None:
            return None
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return None  # e.g. a text band like "favorable"

    def _resolve_metric_column(
        self, metric: str, weather: Table, heat_index: Table
    ) -> Tuple[Any, str]:
        """Find `metric` on either table. Returns (column, label_prefix)."""
        name = str(metric).strip()
        if name in self.EXCLUDED_METRIC_COLUMNS:
            raise ValueError(
                "'%s' is a structural column and is not available as a metric."
                % name
            )
        # Weather wins a name collision, matching _build_metrics' iteration order.
        for table, prefix in ((weather, "w__"), (heat_index, "h__")):
            if name in table.columns:
                return table.columns[name], prefix
        available = sorted(
            c.name
            for t in (weather, heat_index)
            for c in t.columns
            if c.name not in self.EXCLUDED_METRIC_COLUMNS
        )
        raise ValueError(
            "Unknown metric '%s'. Available metrics: %s" % (name, available)
        )

    def _get_table(self, name: str) -> Table:
        cached = (
            self._weather_table
            if name == self.WEATHER_TABLE
            else self._heat_index_table
        )
        if cached is not None:
            return cached

        table = Table(name, self._metadata, autoload_with=self.session.get_bind())
        if name == self.WEATHER_TABLE:
            self._weather_table = table
        else:
            self._heat_index_table = table
        return table

    @staticmethod
    def _resolve_column(table: Table, candidates: Sequence[str]) -> str:
        for candidate in candidates:
            if candidate in table.columns:
                return candidate
        raise ValueError(
            "None of %s found on table '%s'. Available columns: %s"
            % (list(candidates), table.name, [c.name for c in table.columns])
        )

    def _resolve_markets(
        self, market_code: Optional[Union[str, Iterable[str]]]
    ) -> List[str]:
        if market_code is None:
            return list(self.SUPPORTED_MARKET_CODES)
        requested = [market_code] if isinstance(market_code, str) else list(market_code)
        return [
            m
            for m in (str(c).strip().lower() for c in requested)
            if m in self.SUPPORTED_MARKET_CODES
        ]

    def _format_value(self, column: str, value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (dt.date, dt.datetime)):
            return value.isoformat()
        if isinstance(value, (int, float, Decimal)):
            number = float(value)
            rendered = "%.0f" % number if number.is_integer() else "%.1f" % number
            return rendered + self._unit_for(column)
        return str(value)

    def _unit_for(self, column: str) -> str:
        lowered = column.lower()
        for fragment, unit in self.UNIT_HINTS:
            if fragment in lowered:
                return unit
        return ""

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_date(value: DateLike) -> dt.date:
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        return dt.date.fromisoformat(str(value).strip()[:10])

    @staticmethod
    def _to_date_key(value: Any, fallback: dt.date) -> str:
        if isinstance(value, dt.datetime):
            return value.date().isoformat()
        if isinstance(value, dt.date):
            return value.isoformat()
        if value:
            return str(value)[:10]
        return fallback.isoformat()