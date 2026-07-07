from ultralytics import YOLO
from collections import defaultdict
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np


VEHICLE_CLASSES = [1, 2, 3, 5, 6, 7]
DEFAULT_MODEL = "yolo26m-seg.pt"

class VehicleDetector:
    """YOLO vehicle detector that can return bbox and segmentation metadata."""

    def __init__(self, model_type: str | Path | None = None):
        self.model_type = str(
            model_type
            or os.getenv("TRAFFIC_YOLO_MODEL")
            or DEFAULT_MODEL
        )
        self.model = YOLO(self.model_type)
        self.result = None

    def predict(self, image: str | Path | bytes | np.ndarray, conf: float = 0.03, imgsz: int = 640):
        """Run YOLO prediction on an image path, raw bytes, or OpenCV image array."""
        image_input = self._prepare_image_input(image)
        results = self.model.predict(
            image_input,
            classes=VEHICLE_CLASSES,
            conf=conf,
            imgsz=imgsz,
        )
        self.result = results[0]
        return self.result

    def extract_prediction_info(self, result=None) -> dict[str, Any]:
        """Extract vehicle counts, bounding boxes, and segmentation polygons.

        Segmentation fields are populated when the loaded model is a YOLO
        segmentation model. Detection-only models still return bbox data with
        empty segmentation values.
        """
        result = result or self.result
        if result is None:
            raise ValueError("Run predict() before extracting prediction info.")

        vehicle_types = defaultdict(int)
        boxes = result.boxes or []
        total_vehicle_count = len(boxes)
        bboxes = []
        segmentations = []
        detections = []

        mask_polygons = []
        normalized_mask_polygons = []
        if getattr(result, "masks", None) is not None:
            mask_polygons = getattr(result.masks, "xy", []) or []
            normalized_mask_polygons = getattr(result.masks, "xyn", []) or []

        for index, box in enumerate(boxes):
            label = self.model.names[int(box.cls[0])]
            vehicle_types[label] += 1
            bbox = {
                "label": label,
                "confidence": float(box.conf[0]),
                "bbox": [float(value) for value in box.xyxy[0].tolist()],
            }
            segmentation = self._extract_segmentation(
                index,
                mask_polygons,
                normalized_mask_polygons,
            )

            bboxes.append(bbox)
            if segmentation is not None:
                segmentations.append({"label": label, **segmentation})

            detections.append({
                **bbox,
                "segmentation": segmentation,
            })

        return {
            "vehicle_types": dict(vehicle_types),
            "total_vehicle_count": total_vehicle_count,
            "bboxes": bboxes,
            "segmentations": segmentations,
            "detections": detections,
            "has_segmentation": bool(segmentations),
        }
    
    def plot(self, *, show: bool = True, output_path: str | Path | None = None):
        """Render the most recent prediction with boxes and masks if available."""
        if self.result is None:
            raise ValueError("Run predict() before plot().")

        annotated = self.result.plot(labels=False, conf=False)
        if output_path is not None:
            cv2.imwrite(str(output_path), annotated)

        if show:
            cv2.imshow("Vehicle Detection", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return annotated

    @staticmethod
    def _prepare_image_input(image: str | Path | bytes | np.ndarray):
        if isinstance(image, (str, Path, np.ndarray)):
            return image

        if isinstance(image, bytes):
            image_array = np.frombuffer(image, dtype=np.uint8)
            decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if decoded is None:
                raise ValueError("Could not decode image bytes.")
            return decoded

        raise TypeError("image must be a path, bytes, or numpy image array.")

    @staticmethod
    def _extract_segmentation(
        index: int,
        mask_polygons,
        normalized_mask_polygons,
    ) -> dict[str, Any] | None:
        if index >= len(mask_polygons):
            return None

        polygon = mask_polygons[index]
        normalized_polygon = (
            normalized_mask_polygons[index]
            if index < len(normalized_mask_polygons)
            else None
        )

        return {
            "polygon": polygon.astype(float).tolist(),
            "normalized_polygon": (
                normalized_polygon.astype(float).tolist()
                if normalized_polygon is not None
                else None
            ),
        }


if __name__ == "__main__":
    model = VehicleDetector()
    image_path = Path(__file__).with_name("test_traffic_2.png")
    result = model.predict(image_path)
    print(model.extract_prediction_info(result))
    model.plot()
