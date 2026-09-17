"""``repository/heatmap_repository.py`` — the readings behind every heatmap.

The frontend reaches this class through three heatmap routes and both surface
routes:

* ``getDataPointsForCityDateMetric`` — map.ts getHeatmapPointsByCityDateMetric,
  and every non-local-temperature surface
* ``getLocalTemperatureByCityDate``  — map.ts getLocalTemperature{C,F}ByCityDate,
  and the local_temperature_* surfaces
* ``get_simulated_points_by_date``   — simulation.ts getSimulatedPointsByDate

The repository reflects the two tables named by ``HeatmapRepository.WEATHER_TABLE``
and ``HeatmapRepository.HEAT_INDEX_TABLE`` and caches them on the class. Tests run
it against an in-memory SQLite mirror of those two tables, with every class-level
cache reset per test, so both the preloaded path and the lazy database fallback
are exercised for real.

``get_simulated_points_by_date`` is tested as glue: the intervention repository
and ``run_diminishing_return_simulation`` are replaced with recorders, so the
assertions are about what was fetched, how it was grouped and what was handed
on. The simulation physics belongs to ``services/simulation_services.py``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from repository import heatmap_repository
from repository.heatmap_repository import NAN, HeatBlock, HeatmapRepository
from repository.urban_internvetion_repository import UrbanInterventionRecord
from services import simulation_services

DATE = dt.date(2026, 7, 15)
DATE_KEY = "2026-07-15"
NEXT_DATE = dt.date(2026, 7, 16)

# Houston's heat-index points, in insertion order: (lon, lat, uhi, canopy, land_cover).
HOUSTON_A = (-95.40, 29.70, 1.0, 12.0, "urban")
HOUSTON_B = (-95.30, 29.80, 11.0, None, "suburban")
HOUSTON_C = (-95.35, 29.75, None, 40.0, None)  # no UHI reading
DALLAS_A = (-96.80, 32.78, 5.0, 20.0, "urban")


def coordinates(point):
    return [point[0], point[1]]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def fresh_class_cache(monkeypatch):
    """Reset every class-level cache, and put it back afterwards.

    Reflected tables and row caches live on ``HeatmapRepository`` itself and
    are shared process-wide, so without this a test would read whatever the
    previous one loaded.
    """
    for name, value in {
        "_metadata": MetaData(),
        "_weather_table": None,
        "_heat_index_table": None,
        "_heat_partitioned": False,
        "_heat_cache": {},
        "_heat_metric_names": (),
        "_weather_cache": {},
        "_weather_index": {},
        "_heat_loaded": False,
        "_weather_loaded": False,
    }.items():
        monkeypatch.setattr(HeatmapRepository, name, value)


def build_tables(partitioned: bool = False):
    """SQLite mirror of the two reflected tables.

    The table *names* are read off the repository rather than spelled out here:
    it reflects by name, so a mirror with its own copy of the name silently
    stops being reflected the day the real table is renamed, and every test in
    this module fails with NoSuchTableError instead of pointing at the rename.

    The *columns* are ours, chosen to cover each shape the repository treats
    differently: numeric weather columns, a text and a boolean weather column,
    and a heat table with a UHI column, a nullable numeric column and a text
    column. ``partitioned`` adds ``weather_date`` to the heat table, which
    switches the cache from one block per market to one per market per date.
    """
    metadata = MetaData()
    weather = Table(
        HeatmapRepository.WEATHER_TABLE,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("market_code", Text),
        Column("weather_date", Date),
        Column("average_temperature_c", Float),
        Column("average_temperature_f", Float),
        Column("average_relative_humidity_pct", Float),
        Column("major_event_weather_readiness_band", Text),
        Column("heat_stress_flag", Boolean),
    )
    heat_columns = [
        Column("id", Integer, primary_key=True),
        Column("market_code", Text),
        Column("longitude", Float),
        Column("latitude", Float),
        Column("uhi", Float),
        Column("tree_canopy", Float),
        Column("land_cover", Text),
    ]
    if partitioned:
        heat_columns.insert(2, Column("weather_date", Date))
    heat = Table(HeatmapRepository.HEAT_INDEX_TABLE, metadata, *heat_columns)
    return metadata, weather, heat


class HeatmapDatabase:
    """An engine holding the mirror tables, with helpers to fill them."""

    def __init__(self, partitioned: bool = False):
        self.metadata, self.weather, self.heat = build_tables(partitioned)
        # StaticPool: the repository opens its own connections from the engine,
        # and each fresh connection to a plain :memory: URL is an empty database.
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        self.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def add_weather(self, market_code="houston", weather_date=DATE, **values):
        row = {
            "market_code": market_code,
            "weather_date": weather_date,
            "average_temperature_c": 30.0,
            "average_temperature_f": 86.0,
            "average_relative_humidity_pct": 62.5,
            "major_event_weather_readiness_band": "favorable",
            "heat_stress_flag": True,
            **values,
        }
        with self.engine.begin() as connection:
            connection.execute(self.weather.insert(), [row])

    def add_heat(self, market_code, *points, weather_date=None):
        rows = []
        for lon, lat, uhi, canopy, land_cover in points:
            row = {
                "market_code": market_code,
                "longitude": lon,
                "latitude": lat,
                "uhi": uhi,
                "tree_canopy": canopy,
                "land_cover": land_cover,
            }
            if weather_date is not None:
                row["weather_date"] = weather_date
            rows.append(row)
        with self.engine.begin() as connection:
            connection.execute(self.heat.insert(), rows)

    def repository(self):
        return HeatmapRepository(self.session)

    def close(self):
        self.session.close()
        self.engine.dispose()


@pytest.fixture
def database():
    db = HeatmapDatabase()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seeded(database):
    """Houston and Dallas on DATE; Houston has three heat-index points."""
    database.add_weather("houston")
    database.add_weather(
        "dallas",
        average_temperature_c=33.0,
        average_temperature_f=91.4,
        average_relative_humidity_pct=40.0,
    )
    database.add_heat("houston", HOUSTON_A, HOUSTON_B, HOUSTON_C)
    database.add_heat("dallas", DALLAS_A)
    return database


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


class TestToWeight:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (12, 12.0),
            (12.5, 12.5),
            ("12.5", 12.5),
            (Decimal("3.25"), 3.25),
            (True, 1.0),
            (False, 0.0),
            (0, 0.0),
        ],
    )
    def test_a_numeric_value_becomes_a_float(self, raw, expected):
        assert HeatmapRepository._to_weight(raw) == expected

    @pytest.mark.parametrize("raw", [None, NAN, "favorable", object()])
    def test_a_missing_or_non_numeric_value_has_no_weight(self, raw):
        assert HeatmapRepository._to_weight(raw) is None


class TestCoerceDate:
    @pytest.mark.parametrize(
        "raw",
        [DATE, dt.datetime(2026, 7, 15, 18, 30), "2026-07-15", " 2026-07-15 ", "2026-07-15T18:30:00"],
    )
    def test_every_accepted_form_is_the_calendar_date(self, raw):
        assert HeatmapRepository._coerce_date(raw) == DATE

    def test_an_unparseable_date_raises_value_error(self):
        """The routes turn ValueError into a 400."""
        with pytest.raises(ValueError):
            HeatmapRepository._coerce_date("15/07/2026")


class TestResolveMarkets:
    @pytest.fixture
    def repository(self):
        return HeatmapRepository(None)

    def test_no_market_means_every_supported_market(self, repository):
        assert repository._resolve_markets(None) == list(
            HeatmapRepository.SUPPORTED_MARKET_CODES
        )

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("houston", ["houston"]),
            ("Houston", ["houston"]),
            ("  Kansas   City ", ["kansas_city"]),
            ("new_york", ["new_york_nj"]),
            ("New Jersey", ["new_york_nj"]),
            ("San Francisco Bay Area", ["san_francisco"]),
        ],
    )
    def test_a_city_spelling_normalises_to_its_market_code(self, repository, raw, expected):
        assert repository._resolve_markets(raw) == expected

    def test_an_iterable_keeps_order_and_drops_unknown_markets(self, repository):
        assert repository._resolve_markets(["Dallas", "Atlantis", "miami"]) == [
            "dallas",
            "miami",
        ]

    def test_an_unknown_market_resolves_to_nothing(self, repository):
        assert repository._resolve_markets("Atlantis") == []


class TestFormatValue:
    @pytest.fixture
    def repository(self):
        return HeatmapRepository(None)

    @pytest.mark.parametrize(
        "column, raw, expected",
        [
            ("average_temperature_c", 30.0, "30°C"),
            ("average_temperature_c", 30.46, "30.5°C"),
            ("average_relative_humidity_pct", 62.5, "62.5%"),
            ("average_relative_humidity_pct", Decimal("62.5"), "62.5%"),
            ("local_temperature_f", 83.0137, "83.0°F"),
            ("local_temperature_c", 28.34, "28.3°C"),
            ("major_event_weather_readiness_score", 88, "88 / 100"),
            ("uhi", 3.0, "3"),
        ],
    )
    def test_a_number_is_rounded_and_stamped_with_its_unit(self, repository, column, raw, expected):
        assert repository._format_value(column, raw) == expected

    def test_a_boolean_reads_yes_or_no_not_one_or_zero(self, repository):
        assert repository._format_value("heat_stress_flag", True) == "Yes"
        assert repository._format_value("heat_stress_flag", False) == "No"

    def test_a_date_is_iso_formatted(self, repository):
        assert repository._format_value("opened_on", DATE) == "2026-07-15"

    def test_text_passes_through(self, repository):
        assert repository._format_value("major_event_weather_readiness_band", "favorable") == "favorable"


class TestUnitFor:
    """The suffix a formatted value carries is chosen from its column name."""

    @pytest.fixture
    def repository(self):
        return HeatmapRepository(None)

    @pytest.mark.parametrize(
        "column, unit",
        [
            ("average_temperature_c", "°C"),
            ("local_temperature_c", "°C"),
            ("local_temperature_f", "°F"),
            ("average_relative_humidity_pct", "%"),
            ("average_sea_level_pressure_mbar", " hPa"),
            ("major_event_weather_readiness_score", " / 100"),
            ("uhi", ""),
        ],
    )
    def test_a_column_gets_the_unit_its_name_hints_at(self, repository, column, unit):
        assert repository._unit_for(column) == unit

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: UNIT_HINTS has no Fahrenheit entry for anything but "
            "local_temperature_f, so *_f temperature columns fall through to "
            "'temp' / 'dew_point' and are stamped °C (86°F renders as '86°C')."
        ),
    )
    @pytest.mark.parametrize(
        "column", ["average_temperature_f", "maximum_temperature_f", "average_dew_point_f"]
    )
    def test_a_fahrenheit_column_is_stamped_fahrenheit(self, repository, column):
        assert repository._unit_for(column) == "°F"

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: heat_index_c/_f are apparent temperatures (the frontend legend "
            "runs 60°F-125°F / 16°C-52°C), but the 'heat_index' hint stamps "
            "them ' / 100' as if they were scores."
        ),
    )
    @pytest.mark.parametrize("column, unit", [("heat_index_f", "°F"), ("heat_index_c", "°C")])
    def test_a_heat_index_is_stamped_as_a_temperature(self, repository, column, unit):
        assert repository._unit_for(column) == unit

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG: the unit named in the column is replaced by a different one - "
            "*_knots is stamped ' mph' and *_mm is stamped ' in' - with no "
            "conversion of the value."
        ),
    )
    @pytest.mark.parametrize(
        "column, unit",
        [("average_wind_speed_knots", " kn"), ("precipitation_3d_sum_mm", " mm")],
    )
    def test_a_unit_suffixed_column_keeps_its_own_unit(self, repository, column, unit):
        assert repository._unit_for(column) == unit


class TestLocalTemperatureModel:
    """Local temperature = market average + an offset from the point's UHI.

    The model assumes a 7°F spread between UHI 1 and UHI 11, with zero offset
    at the mean UHI. A spread is a temperature *difference*, so it converts to
    Celsius by the 5/9 ratio alone.
    """

    def test_the_mean_uhi_has_no_offset(self):
        mean = HeatmapRepository.MEAN_UHI

        assert HeatmapRepository._calculate_local_temperature_f(86.0, mean) == pytest.approx(86.0)
        assert HeatmapRepository._calculate_local_temperature_c(30.0, mean) == pytest.approx(30.0)

    def test_uhi_1_to_11_spans_seven_fahrenheit_degrees(self):
        low = HeatmapRepository._calculate_local_temperature_f(86.0, 1.0)
        high = HeatmapRepository._calculate_local_temperature_f(86.0, 11.0)

        assert high - low == pytest.approx(7.0)
        assert low == pytest.approx(83.01367381685866)
        assert high == pytest.approx(90.01367381685866)

    def test_the_celsius_spread_has_no_32_degree_offset(self):
        low = HeatmapRepository._calculate_local_temperature_c(30.0, 1.0)
        high = HeatmapRepository._calculate_local_temperature_c(30.0, 11.0)

        assert high - low == pytest.approx(7.0 * 5.0 / 9.0)
        assert low == pytest.approx(28.34092989825481)

    @pytest.mark.parametrize(
        "raw, clamped", [(-4.0, 1.0), (0.0, 1.0), (11.0, 11.0), (25.0, 11.0), (6.5, 6.5)]
    )
    def test_uhi_is_clamped_to_the_1_to_11_scale(self, raw, clamped):
        assert HeatmapRepository._clamp_urban_heat_index(raw) == clamped
        assert HeatmapRepository._calculate_local_temperature_f(
            86.0, raw
        ) == HeatmapRepository._calculate_local_temperature_f(86.0, clamped)


class TestResolveMetricColumn:
    @pytest.fixture
    def tables(self):
        _, weather, heat = build_tables()
        return weather, heat

    def test_a_weather_column_resolves_to_the_weather_table(self, tables):
        weather, heat = tables

        column, source = HeatmapRepository(None)._resolve_metric_column(
            " average_temperature_c ", weather, heat
        )

        assert column is weather.c.average_temperature_c
        assert source == "w__"

    def test_a_heat_index_column_resolves_to_the_heat_table(self, tables):
        weather, heat = tables

        column, source = HeatmapRepository(None)._resolve_metric_column("uhi", weather, heat)

        assert column is heat.c.uhi
        assert source == "h__"

    def test_the_weather_table_wins_a_name_collision(self):
        metadata = MetaData()
        weather = Table("w", metadata, Column("id", Integer, primary_key=True), Column("shared", Float))
        heat = Table("h", metadata, Column("id", Integer, primary_key=True), Column("shared", Float))

        column, source = HeatmapRepository(None)._resolve_metric_column("shared", weather, heat)

        assert column is weather.c.shared
        assert source == "w__"

    @pytest.mark.parametrize("metric", sorted(HeatmapRepository.SYNTHETIC_METRICS))
    def test_a_synthetic_metric_has_no_column(self, tables, metric):
        assert HeatmapRepository(None)._resolve_metric_column(metric, *tables) == (
            None,
            "synthetic__",
        )

    @pytest.mark.parametrize("metric", ["latitude", "market_code", "weather_date", "id"])
    def test_a_structural_column_is_not_a_metric(self, tables, metric):
        with pytest.raises(ValueError, match="structural column"):
            HeatmapRepository(None)._resolve_metric_column(metric, *tables)

    def test_an_unknown_metric_lists_what_is_available(self, tables):
        with pytest.raises(ValueError, match="Unknown metric 'nope'") as raised:
            HeatmapRepository(None)._resolve_metric_column("nope", *tables)

        assert "average_temperature_c" in str(raised.value)
        assert "'latitude'" not in str(raised.value)


class TestHeatBlock:
    def test_a_numeric_null_is_stored_as_nan_and_text_keeps_none(self):
        block = HeatBlock(("uhi", "land_cover"), {"uhi": True, "land_cover": False})

        block.append(-95.4, 29.7, (None, None), ("uhi", "land_cover"))
        block.append(-95.3, 29.8, (3, "urban"), ("uhi", "land_cover"))

        assert block.count == 2
        assert list(block.longitude) == [-95.4, -95.3]
        assert list(block.latitude) == [29.7, 29.8]
        uhi = block.metrics["uhi"]
        assert uhi[0] != uhi[0]  # NaN
        assert uhi[1] == 3.0
        assert block.metrics["land_cover"] == [None, "urban"]

    def test_nbytes_counts_eight_bytes_per_stored_value(self):
        block = HeatBlock(("uhi", "land_cover"), {"uhi": True, "land_cover": False})
        for i in range(3):
            block.append(0.0, 0.0, (float(i), "x"), ("uhi", "land_cover"))

        # lon + lat + uhi as doubles, land_cover as pointers.
        assert block.nbytes() == 3 * 8 * 4


# --------------------------------------------------------------------------- #
# getDataPointsForCityDateMetric
# --------------------------------------------------------------------------- #


class TestDataPointsForCityDateMetric:
    def test_a_weather_metric_puts_the_market_value_on_every_point(self, seeded):
        """Weather is one row per market and date; the heat-index table
        supplies the coordinates it is spread over. Coordinates are
        [lon, lat]."""
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "houston"
        )

        assert result == {
            DATE_KEY: [
                {"value": 30.0, "location_coordinates": coordinates(HOUSTON_A)},
                {"value": 30.0, "location_coordinates": coordinates(HOUSTON_B)},
                {"value": 30.0, "location_coordinates": coordinates(HOUSTON_C)},
            ]
        }

    def test_a_heat_index_metric_is_per_point_and_drops_nulls(self, seeded):
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "tree_canopy", "houston"
        )

        assert result == {
            DATE_KEY: [
                {"value": 12.0, "location_coordinates": coordinates(HOUSTON_A)},
                {"value": 40.0, "location_coordinates": coordinates(HOUSTON_C)},
            ]
        }

    @pytest.mark.parametrize("metric", sorted(HeatmapRepository.SYNTHETIC_METRICS))
    def test_a_synthetic_change_metric_is_zero_everywhere(self, seeded, metric):
        """change_in_* is all zeros until a simulation moves it."""
        result = seeded.repository().getDataPointsForCityDateMetric(DATE_KEY, metric, "houston")

        assert [point["value"] for point in result[DATE_KEY]] == [0, 0, 0]

    def test_only_the_requested_market_is_returned(self, seeded):
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "dallas"
        )

        assert result == {
            DATE_KEY: [{"value": 33.0, "location_coordinates": coordinates(DALLAS_A)}]
        }

    def test_no_market_means_every_market(self, seeded):
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c"
        )

        assert sorted(point["value"] for point in result[DATE_KEY]) == [30.0, 30.0, 30.0, 33.0]

    def test_a_city_display_name_reads_its_market(self, seeded):
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "Houston"
        )

        assert len(result[DATE_KEY]) == 3

    @pytest.mark.parametrize("weather_date", [DATE, dt.datetime(2026, 7, 15, 9, 0)])
    def test_a_date_object_is_keyed_by_its_iso_string(self, seeded, weather_date):
        result = seeded.repository().getDataPointsForCityDateMetric(
            weather_date, "average_temperature_c", "houston"
        )

        assert list(result) == [DATE_KEY]

    def test_a_date_with_no_weather_row_has_no_points(self, seeded):
        """The frontend treats the resulting 404 as an empty map."""
        assert (
            seeded.repository().getDataPointsForCityDateMetric(
                NEXT_DATE, "average_temperature_c", "houston"
            )
            == {}
        )

    def test_a_null_weather_value_skips_the_market(self, database):
        database.add_weather("houston", average_temperature_c=None)
        database.add_heat("houston", HOUSTON_A)

        assert (
            database.repository().getDataPointsForCityDateMetric(
                DATE_KEY, "average_temperature_c", "houston"
            )
            == {}
        )

    def test_an_unknown_city_has_no_points(self, seeded):
        assert (
            seeded.repository().getDataPointsForCityDateMetric(
                DATE_KEY, "average_temperature_c", "Atlantis"
            )
            == {}
        )

    def test_additional_metrics_are_formatted_in_the_requested_order(self, seeded):
        """Rows mix both tables; each carries its unit, and a heat-index value
        that is NULL at a point is simply absent from that point's rows.
        Duplicates and blanks in the request are ignored."""
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY,
            "average_temperature_c",
            "houston",
            additional_metrics=[
                "tree_canopy",
                " average_relative_humidity_pct ",
                "tree_canopy",
                "",
                "land_cover",
            ],
        )

        a, b, c = (point["individual_metrics"] for point in result[DATE_KEY])
        assert list(a.items()) == [
            ("tree_canopy", "12"),
            ("average_relative_humidity_pct", "62.5%"),
            ("land_cover", "urban"),
        ]
        assert list(b.items()) == [
            ("average_relative_humidity_pct", "62.5%"),
            ("land_cover", "suburban"),
        ]
        assert list(c.items()) == [
            ("tree_canopy", "40"),
            ("average_relative_humidity_pct", "62.5%"),
        ]

    def test_weather_only_additional_metrics_are_the_same_on_every_point(self, seeded):
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY,
            "tree_canopy",
            "houston",
            additional_metrics=["heat_stress_flag", "major_event_weather_readiness_band"],
        )

        expected = {
            "heat_stress_flag": "Yes",
            "major_event_weather_readiness_band": "favorable",
        }
        assert [point["individual_metrics"] for point in result[DATE_KEY]] == [expected, expected]

    def test_an_additional_metric_can_repeat_the_drawn_metric(self, seeded):
        """availableMetrics in map.ts lists the drawn metric among its own
        tooltip rows."""
        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "dallas", additional_metrics=["average_temperature_c"]
        )

        assert result[DATE_KEY][0]["individual_metrics"] == {"average_temperature_c": "33°C"}

    @pytest.mark.parametrize(
        "metric, additional, message",
        [
            ("nope", None, "Unknown metric 'nope'"),
            ("latitude", None, "structural column"),
            ("average_temperature_c", ["nope"], "Unknown metric 'nope'"),
        ],
    )
    def test_an_unknown_or_structural_metric_raises(self, seeded, metric, additional, message):
        with pytest.raises(ValueError, match=message):
            seeded.repository().getDataPointsForCityDateMetric(
                DATE_KEY, metric, "houston", additional_metrics=additional
            )


# --------------------------------------------------------------------------- #
# getLocalTemperatureByCityDate
# --------------------------------------------------------------------------- #


class TestLocalTemperatureByCityDate:
    def test_fahrenheit_offsets_the_market_average_by_each_point_s_uhi(self, seeded):
        """A point with no UHI reading has no local temperature and is dropped."""
        result = seeded.repository().getLocalTemperatureByCityDate(
            DATE_KEY, market_code="houston", temperature_unit="f"
        )

        assert list(result) == [DATE_KEY]
        a, b = result[DATE_KEY]
        assert a["location_coordinates"] == coordinates(HOUSTON_A)
        assert a["value"] == pytest.approx(83.01367381685866)
        assert a["individual_metrics"] == {"local_temperature_f": "83.0°F"}
        assert b["location_coordinates"] == coordinates(HOUSTON_B)
        assert b["value"] == pytest.approx(90.01367381685866)
        assert b["individual_metrics"] == {"local_temperature_f": "90.0°F"}

    def test_celsius_reads_the_celsius_average(self, seeded):
        result = seeded.repository().getLocalTemperatureByCityDate(
            DATE_KEY, market_code="houston", temperature_unit="c"
        )

        values = [point["value"] for point in result[DATE_KEY]]
        assert values == pytest.approx([28.34092989825481, 32.2298187871437])
        assert result[DATE_KEY][0]["individual_metrics"] == {"local_temperature_c": "28.3°C"}

    def test_the_frontend_s_explicit_source_column_is_used(self, seeded):
        """map.ts sends metric=average_temperature_c with unit c."""
        result = seeded.repository().getLocalTemperatureByCityDate(
            DATE_KEY,
            metric="average_temperature_c",
            market_code="houston",
            temperature_unit="c",
        )

        assert result[DATE_KEY][0]["value"] == pytest.approx(28.34092989825481)

    def test_the_default_unit_is_fahrenheit(self, seeded):
        result = seeded.repository().getLocalTemperatureByCityDate(DATE_KEY, market_code="houston")

        assert "local_temperature_f" in result[DATE_KEY][0]["individual_metrics"]

    def test_the_unit_is_case_and_space_insensitive(self, seeded):
        result = seeded.repository().getLocalTemperatureByCityDate(
            DATE_KEY, market_code="houston", temperature_unit=" C "
        )

        assert "local_temperature_c" in result[DATE_KEY][0]["individual_metrics"]

    def test_requested_rows_come_first_and_the_local_temperature_last(self, seeded):
        result = seeded.repository().getLocalTemperatureByCityDate(
            DATE_KEY,
            market_code="houston",
            additional_metrics=["uhi", "average_relative_humidity_pct", "tree_canopy"],
            temperature_unit="f",
        )

        a, b = (point["individual_metrics"] for point in result[DATE_KEY])
        assert list(a.items()) == [
            ("uhi", "1"),
            ("average_relative_humidity_pct", "62.5%"),
            ("tree_canopy", "12"),
            ("local_temperature_f", "83.0°F"),
        ]
        # HOUSTON_B has no canopy reading, so that row is absent there.
        assert list(b) == ["uhi", "average_relative_humidity_pct", "local_temperature_f"]

    def test_a_date_with_no_weather_row_has_no_points(self, seeded):
        assert seeded.repository().getLocalTemperatureByCityDate(NEXT_DATE, market_code="houston") == {}

    def test_a_null_average_temperature_skips_the_market(self, database):
        database.add_weather("houston", average_temperature_f=None)
        database.add_heat("houston", HOUSTON_A)

        assert database.repository().getLocalTemperatureByCityDate(DATE_KEY, market_code="houston") == {}

    def test_an_unknown_city_has_no_points(self, seeded):
        assert seeded.repository().getLocalTemperatureByCityDate(DATE_KEY, market_code="Atlantis") == {}

    def test_an_unsupported_unit_raises(self, seeded):
        with pytest.raises(ValueError, match="temperature_unit must be 'f' or 'c'"):
            seeded.repository().getLocalTemperatureByCityDate(
                DATE_KEY, market_code="houston", temperature_unit="k"
            )

    @pytest.mark.parametrize("metric", ["uhi", "market_code", "nope"])
    def test_a_source_column_that_is_not_a_weather_metric_raises(self, seeded, metric):
        with pytest.raises(ValueError, match="is not an available column"):
            seeded.repository().getLocalTemperatureByCityDate(
                DATE_KEY, metric=metric, market_code="houston"
            )


# --------------------------------------------------------------------------- #
# Cache behaviour behind both reads
# --------------------------------------------------------------------------- #


class TestPreloadAndFallback:
    def test_after_the_preload_reads_need_no_tables(self, seeded):
        """Once initialize_tables has run, serving a request touches no
        database: dropping both tables changes nothing."""
        HeatmapRepository.initialize_tables(seeded.engine)
        seeded.metadata.drop_all(seeded.engine)

        result = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "houston"
        )

        assert [point["value"] for point in result[DATE_KEY]] == [30.0, 30.0, 30.0]

    def test_the_lazy_fallback_and_the_preload_give_the_same_answer(self, seeded):
        arguments = dict(
            weather_date=DATE_KEY,
            metric="average_temperature_c",
            market_code="houston",
            additional_metrics=["tree_canopy", "heat_stress_flag"],
        )

        lazy = seeded.repository().getDataPointsForCityDateMetric(**arguments)
        HeatmapRepository.initialize_tables(seeded.engine, force=True)
        preloaded = seeded.repository().getDataPointsForCityDateMetric(**arguments)

        assert lazy == preloaded

    def test_a_lazy_single_market_load_does_not_mark_the_table_loaded(self, seeded):
        """Otherwise every other market would read as empty forever."""
        seeded.repository().getDataPointsForCityDateMetric(DATE_KEY, "tree_canopy", "houston")

        assert HeatmapRepository._heat_loaded is False
        assert set(HeatmapRepository._heat_cache) == {("houston", None)}

        dallas = seeded.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "tree_canopy", "dallas"
        )
        assert [point["value"] for point in dallas[DATE_KEY]] == [20.0]

    def test_heat_rows_without_coordinates_are_not_loaded(self, database):
        database.add_weather("houston")
        database.add_heat("houston", HOUSTON_A, (None, 29.9, 3.0, 5.0, "x"), (-95.2, None, 3.0, 5.0, "x"))

        result = database.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "houston"
        )

        assert [point["location_coordinates"] for point in result[DATE_KEY]] == [coordinates(HOUSTON_A)]

    def test_a_duplicate_weather_row_keeps_the_first(self, database):
        database.add_weather("houston", average_temperature_c=30.0)
        database.add_weather("houston", average_temperature_c=99.0)
        database.add_heat("houston", HOUSTON_A)

        result = database.repository().getDataPointsForCityDateMetric(
            DATE_KEY, "average_temperature_c", "houston"
        )

        assert result[DATE_KEY][0]["value"] == 30.0

    def test_a_forced_reload_picks_up_new_rows(self, seeded):
        HeatmapRepository.initialize_tables(seeded.engine)
        seeded.add_weather("houston", weather_date=NEXT_DATE, average_temperature_c=25.0)

        before = seeded.repository().getDataPointsForCityDateMetric(
            NEXT_DATE, "average_temperature_c", "houston"
        )
        HeatmapRepository.initialize_tables(seeded.engine, force=True)
        after = seeded.repository().getDataPointsForCityDateMetric(
            NEXT_DATE, "average_temperature_c", "houston"
        )

        assert before == {}
        assert [point["value"] for point in after["2026-07-16"]] == [25.0, 25.0, 25.0]

    def test_cache_stats_describe_what_is_resident(self, seeded):
        HeatmapRepository.initialize_tables(seeded.engine)

        stats = HeatmapRepository.cache_stats()

        assert stats["heat_blocks"] == 2
        assert stats["heat_points"] == 4
        assert stats["weather_rows"] == 2
        assert stats["heat_loaded"] is True
        assert stats["weather_loaded"] is True
        assert stats["heat_partitioned_by_date"] is False


class TestDatePartitionedHeatTable:
    @pytest.fixture
    def partitioned(self):
        db = HeatmapDatabase(partitioned=True)
        db.add_weather("houston", weather_date=DATE)
        db.add_weather("houston", weather_date=NEXT_DATE, average_temperature_c=25.0)
        db.add_heat("houston", HOUSTON_A, weather_date=DATE)
        db.add_heat("houston", HOUSTON_B, weather_date=NEXT_DATE)
        try:
            yield db
        finally:
            db.close()

    @pytest.mark.parametrize("preload", [True, False])
    def test_each_date_reads_only_its_own_points(self, partitioned, preload):
        if preload:
            HeatmapRepository.initialize_tables(partitioned.engine)
        repository = partitioned.repository()

        today = repository.getDataPointsForCityDateMetric(DATE, "average_temperature_c", "houston")
        tomorrow = repository.getDataPointsForCityDateMetric(
            NEXT_DATE, "average_temperature_c", "houston"
        )

        assert today == {
            DATE_KEY: [{"value": 30.0, "location_coordinates": coordinates(HOUSTON_A)}]
        }
        assert tomorrow == {
            "2026-07-16": [{"value": 25.0, "location_coordinates": coordinates(HOUSTON_B)}]
        }

    def test_weather_date_is_not_reported_as_a_metric(self, partitioned):
        result = partitioned.repository().getDataPointsForCityDateMetric(
            DATE, "uhi", "houston", additional_metrics=["land_cover"]
        )

        assert result[DATE_KEY][0]["individual_metrics"] == {"land_cover": "urban"}
        assert HeatmapRepository.cache_stats()["heat_partitioned_by_date"] is True


# --------------------------------------------------------------------------- #
# get_simulated_points_by_date
# --------------------------------------------------------------------------- #


def intervention(**overrides):
    fields = dict(
        id="0b6c3b4e-0000-0000-0000-000000000001",
        market_code="houston",
        name="Tree",
        color="#22c55e",
        archetype_code="vegetation",
        intervention_type="street_tree",
        geometry_kind="point",
        geometry={"type": "Point", "coordinates": [-95.4, 29.7]},
        parameters={"coverPct": 40},
        status="active",
        active_from=dt.datetime(2026, 7, 1),
        active_to=None,
    )
    fields.update(overrides)
    return UrbanInterventionRecord(**fields)


@pytest.fixture
def simulation_seams(monkeypatch):
    """Record the intervention query and the simulation call."""
    recorded = SimpleNamespace(interventions=[], queries=[], simulations=[])

    class FakeInterventionRepository:
        def __init__(self, session):
            self.session = session

        def get_all_by_city_between_date(self, city, from_date, to_date):
            recorded.queries.append((city, from_date, to_date))
            return iter(recorded.interventions)

    def fake_simulation(metric, points_by_date, categorized_objects, mode):
        recorded.simulations.append(
            dict(
                metric=metric,
                points_by_date=points_by_date,
                categorized_objects=categorized_objects,
                mode=mode,
            )
        )
        return SimpleNamespace(
            points_by_date={"simulated": True},
            feedback=SimpleNamespace(affected_points=0, overlap_points=0, max_objects_at_point=0),
        )

    monkeypatch.setattr(heatmap_repository, "UrbanInterventionRepository", FakeInterventionRepository)
    monkeypatch.setattr(simulation_services, "run_diminishing_return_simulation", fake_simulation)
    return recorded


class TestSimulatedPointsByDate:
    def test_the_simulation_result_is_returned(self, seeded, simulation_seams):
        """Inside an envelope, not bare.

        A standard run carries the points alone. The other two branches add a
        sibling key rather than changing this one: ``mode="contextual"`` adds
        ``feedback``, and passing chat ``state`` adds ``messages``.
        """
        result = seeded.repository().get_simulated_points_by_date(
            DATE_KEY, DATE_KEY, "Houston", "average_temperature_c"
        )

        assert result == {"points_by_date": {"simulated": True}}

    def test_every_date_in_the_range_is_fed_to_the_simulation(self, seeded, simulation_seams):
        """Including a date with no readings, as an empty list."""
        seeded.add_weather("houston", weather_date=NEXT_DATE, average_temperature_c=25.0)

        seeded.repository().get_simulated_points_by_date(
            DATE_KEY, "2026-07-17", "Houston", "average_temperature_c", mode="contextual"
        )

        (call,) = simulation_seams.simulations
        points_by_date = call["points_by_date"]
        assert list(points_by_date) == ["2026-07-15", "2026-07-16", "2026-07-17"]
        assert [p["value"] for p in points_by_date["2026-07-15"]] == [30.0, 30.0, 30.0]
        assert [p["value"] for p in points_by_date["2026-07-16"]] == [25.0, 25.0, 25.0]
        assert points_by_date["2026-07-17"] == []
        assert call["metric"] == "average_temperature_c"
        assert call["mode"] == "contextual"

    def test_interventions_are_queried_for_the_market_and_range(self, seeded, simulation_seams):
        seeded.repository().get_simulated_points_by_date(
            DATE_KEY, "2026-07-17", "New Jersey", "average_temperature_c"
        )

        assert simulation_seams.queries == [("new_york_nj", DATE, dt.date(2026, 7, 17))]

    def test_additional_metrics_reach_the_readings(self, seeded, simulation_seams):
        seeded.repository().get_simulated_points_by_date(
            DATE_KEY,
            DATE_KEY,
            "houston",
            "average_temperature_c",
            additional_metrics=["average_relative_humidity_pct"],
        )

        points = simulation_seams.simulations[0]["points_by_date"][DATE_KEY]
        assert points[0]["individual_metrics"] == {"average_relative_humidity_pct": "62.5%"}

    @pytest.mark.parametrize(
        "metric, expected",
        [
            ("local_temperature_f", [83.01367381685866, 90.01367381685866]),
            ("change_in_local_temperature_f", [83.01367381685866, 90.01367381685866]),
            ("local_temperature_c", [28.34092989825481, 32.2298187871437]),
            ("change_in_local_temperature_c", [28.34092989825481, 32.2298187871437]),
        ],
    )
    def test_local_temperature_metrics_start_from_the_local_temperature(
        self, seeded, simulation_seams, metric, expected
    ):
        """The simulation cools each point from its own local temperature, in
        the metric's unit."""
        seeded.repository().get_simulated_points_by_date(DATE_KEY, DATE_KEY, "houston", metric)

        points = simulation_seams.simulations[0]["points_by_date"][DATE_KEY]
        assert [point["value"] for point in points] == pytest.approx(expected)

    def test_a_change_in_average_temperature_starts_from_zero(self, seeded, simulation_seams):
        seeded.repository().get_simulated_points_by_date(
            DATE_KEY, DATE_KEY, "houston", "change_in_average_temperature_c"
        )

        points = simulation_seams.simulations[0]["points_by_date"][DATE_KEY]
        assert [point["value"] for point in points] == [0, 0, 0]

    def test_a_reversed_range_raises(self, seeded, simulation_seams):
        with pytest.raises(ValueError, match="from_date must not be after to_date"):
            seeded.repository().get_simulated_points_by_date(
                "2026-07-16", DATE_KEY, "houston", "average_temperature_c"
            )

        assert simulation_seams.simulations == []

    def test_an_unknown_city_raises(self, seeded, simulation_seams):
        with pytest.raises(ValueError, match="Unknown city 'Atlantis'"):
            seeded.repository().get_simulated_points_by_date(
                DATE_KEY, DATE_KEY, "Atlantis", "average_temperature_c"
            )

    def test_interventions_are_grouped_before_simulating(self, seeded, simulation_seams):
        simulation_seams.interventions = [intervention()]

        seeded.repository().get_simulated_points_by_date(
            DATE_KEY, DATE_KEY, "houston", "average_temperature_c"
        )

        grouped = simulation_seams.simulations[0]["categorized_objects"]
        assert [obj["name"] for obj in grouped["Vegetation"]] == ["Tree"]


