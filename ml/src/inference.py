"""CivicSight ML Subsystem — Reusable Road Defect Detection Inference Module (Week 6)

Provides a clean, modular inference interface for the finalized Week 5 YOLOv8n model
(trained on RDD2022). Can be imported and invoked by upstream services, testing scripts,
and future API background workers.

Key Features:
- Singleton model caching to eliminate weight reloading overhead across consecutive calls
- Polymorphic input handling: File path (str/Path), PIL Image, NumPy array (RGB/BGR),
  or preprocessed dictionary from ml.src.preprocess.preprocess_report_image
- Standardized RDD2022 4-class taxonomy:
    * D00: Longitudinal Crack (MEDIUM severity)
    * D10: Transverse Crack (MEDIUM severity)
    * D20: Alligator Crack (HIGH severity)
    * D40: Pothole (HIGH severity)
- Structured dictionary output with exact pixel bounding boxes, normalized [0, 1] boxes,
  confidence scores, and aggregated hazard priority calculation.
"""

from typing import Union, Dict, Any, List, Optional, Tuple
from pathlib import Path
import time
import cv2
import numpy as np
import torch
from PIL import Image
from ultralytics import YOLO

# Project root resolution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_WEIGHTS_PATH = _PROJECT_ROOT / "ml" / "runs" / "detect" / "experiment2_week5" / "weights" / "best.pt"

# RDD2022 Class Taxonomy & Severity Grading
CLASS_METADATA: Dict[int, Dict[str, str]] = {
    0: {
        "code": "D00",
        "description": "Longitudinal Crack",
        "severity": "MEDIUM",
        "category": "Surface Fracture",
    },
    1: {
        "code": "D10",
        "description": "Transverse Crack",
        "severity": "MEDIUM",
        "category": "Surface Fracture",
    },
    2: {
        "code": "D20",
        "description": "Alligator Crack",
        "severity": "HIGH",
        "category": "Structural Fatigue",
    },
    3: {
        "code": "D40",
        "description": "Pothole",
        "severity": "HIGH",
        "category": "Cavity / Loss of Pavement",
    },
}

# Global cache for loaded model instances (keyed by model_path and device)
_MODEL_CACHE: Dict[str, YOLO] = {}


def get_road_damage_detector(
    model_path: Optional[Union[str, Path]] = None,
    device: str = "cpu",
) -> YOLO:
    """Retrieves or loads the finalized YOLO road defect model instance from cache.

    Args:
        model_path: Optional path to weights. Defaults to experiment2_week5/best.pt.
        device: Execution device ('cpu' or 'cuda').

    Returns:
        YOLO: Instantiated and warm Ultralytics model instance.
    """
    resolved_path = Path(model_path) if model_path else _DEFAULT_WEIGHTS_PATH
    if not resolved_path.is_file():
        raise FileNotFoundError(
            f"Finalized model weights not found at: {resolved_path}. "
            f"Ensure Week 5 weights have been downloaded or generated."
        )

    cache_key = f"{resolved_path.as_posix()}_{device}"
    if cache_key not in _MODEL_CACHE:
        model = YOLO(str(resolved_path))
        # Ensure device assignment
        _MODEL_CACHE[cache_key] = model

    return _MODEL_CACHE[cache_key]


