"""CivicSight ML Subsystem — Road Damage Defect Detection Inference Module

Provides a clean, modular inference interface for the 4-class YOLOv8 road defect detection model:
  * D00 (0): Longitudinal Crack (MEDIUM severity)
  * D10 (1): Transverse Crack (MEDIUM severity)
  * D20 (2): Alligator Crack (HIGH severity)
  * D40 (3): Pothole (HIGH severity)

Guarantees:
- Genuine model detections without fabrication or hardcoded biases.
- Clean roads / empty detections explicitly produce 0 detections (primary_damage_type: 'NONE').
- Single source of truth for RDD2022 4-class taxonomy across backend and frontend.
- Bounding boxes accurately mapped to original uploaded image coordinate space.
"""

from typing import Union, Dict, Any, List, Optional
from pathlib import Path
import time
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

# Project root resolution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Ordered candidate paths for best model weights
_WEIGHTS_CANDIDATES = [
    _PROJECT_ROOT / "ml" / "runs" / "detect" / "civicsight_yolov8n_4class" / "weights" / "best.pt",
    _PROJECT_ROOT / "ml" / "runs" / "detect" / "experiment2_week5" / "weights" / "best.pt",
    _PROJECT_ROOT / "ml" / "weights" / "best.pt",
    _PROJECT_ROOT / "best.pt",
    _PROJECT_ROOT / "yolov8n.pt",
]

# Standardized 4-Class Taxonomy & Severity Grading
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

# Global model cache to avoid reloading weights repeatedly
_MODEL_CACHE: Dict[str, YOLO] = {}


def resolve_model_weights_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Finds the first existing model weights checkpoint."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Specified model weights not found at: {custom_path}")

    for candidate in _WEIGHTS_CANDIDATES:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"No valid model weights found in candidate paths. "
        f"Please ensure training has run or weights are placed in ml/runs/detect/."
    )


def get_road_damage_detector(
    model_path: Optional[Union[str, Path]] = None,
    device: str = "cpu",
) -> YOLO:
    """Retrieves or loads the YOLO road defect model instance from cache."""
    resolved_path = resolve_model_weights_path(model_path)
    cache_key = f"{resolved_path.as_posix()}_{device}"

    if cache_key not in _MODEL_CACHE:
        model = YOLO(str(resolved_path))
        _MODEL_CACHE[cache_key] = model

    return _MODEL_CACHE[cache_key]


def detect_road_damage(
    image_input: Union[str, Path, Image.Image, np.ndarray, Dict[str, Any]],
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    model_path: Optional[Union[str, Path]] = None,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Runs road damage defect detection on an input image.

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
            - detections (List[dict]): List of structured detection records.
    """
    start_time = time.perf_counter()

    # 1. Normalize image source and extract original dimensions
    orig_w: int = 0
    orig_h: int = 0
    pad_w: float = 0.0
    pad_h: float = 0.0
    scale_ratio: float = 1.0
    is_preprocessed_dict: bool = False
    prediction_source: Any = None

    try:
        if isinstance(image_input, dict) and "preprocessed_np" in image_input:
            padded_rgb = image_input["preprocessed_np"]
            prediction_source = cv2.cvtColor(padded_rgb, cv2.COLOR_RGB2BGR)
            is_preprocessed_dict = True
            if "original_shape" in image_input:
                orig_h, orig_w = image_input["original_shape"]
            else:
                orig_h, orig_w = padded_rgb.shape[:2]
            if "padding" in image_input:
                pad_w, pad_h = image_input["padding"]
            if "scale_ratio" in image_input:
                scale_ratio = float(image_input["scale_ratio"])
        elif isinstance(image_input, (str, Path)):
            path_obj = Path(image_input)
            if not path_obj.is_file():
                return {
                    "success": False,
                    "error": f"Image file not found: {image_input}",
                    "num_detections": 0,
                    "detections": [],
                    "primary_damage_type": "NONE",
                    "primary_priority": "LOW",
                }
            prediction_source = str(path_obj)
            with Image.open(path_obj) as img:
                orig_w, orig_h = img.size
        elif isinstance(image_input, Image.Image):
            orig_w, orig_h = image_input.size
            prediction_source = cv2.cvtColor(np.array(image_input.convert("RGB")), cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            orig_h, orig_w = image_input.shape[:2]
            prediction_source = image_input
        else:
            return {
                "success": False,
                "error": f"Unsupported image input type: {type(image_input)}",
                "num_detections": 0,
                "detections": [],
                "primary_damage_type": "NONE",
                "primary_priority": "LOW",
            }

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

            if orig_w == 0 or orig_h == 0:
                if hasattr(result, "orig_shape"):
                    orig_h, orig_w = result.orig_shape

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_id = int(box.cls.item())
                    conf = float(box.conf.item())
                    xyxy = box.xyxy[0].tolist()

                    meta = CLASS_METADATA.get(
                        cls_id,
                        {
                            "code": f"D{cls_id}",
                            "description": "Road Defect",
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

                    if is_preprocessed_dict and scale_ratio > 0:
                        raw_xmin = (xyxy[0] - pad_w) / scale_ratio
                        raw_ymin = (xyxy[1] - pad_h) / scale_ratio
                        raw_xmax = (xyxy[2] - pad_w) / scale_ratio
                        raw_ymax = (xyxy[3] - pad_h) / scale_ratio
                    else:
                        raw_xmin, raw_ymin, raw_xmax, raw_ymax = xyxy[0], xyxy[1], xyxy[2], xyxy[3]

                    # Clamp bounding boxes within original dimensions
                    xmin = max(0.0, min(float(orig_w), raw_xmin))
                    ymin = max(0.0, min(float(orig_h), raw_ymin))
                    xmax = max(0.0, min(float(orig_w), raw_xmax))
                    ymax = max(0.0, min(float(orig_h), raw_ymax))

                    # Normalized [0, 1] relative coordinates
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
        if not detections:
            primary_priority = "LOW"
            primary_damage_type = "NONE"
        else:
            if has_high_severity:
                primary_priority = "HIGH"
            elif has_medium_severity:
                primary_priority = "MEDIUM"
            else:
                primary_priority = "LOW"

            # Primary damage selection: D40 > D20 > D10 > D00 or highest frequency
            if any(d["class_name"] == "D40" for d in detections):
                primary_damage_type = "D40"
            elif any(d["class_name"] == "D20" for d in detections):
                primary_damage_type = "D20"
            elif any(d["class_name"] == "D10" for d in detections):
                primary_damage_type = "D10"
            elif any(d["class_name"] == "D00" for d in detections):
                primary_damage_type = "D00"
            else:
                primary_damage_type = max(class_frequency.items(), key=lambda kv: kv[1])[0]

        resolved_w_name = Path(resolve_model_weights_path(model_path)).name

        return {
            "success": True,
            "model_version": "YOLOv8n-CivicSight-4Class",
            "weights_source": resolved_w_name,
            "inference_time_ms": round(inference_ms, 2),
            "original_dimensions": {"width": orig_w, "height": orig_h},
            "num_detections": len(detections),
            "primary_damage_type": primary_damage_type,
            "primary_priority": primary_priority,
            "detections": detections,
        }

    except Exception as e:
        inference_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": False,
            "error": str(e),
            "inference_time_ms": round(inference_ms, 2),
            "num_detections": 0,
            "detections": [],
            "primary_damage_type": "NONE",
            "primary_priority": "LOW",
        }
