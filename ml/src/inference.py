"""CivicSight ML Subsystem — Reusable Road Defect Detection Inference Module (Week 6/9+)

Provides a clean, modular inference interface for the finalized YOLOv8 road damage detection
model (trained on RDD2022). Can be imported and invoked by upstream services, testing scripts,
and background workers.

Delegates core execution and weights resolution to `ml.inference_adapter` while maintaining
exact backwards compatibility with all function signatures, global caches, and metadata dicts.
"""

from typing import Union, Dict, Any, List, Optional
from pathlib import Path
from PIL import Image
import numpy as np
from ultralytics import YOLO

# Import unified components from the inference adapter
from ml.inference_adapter import (
    CLASS_METADATA,
    ModelVersionStr,
    get_model_path,
    get_model_version,
    get_road_damage_detector,
    detect_road_damage,
    run_inference,
    _DEFAULT_WEIGHTS_PATH,
    _MODEL_CACHE,
)

__all__ = [
    "CLASS_METADATA",
    "ModelVersionStr",
    "get_model_path",
    "get_model_version",
    "get_road_damage_detector",
    "detect_road_damage",
    "run_inference",
    "_DEFAULT_WEIGHTS_PATH",
    "_MODEL_CACHE",
]