def detect_road_damage(
    image_input: Union[str, Path, Image.Image, np.ndarray, Dict[str, Any]],
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    model_path: Optional[Union[str, Path]] = None,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Runs road damage defect detection on an input image using the finalized model.

    Args:
        image_input: An image path (str/Path), PIL Image, OpenCV NumPy array (RGB/BGR),
            or the preprocessed dict returned by `preprocess_report_image()`.
        confidence_threshold: Minimum detection confidence score (default: 0.25).
        iou_threshold: Non-Maximum Suppression (NMS) IoU threshold (default: 0.45).
        model_path: Optional path to model weights override.
        device: Inference device ('cpu' or 'cuda').

    Returns:
        Structured dictionary containing:
            - success (bool): Whether inference completed without error.
            - model_version (str): Canonical model identifier.
            - inference_time_ms (float): Execution duration in milliseconds.
            - original_dimensions (dict): {"width": int, "height": int}.
            - num_detections (int): Total count of detected bounding boxes.
            - primary_damage_type (str): Dominant detected defect code ('D40', 'D20', etc.) or 'NONE'.
            - primary_priority (str): Municipal triage priority ('HIGH', 'MEDIUM', 'LOW').
            - detections (List[dict]): List of structured detection records, each with:
                * class_id (int): 0-3 index.
                * class_name (str): 'D00', 'D10', 'D20', or 'D40'.
                * description (str): Human-readable defect label.
                * confidence (float): Score rounded to 4 decimals.
                * severity (str): 'HIGH' or 'MEDIUM'.
                * bbox (List[float]): [xmin, ymin, xmax, ymax] in original pixel coordinates.
                * bbox_normalized (List[float]): [xmin, ymin, xmax, ymax] scaled to [0.0, 1.0].
    """
    start_time = time.perf_counter()

    # 1. Normalize image source and extract original dimensions
    orig_w: int = 0
    orig_h: int = 0
    prediction_source: Any = None

    if isinstance(image_input, dict) and "preprocessed_np" in image_input:
        # Preprocessed output from Week 4 pipeline
        prediction_source = image_input["preprocessed_np"]
        if "original_shape" in image_input:
            orig_h, orig_w = image_input["original_shape"]
        else:
            orig_h, orig_w = prediction_source.shape[:2]
    elif isinstance(image_input, (str, Path)):
        path_obj = Path(image_input)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Image not found at path: {image_input}")
        prediction_source = str(path_obj)
        # Read header dimensions via PIL to avoid loading full image into RAM twice
        with Image.open(path_obj) as img:
            orig_w, orig_h = img.size
    elif isinstance(image_input, Image.Image):
        orig_w, orig_h = image_input.size
        prediction_source = np.array(image_input.convert("RGB"))
    elif isinstance(image_input, np.ndarray):
        orig_h, orig_w = image_input.shape[:2]
        prediction_source = image_input
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    # 2. Retrieve model
    model = get_road_damage_detector(model_path=model_path, device=device)

    # 3. Execute prediction
    results = model.predict(
        source=prediction_source,
        conf=confidence_threshold,
        iou=iou_threshold,
        device=device,
        verbose=False,
    )

    inference_ms = (time.perf_counter() - start_time) * 1000.0

    # 4. Parse detections
    detections: List[Dict[str, Any]] = []
    has_high_severity = False
    has_medium_severity = False
    class_frequency: Dict[str, int] = {}

    if results and len(results) > 0:
        result = results[0]
        boxes = result.boxes

        # If dimensions were not resolved yet (e.g. from prediction_source directly)
        if orig_w == 0 or orig_h == 0:
            if hasattr(result, "orig_shape"):
                orig_h, orig_w = result.orig_shape

        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls.item())
                conf = float(box.conf.item())
                xyxy = box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]

                meta = CLASS_METADATA.get(
                    cls_id,
                    {
                        "code": f"UNKNOWN_{cls_id}",
                        "description": "Unclassified Damage",
                        "severity": "MEDIUM",
                        "category": "Unknown",
                    },
                )

                class_code = meta["code"]
                severity = meta["severity"]
                if severity == "HIGH":
                    has_high_severity = True
                elif severity == "MEDIUM":
                    has_medium_severity = True

                class_frequency[class_code] = class_frequency.get(class_code, 0) + 1

                # Clamp bounding boxes within original image dimensions
                xmin = max(0.0, min(float(orig_w), xyxy[0]))
                ymin = max(0.0, min(float(orig_h), xyxy[1]))
                xmax = max(0.0, min(float(orig_w), xyxy[2]))
                ymax = max(0.0, min(float(orig_h), xyxy[3]))

                # Calculate normalized [0, 1] relative coordinates
                norm_w = float(orig_w) if orig_w > 0 else 1.0
                norm_h = float(orig_h) if orig_h > 0 else 1.0
                norm_box = [
                    round(xmin / norm_w, 4),
                    round(ymin / norm_h, 4),
                    round(xmax / norm_w, 4),
                    round(ymax / norm_h, 4),
                ]

                detections.append(
                    {
                        "class_id": cls_id,
                        "class_name": class_code,
                        "description": meta["description"],
                        "category": meta["category"],
                        "confidence": round(conf, 4),
                        "severity": severity,
                        "bbox": [round(xmin, 1), round(ymin, 1), round(xmax, 1), round(ymax, 1)],
                        "bbox_normalized": norm_box,
                    }
                )

    # 5. Determine primary damage type and priority level
    if has_high_severity:
        primary_priority = "HIGH"
    elif has_medium_severity:
        primary_priority = "MEDIUM"
    else:
        primary_priority = "LOW"

    # Select primary damage type (prefer D40 or D20 if present, else highest frequency)
    if any(d["class_name"] == "D40" for d in detections):
        primary_damage_type = "D40"
    elif any(d["class_name"] == "D20" for d in detections):
        primary_damage_type = "D20"
    elif detections:
        # Most frequent class
        primary_damage_type = max(class_frequency.items(), key=lambda kv: kv[1])[0]
    else:
        primary_damage_type = "NONE"

    return {
        "success": True,
        "model_version": "YOLOv8n-experiment2_week5",
        "weights_source": str(Path(model_path).name if model_path else _DEFAULT_WEIGHTS_PATH.name),
        "inference_time_ms": round(inference_ms, 2),
        "original_dimensions": {"width": orig_w, "height": orig_h},
        "num_detections": len(detections),
        "primary_damage_type": primary_damage_type,
        "primary_priority": primary_priority,
        "detections": detections,
    }
