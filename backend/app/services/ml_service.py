"""CivicSight ML Pipeline Service (Week 7 Prototype Integration)

Orchestrates end-to-end integration between FastAPI report ingestion and
the finalized YOLOv8n road defect detection subsystem:
1. Reuses Week 4 preprocessing pipeline (ml.src.preprocess.preprocess_report_image)
2. Reuses Week 6 finalized inference module (ml.src.inference.detect_road_damage)
3. Persists detection findings in detection_results table (1:N relationship with reports)
4. Manages explicit lifecycle states: ML_PENDING, ML_COMPLETE, ML_NO_DETECTIONS, ML_FAILED
5. Enforces zero-failure policy: ML exceptions or timeouts never crash report creation
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.models import Report, DetectionResult

logger = logging.getLogger("civicsight.ml_service")

# Resolve project root and ensure imports from ml package succeed
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Canonical model identifiers
DEFAULT_MODEL_VERSION = "YOLOv8n-experiment2_week5"
INFERENCE_TIMEOUT_SECONDS = 12.0


def resolve_image_disk_path(image_url: Optional[str]) -> Optional[Path]:
    """Resolves a report's stored image_url string to an existing Path on disk.
    
    Handles relative paths (/uploads/reports/...), disk paths, and URL patterns.
    """
    if not image_url or not str(image_url).strip():
        return None

    cleaned = str(image_url).strip()

    # If it's a URL with hostname, extract the path part
    if "://" in cleaned:
        from urllib.parse import urlparse
        cleaned = urlparse(cleaned).path

    # Remove leading slash for local joining
    rel_path = cleaned.lstrip("/\\")

    # Candidate 1: relative to backend directory (e.g. backend/uploads/reports/...)
    p1 = BACKEND_DIR / rel_path
    if p1.is_file():
        return p1

    # Candidate 2: relative to project root
    p2 = PROJECT_ROOT / rel_path
    if p2.is_file():
        return p2

    # Candidate 3: direct absolute path
    p3 = Path(cleaned)
    if p3.is_file():
        return p3

    return None


def run_ml_inference_guarded(image_path: Path, timeout_seconds: float = INFERENCE_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Executes Week 4 preprocessing and Week 6 YOLO inference inside a guarded thread with strict timeout.
    
    Raises:
        FileNotFoundError: If model weights or image file cannot be accessed.
        ValueError / TypeError: If image data is invalid or corrupt.
        FutureTimeoutError: If execution exceeds timeout_seconds.
        Exception: Any runtime inference errors.
    """
    from ml.src.preprocess import preprocess_report_image
    from ml.src.inference import detect_road_damage

    def _execute() -> Dict[str, Any]:
        # Step 1: Preprocess using Week 4 module
        preprocessed = preprocess_report_image(image_path)

        # Step 2: Run inference using Week 6 finalized model
        result = detect_road_damage(preprocessed, confidence_threshold=0.10)
        return result

    # Execute within ThreadPoolExecutor to prevent long hangs
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_execute)
        return future.result(timeout=timeout_seconds)


