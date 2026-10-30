"""CivicSight Priority Engine (Week 8)

Isolated, pure scoring and triage engine with zero database or HTTP dependencies.
Fully deterministic, explainable, and configurable via PriorityConfig.

Evaluates:
- Worst ML detection (class weight, confidence, relative bbox area)
- ML pipeline state (ML_COMPLETE, ML_NO_DETECTIONS, ML_PENDING, ML_FAILED)
- Proximity / repeated reports count
- Persistence / age of unresolved report
- Optional location risk factor
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PriorityConfig:
    """Configurable scoring weights, thresholds, and limits for the priority engine."""

    # Damage class weights: D40 (pothole) highest, D20 (alligator) high,
    # D10 (transverse) medium, D00 (longitudinal) low-medium
    class_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "D40": 1.00,  # Pothole
            "D20": 0.85,  # Alligator Crack
            "D10": 0.55,  # Transverse Crack
            "D00": 0.40,  # Longitudinal Crack
        }
    )

    class_labels: Dict[str, str] = field(
        default_factory=lambda: {
            "D40": "Pothole",
            "D20": "Alligator cracking",
            "D10": "Transverse crack",
            "D00": "Longitudinal crack",
        }
    )

    # Minimum detection confidence threshold (detections below this are ignored)
    min_confidence: float = 0.25

    # Severity score thresholds (worst detection score mapping)
    high_severity_threshold: float = 0.55
    medium_severity_threshold: float = 0.28

    # Priority composite score thresholds (out of 100)
    high_priority_score_threshold: float = 60.0
    medium_priority_score_threshold: float = 30.0

    # Optional aliases
    high_score_threshold: Optional[float] = None
    medium_score_threshold: Optional[float] = None

    def __post_init__(self):
        if self.high_score_threshold is not None:
            self.high_priority_score_threshold = self.high_score_threshold
        if self.medium_score_threshold is not None:
            self.medium_priority_score_threshold = self.medium_score_threshold

    # Repeated reports thresholds (elevate priority directly)
    high_priority_nearby_count: int = 4
    medium_priority_nearby_count: int = 2

    # Score component maximum points and rates
    points_per_nearby_report: float = 7.5
    max_nearby_points: float = 30.0

    points_per_day_age: float = 1.0
    max_age_points: float = 15.0

    max_location_risk_points: float = 5.0
    max_damage_points: float = 50.0

    damage_score_high: float = 45.0
    damage_score_medium: float = 28.0
    damage_score_low: float = 14.0
    damage_score_unknown: float = 10.0

    @classmethod
    def from_env(cls) -> "PriorityConfig":
        """Builds a PriorityConfig instance with optional environment variable overrides."""
        cfg = cls()
        if "PRIORITY_MIN_CONFIDENCE" in os.environ:
            try:
                cfg.min_confidence = float(os.environ["PRIORITY_MIN_CONFIDENCE"])
            except ValueError:
                pass
        if "PRIORITY_HIGH_SEVERITY_THRESHOLD" in os.environ:
            try:
                cfg.high_severity_threshold = float(os.environ["PRIORITY_HIGH_SEVERITY_THRESHOLD"])
            except ValueError:
                pass
        if "PRIORITY_MEDIUM_SEVERITY_THRESHOLD" in os.environ:
            try:
                cfg.medium_severity_threshold = float(os.environ["PRIORITY_MEDIUM_SEVERITY_THRESHOLD"])
            except ValueError:
                pass
        if "PRIORITY_HIGH_SCORE_THRESHOLD" in os.environ:
            try:
                cfg.high_priority_score_threshold = float(os.environ["PRIORITY_HIGH_SCORE_THRESHOLD"])
            except ValueError:
                pass
        if "PRIORITY_MEDIUM_SCORE_THRESHOLD" in os.environ:
            try:
                cfg.medium_priority_score_threshold = float(os.environ["PRIORITY_MEDIUM_SCORE_THRESHOLD"])
            except ValueError:
                pass
        if "PRIORITY_HIGH_NEARBY_COUNT" in os.environ:
            try:
                cfg.high_priority_nearby_count = int(os.environ["PRIORITY_HIGH_NEARBY_COUNT"])
            except ValueError:
                pass
        if "PRIORITY_MEDIUM_NEARBY_COUNT" in os.environ:
            try:
                cfg.medium_priority_nearby_count = int(os.environ["PRIORITY_MEDIUM_NEARBY_COUNT"])
            except ValueError:
                pass
        return cfg


DEFAULT_CONFIG = PriorityConfig()


def compute_relative_bbox_area(bbox: Any) -> float:
    """Computes relative bounding box area in normalized coordinates [0.0, 1.0]."""
    if not bbox or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return 0.08  # Default modest area factor

    try:
        # Check if coordinates are normalized [0..1]
        c0, c1, c2, c3 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        # Accommodate both [xmin, ymin, xmax, ymax] and [ymin, xmin, ymax, xmax]
        width = abs(c2 - c0)
        height = abs(c3 - c1)

        # If pixel coords (> 1.0), normalize to a representative ratio
        if width > 1.0 or height > 1.0:
            width = min(1.0, max(0.01, width / 640.0))
            height = min(1.0, max(0.01, height / 640.0))

        area = width * height
        return max(0.01, min(1.0, area))
    except Exception:
        return 0.08


def calculate_severity(
    detections: Optional[List[Dict[str, Any]]] = None,
    ml_status: Optional[str] = None,
    config: Optional[PriorityConfig] = None,
    cfg: Optional[PriorityConfig] = None,
) -> Tuple[str, float, List[str]]:
    """Derives severity (HIGH, MEDIUM, LOW, UNKNOWN) from the worst detection present.

    Returns:
        (severity_str, worst_score, reasons_list)
    """
    effective_cfg = cfg or config or DEFAULT_CONFIG
    reasons: List[str] = []

    # Handle missing or pending ML inference
    status_clean = (ml_status or "").strip().upper()
    if status_clean in ("ML_FAILED", "ML_PENDING"):
        reasons.append("Automated assessment unavailable")
        return "UNKNOWN", 0.0, reasons

    if status_clean == "ML_NO_DETECTIONS":
        reasons.append("No road damage detected by automated assessment")
        return "LOW", 0.0, reasons

    if not detections:
        # If ML reported complete but no detections were in the array
        if status_clean == "ML_COMPLETE":
            reasons.append("No road damage detected by automated assessment")
            return "LOW", 0.0, reasons
        reasons.append("Automated assessment unavailable")
        return "UNKNOWN", 0.0, reasons

    valid_scored_detections: List[Tuple[float, str, float, float, Dict[str, Any]]] = []
    ignored_low_conf_count = 0

    for det in detections:
        # Extract class code from 'class', 'class_name', 'type', or 'detected_class'
        raw_class = (
            det.get("class")
            or det.get("class_name")
            or det.get("type")
            or det.get("detected_class")
            or "D00"
        )
        class_code = str(raw_class).strip().upper()

        # Validate confidence explicitly (must be float between 0 and 1)
        raw_conf = det.get("confidence")
        if raw_conf is None:
            reasons.append(f"Ignored detection ({class_code}) with missing confidence")
            continue

        try:
            conf = float(raw_conf)
        except (ValueError, TypeError):
            reasons.append(f"Ignored detection ({class_code}) with invalid non-numeric confidence")
            continue

        if conf < 0.0 or conf > 1.0:
            reasons.append(f"Ignored detection ({class_code}) with unreliable out-of-range confidence ({conf})")
            continue

        # Filter below minimum confidence
        if conf < effective_cfg.min_confidence:
            ignored_low_conf_count += 1
            continue

        # Relative bounding box area factor
        if "bbox_area" in det and det["bbox_area"] is not None:
            area = float(det["bbox_area"])
        else:
            bbox = det.get("bbox_normalized") or det.get("bbox") or det.get("bbox_pixels")
            area = compute_relative_bbox_area(bbox)

        # Detection scoring formula
        class_weight = effective_cfg.class_weights.get(class_code, 0.40)
        # 75% confidence, 25% area factor
        det_score = class_weight * (0.75 * conf + 0.25 * min(1.0, area * 3.0))

        valid_scored_detections.append((det_score, class_code, conf, area, det))

    if ignored_low_conf_count > 0:
        reasons.append(
            f"{ignored_low_conf_count} detection(s) below minimum confidence ({effective_cfg.min_confidence:.0%}) ignored"
        )

    if not valid_scored_detections:
        reasons.append("Low model confidence, priority based on citizen reports only")
        return "LOW", 0.0, reasons

    # Sort descending by detection score to find the worst damage
    valid_scored_detections.sort(key=lambda x: x[0], reverse=True)
    worst_score, worst_class, worst_conf, worst_area, _ = valid_scored_detections[0]

    label = effective_cfg.class_labels.get(worst_class, f"Defect {worst_class}")
    reasons.append(f"{label} detected at {int(round(worst_conf * 100))}% confidence")

    if worst_score >= effective_cfg.high_severity_threshold:
        return "HIGH", worst_score, reasons
    elif worst_score >= effective_cfg.medium_severity_threshold:
        return "MEDIUM", worst_score, reasons
    else:
        return "LOW", worst_score, reasons


def calculate_priority(
    detections: Optional[List[Dict[str, Any]]] = None,
    ml_status: Optional[str] = None,
    nearby_report_count: int = 0,
    report_age_days: float = 0.0,
    location_risk: Optional[float] = None,
    has_valid_coordinates: bool = True,
    nearby_distance_meters: float = 50.0,
    config: Optional[PriorityConfig] = None,
    cfg: Optional[PriorityConfig] = None,
) -> Dict[str, Any]:
    """Pure, deterministic road hazard priority scoring engine.

    Inputs:
        detections: List of detection dictionaries (class_name, confidence, bbox)
        ml_status: ML lifecycle status ('ML_COMPLETE', 'ML_PENDING', 'ML_NO_DETECTIONS', 'ML_FAILED')
        nearby_report_count: Number of non-rejected reports within proximity distance
        report_age_days: Elapsed days since report creation
        location_risk: Optional float (0.0 to 1.0) indicating traffic density/infrastructure hazard
        has_valid_coordinates: Flag indicating if report coordinates were valid for GIS analysis
        nearby_distance_meters: Proximity radius in meters for human-readable reasons
        config: Optional PriorityConfig override (defaults to environment or standard values)
        cfg: Optional alias for config

    Returns:
        dict: {
            "severity": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
            "priority": "HIGH" | "MEDIUM" | "LOW",
            "score": float (0.0 to 100.0),
            "reasons": List[str] (human-readable explainability list)
        }
    """
    effective_cfg = cfg or config or DEFAULT_CONFIG
    cfg = effective_cfg
    all_reasons: List[str] = []

    # 1. Coordinate check
    if not has_valid_coordinates:
        all_reasons.append("Invalid or missing coordinates: proximity analysis skipped")
        nearby_report_count = 0

    # 2. Derive Severity and ML explainability
    severity, worst_score, severity_reasons = calculate_severity(
        detections=detections,
        ml_status=ml_status,
        config=cfg,
    )
    all_reasons.extend(severity_reasons)

    # 3. Component Scores
    # Damage Component (0 - 50 points)
    if severity == "HIGH":
        damage_pts = cfg.damage_score_high + min(5.0, worst_score * 5.0)
    elif severity == "MEDIUM":
        damage_pts = cfg.damage_score_medium + min(7.0, worst_score * 8.0)
    elif severity == "LOW":
        damage_pts = cfg.damage_score_low + min(6.0, worst_score * 8.0)
    else:  # UNKNOWN
        damage_pts = cfg.damage_score_unknown

    # Proximity Component (0 - 30 points)
    safe_nearby_count = max(0, int(nearby_report_count))
    nearby_pts = min(cfg.max_nearby_points, safe_nearby_count * cfg.points_per_nearby_report)
    if safe_nearby_count > 0:
        dist_label = int(round(nearby_distance_meters))
        plural_suffix = "s" if safe_nearby_count != 1 else ""
        all_reasons.append(f"{safe_nearby_count} other report{plural_suffix} within {dist_label} m")

    # Persistence / Age Component (0 - 15 points)
    safe_age_days = max(0.0, float(report_age_days))
    age_pts = min(cfg.max_age_points, safe_age_days * cfg.points_per_day_age)
    if safe_age_days >= 1.0:
        all_reasons.append(f"Open for {int(safe_age_days)} days without resolution")

    # Location Risk Component (0 - 5 points)
    loc_pts = 0.0
    if location_risk is not None:
        try:
            val = float(location_risk)
            clamped_risk = max(0.0, min(1.0, val))
            loc_pts = round(clamped_risk * cfg.max_location_risk_points, 1)
            all_reasons.append(f"Location risk factor applied ({loc_pts:.1f} pts)")
        except (ValueError, TypeError):
            pass

    # Composite Score calculation
    total_score = round(min(100.0, max(0.0, damage_pts + nearby_pts + age_pts + loc_pts)), 2)

    # 4. Priority Triage Rules
    # Rule 1: High Priority:
    # - Severe damage (confident pothole or alligator cracking), OR
    # - Recurring hazard confirmed by several repeated reports (>= 4), OR
    # - Composite score exceeds high threshold (>= 60)
    is_high = (
        severity == "HIGH"
        or safe_nearby_count >= cfg.high_priority_nearby_count
        or total_score >= cfg.high_priority_score_threshold
    )

    # Rule 2: Medium Priority:
    # - Moderate damage (transverse/longitudinal cracks), OR
    # - Multiple reports suggesting recurring issue (>= 2), OR
    # - Composite score exceeds medium threshold (>= 30)
    is_medium = (
        severity == "MEDIUM"
        or safe_nearby_count >= cfg.medium_priority_nearby_count
        or total_score >= cfg.medium_priority_score_threshold
    )

    if is_high:
        priority = "HIGH"
        if severity != "HIGH" and safe_nearby_count >= cfg.high_priority_nearby_count:
            all_reasons.append("Recurring hazard confirmed by several repeated reports")
    elif is_medium:
        priority = "MEDIUM"
        if severity == "LOW" and safe_nearby_count >= cfg.medium_priority_nearby_count:
            all_reasons.append("Multiple reports suggesting a recurring issue")
    else:
        priority = "LOW"
        if (ml_status or "").strip().upper() in ("ML_FAILED", "ML_PENDING"):
            all_reasons.append("Priority based on citizen reports and persistence only")
        elif safe_nearby_count == 0 and safe_age_days < 2.0:
            all_reasons.append("Minor damage with little evidence of urgency")

    # Guarantee non-empty explainability list
    if not all_reasons:
        all_reasons.append("Standard initial assessment based on single report")

    return {
        "severity": severity,
        "priority": priority,
        "score": total_score,
        "reasons": all_reasons,
    }
