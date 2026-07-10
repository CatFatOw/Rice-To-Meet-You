"""Helpers for live traffic camera metadata.

These functions fetch public traffic camera metadata that can be passed to
frontend map layers or downstream computer-vision jobs.
"""

from datetime import datetime, timezone
from typing import Any
import requests

TXDOT_BASE_URL = "https://its.txdot.gov/its"
TXDOT_CCTV_STATUS_ENDPOINT = "DistrictIts/GetCctvStatusListByDistrict"
DEFAULT_TIMEOUT_SECONDS = 15


def get_txdot_cameras(
    district_code: str = "HOU",
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return TxDOT cameras as flat map-ready records.

    TxDOT returns camera statuses grouped by roadway. For the frontend we only
    need one flat list containing each camera's display name, IDs, and position.
    """
    http = session or requests
    response = http.get(
        f"{TXDOT_BASE_URL}/{TXDOT_CCTV_STATUS_ENDPOINT}",
        params={"districtCode": district_code},
        timeout=timeout,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()

    payload = response.json()
    roadway_cameras = payload.get("roadwayCctvStatuses", {})
    cameras: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()

    for roadway_name, camera_group in roadway_cameras.items():
        for camera in camera_group or []:
            normalized = _normalize_txdot_camera(camera, roadway_name)
            if not normalized:
                continue

            camera_key = (normalized["icd_id"], normalized["netid"])
            if camera_key in seen:
                continue

            seen.add(camera_key)
            cameras.append(normalized)

    return cameras


def get_txdot_houston_cameras(
    *,
    session: requests.Session | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Return Houston TxDOT cameras from https://its.txdot.gov/its/District/HOU."""
    return get_txdot_cameras("HOU", session=session, timeout=timeout)


def _normalize_txdot_camera(
    camera: dict[str, Any],
    roadway_name: str | None = None,
) -> dict[str, Any] | None:
    lat = _to_float(camera.get("latitude") or camera.get("latString"))
    lon = _to_float(camera.get("longitude") or camera.get("lonString"))
    if lat is None or lon is None:
        return None

    return {
        "name": camera.get("name"),
        "icd_id": camera.get("icd_Id") or camera.get("icdId") or camera.get("id"),
        "netid": camera.get("netId") or camera.get("netid"),
        "lat": lat,
        "lon": lon,
        "roadway": roadway_name,
    }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

from math import radians, sin, cos, sqrt, atan2
import base64


TXDOT_SNAPSHOT_ENDPOINT = "DistrictIts/GetCctvSnapshotByIcdId"
SNAPSHOT_TIME_KEYS = {
    "capturedAt",
    "captured_at",
    "captureTime",
    "capture_time",
    "dateTime",
    "date_time",
    "imageDate",
    "image_date",
    "imageTime",
    "image_time",
    "lastUpdate",
    "last_update",
    "lastUpdated",
    "last_updated",
    "lastUpdatedTime",
    "last_updated_time",
    "timestamp",
    "timeStamp",
}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Function computes the greatest circle distance between two coordinates via 
    haversine formula to calculate shortes distance """
    r = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )

    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def get_nearest_txdot_camera(
    lat: float,
    lon: float,
    district_code: str = "HOU",
) -> dict[str, Any] | None:
    """Function gets cloests txdot traffic camera to a given location"""
    cameras = get_txdot_cameras(district_code)

    if not cameras:
        return None

    nearest = min(
        cameras,
        key=lambda cam: haversine_miles(lat, lon, cam["lat"], cam["lon"]),
    )

    nearest["distance_miles"] = round(
        haversine_miles(lat, lon, nearest["lat"], nearest["lon"]),
        3,
    )

    return nearest


def get_txdot_camera_snapshot(
    camera: dict[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> bytes:
    """Get the latest still image snapshot bytes."""
    snapshot = get_txdot_camera_snapshot_payload(camera, timeout=timeout)
    return snapshot["image_bytes"]


def get_txdot_camera_snapshot_payload(
    camera: dict[str, Any],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Get the latest snapshot image plus available TxDOT metadata."""
    icd_id = camera.get("icd_id")
    district_code = camera.get("netid") or "HOU"

    if not icd_id:
        raise ValueError("Camera is missing icd_id")

    response = requests.get(
        f"{TXDOT_BASE_URL}/{TXDOT_SNAPSHOT_ENDPOINT}",
        params={
            "icdId": icd_id,
            "districtCode": district_code,
        },
        timeout=timeout,
        headers={"Accept": "application/json"},
    )

    response.raise_for_status()
    payload = response.json()

    snippet = payload.get("snippet")
    if not snippet:
        raise ValueError("No camera snapshot returned")

    metadata = {key: value for key, value in payload.items() if key != "snippet"}

    return {
        "image_bytes": base64.b64decode(snippet),
        "captured_at": _find_snapshot_time(metadata),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }


def _find_snapshot_time(value: Any) -> str | None:
    """Best-effort extraction of a timestamp from TxDOT snapshot metadata."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SNAPSHOT_TIME_KEYS and item:
                return str(item)
        for item in value.values():
            found = _find_snapshot_time(item)
            if found:
                return found

    if isinstance(value, list):
        for item in value:
            found = _find_snapshot_time(item)
            if found:
                return found

    return None