class TestGroupInterventionsForSimulation:
    group = staticmethod(HeatmapRepository._group_interventions_for_simulation)

    def test_no_interventions_still_yields_every_category(self):
        assert self.group([]) == {
            "Vegetation": [],
            "High-albedo surface": [],
            "Shade structure": [],
            "Evaporative / water": [],
        }

    @pytest.mark.parametrize(
        "intervention_type, category",
        [
            ("street_tree", "Vegetation"),
            ("cool_roof", "High-albedo surface"),
            ("cool_pavement", "High-albedo surface"),
            ("shade_structure", "Shade structure"),
            ("misting_station", "Evaporative / water"),
        ],
    )
    def test_each_intervention_type_lands_in_its_archetype(self, intervention_type, category):
        grouped = self.group([intervention(intervention_type=intervention_type)])

        assert [obj["type"] for obj in grouped[category]] == [intervention_type]
        assert sum(len(objects) for objects in grouped.values()) == 1

    def test_a_record_becomes_the_placed_object_shape_the_simulation_reads(self):
        """Keys follow the TypeScript BasePlacedObject, camelCase included."""
        grouped = self.group(
            [
                intervention(
                    active_from=dt.datetime(2026, 7, 1),
                    active_to=dt.datetime(2026, 7, 31, 12, 0),
                )
            ]
        )

        assert grouped["Vegetation"] == [
            {
                "id": "0b6c3b4e-0000-0000-0000-000000000001",
                "name": "Tree",
                "type": "street_tree",
                "category": "Vegetation",
                "color": "#22c55e",
                "market_code": "houston",
                "geometry": {"kind": "point", "longitude": -95.4, "latitude": 29.7},
                "params": {"coverPct": 40},
                "activeFrom": "2026-07-01T00:00:00",
                "activeTo": "2026-07-31T12:00:00",
            }
        ]

    def test_an_open_ended_window_is_none(self):
        (obj,) = self.group([intervention(active_from=None, active_to=None)])["Vegetation"]

        assert obj["activeFrom"] is None
        assert obj["activeTo"] is None

    def test_a_line_keeps_its_coordinates(self):
        line = [[-95.4, 29.7], [-95.3, 29.8]]

        (obj,) = self.group(
            [intervention(geometry_kind="line", geometry={"type": "LineString", "coordinates": line})]
        )["Vegetation"]

        assert obj["geometry"] == {"kind": "line", "coordinates": line}

    def test_a_polygon_is_reduced_to_its_outer_ring(self):
        outer = [[-95.4, 29.7], [-95.3, 29.7], [-95.3, 29.8], [-95.4, 29.7]]
        hole = [[-95.36, 29.72], [-95.34, 29.72], [-95.35, 29.74], [-95.36, 29.72]]

        (obj,) = self.group(
            [
                intervention(
                    intervention_type="cool_roof",
                    geometry_kind="polygon",
                    geometry={"type": "Polygon", "coordinates": [outer, hole]},
                )
            ]
        )["High-albedo surface"]

        assert obj["geometry"] == {"kind": "polygon", "ring": outer}

    def test_a_uuid_id_is_sent_as_a_string(self):
        from uuid import UUID

        uuid = UUID("12345678-1234-5678-1234-567812345678")

        (obj,) = self.group([intervention(id=uuid)])["Vegetation"]

        assert obj["id"] == "12345678-1234-5678-1234-567812345678"