def process_report_image_ml(
    report_id: int,
    db: Optional[Session] = None,
    timeout_seconds: float = INFERENCE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Processes a report's attached photo through the complete ML pipeline and stores results.
    
    Can be invoked synchronously or via FastAPI BackgroundTasks.
    Guarantees that database records are updated to one of:
      - ML_COMPLETE: Model detected road damage, records created in detection_results
      - ML_NO_DETECTIONS: Model executed normally, 0 defects detected
      - ML_FAILED: Image missing/corrupt, model load failure, or timeout
    
    Returns:
        Dict summarising processing outcome and status.
    """
    managed_session = False
    if db is None:
        db = SessionLocal()
        managed_session = True

    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            logger.warning(f"[ML Pipeline] Report #{report_id} not found in database.")
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": "Report not found"}

        # Check for image URL
        if not report.image_url:
            report.ml_status = "ML_FAILED"
            report.ml_error_message = "No photo attached to report"
            report.ml_processed_at = datetime.utcnow()
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": report.ml_error_message}

        # Resolve image file on disk
        disk_path = resolve_image_disk_path(report.image_url)
        if not disk_path or not disk_path.is_file():
            err_msg = f"Attached image file not found on server disk: {report.image_url}"
            logger.warning(f"[ML Pipeline] {err_msg} for Report #{report_id}")
            report.ml_status = "ML_FAILED"
            report.ml_error_message = err_msg
            report.ml_processed_at = datetime.utcnow()
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": err_msg}

        logger.info(f"[ML Pipeline] Running YOLO damage triage on Report #{report_id} (image: {disk_path.name})...")

        # Execute guarded inference
        try:
            inference_output = run_ml_inference_guarded(disk_path, timeout_seconds=timeout_seconds)
        except FutureTimeoutError:
            err_msg = f"ML inference timed out after {timeout_seconds:.1f} seconds"
            logger.error(f"[ML Pipeline] Report #{report_id}: {err_msg}")
            report.ml_status = "ML_FAILED"
            report.ml_error_message = err_msg
            report.ml_processed_at = datetime.utcnow()
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": err_msg}
        except Exception as e:
            err_msg = f"Inference processing error: {str(e)}"
            logger.error(f"[ML Pipeline] Report #{report_id} failed: {err_msg}", exc_info=True)
            report.ml_status = "ML_FAILED"
            report.ml_error_message = err_msg
            report.ml_processed_at = datetime.utcnow()
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": err_msg}

        # Clear any prior detection results for this report if re-running
        db.query(DetectionResult).filter(DetectionResult.report_id == report_id).delete()

        raw_detections = inference_output.get("detections", [])
        model_version = inference_output.get("model_version", DEFAULT_MODEL_VERSION)
        inference_time_ms = inference_output.get("inference_time_ms", 0.0)
        primary_damage = inference_output.get("primary_damage_type", "NONE")
        primary_priority = inference_output.get("primary_priority", "LOW")

        now = datetime.utcnow()
        report.ml_model_version = model_version
        report.ml_inference_time_ms = inference_time_ms
        report.ml_processed_at = now
        report.ml_error_message = None

        if len(raw_detections) == 0:
            # Case: Zero detections returned (valid, different from failure)
            logger.info(f"[ML Pipeline] Report #{report_id}: 0 defects detected. Marked as ML_NO_DETECTIONS.")
            report.ml_status = "ML_NO_DETECTIONS"
            report.ml_detections = "[]"
            db.commit()
            db.refresh(report)
            return {
                "success": True,
                "report_id": report_id,
                "ml_status": "ML_NO_DETECTIONS",
                "num_detections": 0,
                "inference_time_ms": inference_time_ms,
            }

        # Case: Detections found -> Store ALL detections
        stored_detections: List[Dict[str, Any]] = []
        for det in raw_detections:
            cls_code = det.get("class_name", "OTHER")
            cls_desc = det.get("description", det.get("class_name", "Defect"))
            conf = float(det.get("confidence", 0.0))
            severity = det.get("severity", "MEDIUM")
            bbox_px = det.get("bbox", [0.0, 0.0, 0.0, 0.0])  # [xmin, ymin, xmax, ymax]
            bbox_norm = det.get("bbox_normalized", [0.0, 0.0, 0.0, 0.0])  # [xmin_norm, ymin_norm, xmax_norm, ymax_norm]

            # Invert norm_box to [ymin, xmin, ymax, xmax] for frontend ml-viewer convention
            if len(bbox_norm) == 4:
                frontend_norm = [bbox_norm[1], bbox_norm[0], bbox_norm[3], bbox_norm[2]]
            else:
                frontend_norm = bbox_norm

            det_row = DetectionResult(
                report_id=report.id,
                detected_class=cls_code,
                class_name=cls_desc,
                confidence=conf,
                bbox_xmin=bbox_px[0],
                bbox_ymin=bbox_px[1],
                bbox_xmax=bbox_px[2],
                bbox_ymax=bbox_px[3],
                bbox_normalized=json.dumps(frontend_norm),
                severity=severity,
                model_version=model_version,
                inference_timestamp=now,
            )
            db.add(det_row)

            stored_detections.append({
                "type": cls_code,
                "label": cls_desc,
                "confidence": conf,
                "severity": severity,
                "bbox": frontend_norm,
                "bbox_pixels": bbox_px,
            })

        report.ml_status = "ML_COMPLETE"
        report.ml_detections = json.dumps(stored_detections)

        # Smart classification enrichment:
        # If the report didn't have a specific damage type set (or was OTHER), update with primary detected type
        if not report.damage_type or report.damage_type.upper() in ["OTHER", "NONE", "UNSURE"]:
            if primary_damage and primary_damage != "NONE":
                report.damage_type = primary_damage

        # If report priority is still default MEDIUM and AI identified a HIGH severity hazard (e.g. Pothole / D40),
        # elevate the initial triage recommendation
        if report.priority in ["MEDIUM", "LOW"] and primary_priority == "HIGH":
            report.priority = "HIGH"

        db.commit()
        db.refresh(report)

        logger.info(
            f"[ML Pipeline] Report #{report_id} complete: {len(raw_detections)} detections stored "
            f"in {inference_time_ms:.1f}ms. Marked ML_COMPLETE."
        )
        return {
            "success": True,
            "report_id": report_id,
            "ml_status": "ML_COMPLETE",
            "num_detections": len(raw_detections),
            "primary_damage_type": primary_damage,
            "primary_priority": primary_priority,
            "inference_time_ms": inference_time_ms,
        }

    finally:
        if managed_session:
            db.close()
