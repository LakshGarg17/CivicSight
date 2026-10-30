"""CivicSight ML Pipeline Service (Week 7 Prototype Integration)

Orchestrates end-to-end integration between FastAPI report ingestion and
the finalized YOLOv8n 4-class road defect detection subsystem:
1. Preprocessing pipeline (ml.src.preprocess.preprocess_report_image)
2. Finalized inference module (ml.src.inference.detect_road_damage)
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
DEFAULT_MODEL_VERSION = "YOLOv8n-CivicSight-4Class"
INFERENCE_TIMEOUT_SECONDS = 30.0


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


def run_ml_inference_guarded(
    image_path: Path,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    timeout_seconds: float = INFERENCE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Executes preprocessing and YOLO inference inside a guarded thread with strict timeout."""
    from ml.src.preprocess import preprocess_report_image
    from ml.src.inference import detect_road_damage

    def _execute() -> Dict[str, Any]:
        # Step 1: Preprocess using module
        preprocessed = preprocess_report_image(image_path)

        # Step 2: Run inference using 4-class model with validated confidence threshold
        result = detect_road_damage(
            preprocessed,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
        )
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
    
    Guarantees that database records are updated to one of:
      - ML_COMPLETE: Model detected road damage, records created in detection_results
      - ML_NO_DETECTIONS: Model executed normally, 0 defects detected
      - ML_FAILED: Image missing/corrupt, model load failure, or timeout
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
            from app.services.proximity import process_report_proximity
            process_report_proximity(report, db, recalculate_neighbors=False)
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
            from app.services.proximity import process_report_proximity
            process_report_proximity(report, db, recalculate_neighbors=False)
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": err_msg}

        logger.info(f"[ML Pipeline] Running YOLO damage triage on Report #{report_id} (image: {disk_path.name})...")

        # Execute guarded inference
        try:
            inference_output = run_ml_inference_guarded(disk_path, timeout_seconds=timeout_seconds)
            if not inference_output.get("success", False):
                raise RuntimeError(inference_output.get("error", "Inference reported failure"))
        except FutureTimeoutError:
            err_msg = f"ML inference timed out after {timeout_seconds:.1f} seconds"
            logger.error(f"[ML Pipeline] Report #{report_id}: {err_msg}")
            report.ml_status = "ML_FAILED"
            report.ml_error_message = err_msg
            report.ml_processed_at = datetime.utcnow()
            from app.services.proximity import process_report_proximity
            process_report_proximity(report, db, recalculate_neighbors=False)
            db.commit()
            return {"success": False, "report_id": report_id, "ml_status": "ML_FAILED", "error": err_msg}
        except Exception as e:
            err_msg = f"Inference processing error: {str(e)}"
            logger.error(f"[ML Pipeline] Report #{report_id} failed: {err_msg}", exc_info=True)
            report.ml_status = "ML_FAILED"
            report.ml_error_message = err_msg
            report.ml_processed_at = datetime.utcnow()
            from app.services.proximity import process_report_proximity
            process_report_proximity(report, db, recalculate_neighbors=False)
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

        from app.services.proximity import process_report_proximity

        if len(raw_detections) == 0:
            # Case: Zero detections returned (clean road surface)
            logger.info(f"[ML Pipeline] Report #{report_id}: 0 defects detected. Marked as ML_NO_DETECTIONS.")
            report.ml_status = "ML_NO_DETECTIONS"
            report.ml_detections = "[]"
            process_report_proximity(report, db, recalculate_neighbors=True)
            db.commit()
            db.refresh(report)
            return {
                "success": True,
                "report_id": report_id,
                "ml_status": "ML_NO_DETECTIONS",
                "num_detections": 0,
                "primary_damage_type": "NONE",
                "primary_priority": report.priority or "LOW",
                "inference_time_ms": inference_time_ms,
            }

        # Case: Detections found -> Store genuine detections
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
        # If citizen report didn't have specific damage type, update with dominant detected type
        if not report.damage_type or report.damage_type.upper() in ["OTHER", "NONE", "UNSURE"]:
            if primary_damage and primary_damage != "NONE":
                report.damage_type = primary_damage

        # Run Week 8 Priority Engine & Proximity Analysis
        process_report_proximity(report, db, recalculate_neighbors=True)
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
