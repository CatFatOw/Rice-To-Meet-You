import os
from pathlib import Path


def _load_environment_from_project_root() -> None:
    """Load values from the repository-level .env file if present."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_environment_from_project_root()


CACHE_VERSION = os.getenv("HEATMAP_CACHE_VERSION", "v1")

KEY_PREFIX = "heatsafe"


def create_weather_cache_key(market_code: str, weather_date) -> str:
    """Redis key holding the cached weather row for one market on one date."""
    return (
        f"{KEY_PREFIX}:weather:{CACHE_VERSION}:"
        f"{market_code.strip().lower()}:{weather_date.isoformat()}"
    )


def create_urban_heat_cache_key(market_code: str) -> str:
    """Redis key holding the cached urban heat index points for one market.

    Urban heat rows are reference data that do not vary by date, so one key per
    market is the whole cache entry.
    """
    return (
        f"{KEY_PREFIX}:urban_heat:{CACHE_VERSION}:"
        f"{market_code.strip().lower()}"
    )