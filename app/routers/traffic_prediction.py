from functools import lru_cache

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from ml_models.YOLO_pipeline.traffic_detector import VehicleDetector
from services.live_traffic import (
    get_nearest_txdot_camera,
    get_txdot_camera_snapshot_payload,
    get_txdot_cameras,
)

router = APIRouter(prefix="/traffic_predict", tags=["traffic_predict"])


@lru_cache(maxsize=1)
def get_vehicle_detector() -> VehicleDetector:
    return VehicleDetector()


@router.get("/get_cameras/houston")
async def get_cameras_houston():
    """Function gets every single metadata for public city traffic data"""
    return {
        "district": "HOU",
        "cameras":get_txdot_cameras(),

    }

@router.get("/get_nearest_cameras")
async def get_nearest_cameras_houston(lat:float, lon:float):
    """Route gets nearest cameras given lat and lon"""
    camera = get_nearest_txdot_camera(lat, lon)
    if not camera:
        raise HTTPException(
            status_code=404,
            detail="No Houston TxDOT cameras found.",
        )
    return {
        "query": {
            "lat": lat,
            "lon": lon,
        },
        "camera": camera,
    }


@router.get("/nearest_camera/image")
async def get_nearest_camera_image(lat: float, lon: float):
    """Return the latest image from the nearest Houston TxDOT camera."""
    camera = get_nearest_txdot_camera(lat, lon, "HOU")

    if not camera:
        raise HTTPException(status_code=404, detail="No Houston TxDOT cameras found.")

    try:
        snapshot = get_txdot_camera_snapshot_payload(camera)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    headers = {
        "X-Traffic-Snapshot-Fetched-At": snapshot["fetched_at"],
    }
    if snapshot["captured_at"]:
        headers["X-Traffic-Snapshot-Captured-At"] = snapshot["captured_at"]

    return Response(content=snapshot["image_bytes"], media_type="image/jpeg", headers=headers)
    

@router.get("/nearest_camera/predict")
async def predict_nearest_camera(lat:float, lon:float):
    """Function uses YOLO model to predict on the camera image """
    camera = get_nearest_txdot_camera(lat, lon)
    if not camera:
        raise HTTPException(status_code=404, detail="No Houston TxDOT cameras found.")
    
    try:
        snapshot = get_txdot_camera_snapshot_payload(camera)
        model = get_vehicle_detector()
        result = model.predict(snapshot["image_bytes"])
        analysis = model.extract_prediction_info(result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "query": {"lat": lat, "lon": lon},
        "camera": camera,
        "snapshot": {
            "captured_at": snapshot["captured_at"],
            "fetched_at": snapshot["fetched_at"],
            "metadata": snapshot["metadata"],
        },
        "analysis": analysis,
    }
