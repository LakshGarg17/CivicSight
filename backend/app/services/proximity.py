"""CivicSight Proximity & Spatial Duplicate Detection Service (Week 8)

Handles:
- Haversine great-circle distance calculation
- Lat/Lng bounding box spatial prefiltering
- Identification of POTENTIAL_DUPLICATE vs NEARBY_RELATED reports
- Prevention of self-relations and duplicate unordered pairs
- Synchronous and asynchronous nearby report count updates
- Cascading priority recalculation with loop-guards and audit history
- Non-blocking error handling
"""

import math
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.core.config import settings
from app.models.models import Report, ReportStatus, ReportRelation, PriorityHistory
from app.services.priority import calculate_priority, PriorityConfig

logger = logging.getLogger("civicsight.proximity")

# Earth radius in meters
EARTH_RADIUS_METERS = 6371000.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two GPS coordinates in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def get_bounding_box(lat: float, lon: float, distance_meters: float) -> Tuple[float, float, float, float]:
    """Returns (min_lat, max_lat, min_lon, max_lon) for prefiltering database candidates."""
    delta_lat = distance_meters / 111139.0
    rad_lat = math.radians(lat)
    cos_lat = math.cos(rad_lat)
    if abs(cos_lat) < 1e-6:
        delta_lon = 180.0
    else:
        delta_lon = distance_meters / (111139.0 * abs(cos_lat))

    return (
        max(-90.0, lat - delta_lat),
        min(90.0, lat + delta_lat),
        max(-180.0, lon - delta_lon),
        min(180.0, lon + delta_lon),
    )


def are_damage_classes_similar(class1: Optional[str], class2: Optional[str]) -> bool:
    """Determines whether two reported defect classes represent the same or similar damage category.
    
    Rules:
    - Identical class code (e.g. both D40, both D10, etc.) -> Similar
    - Similar crack families (e.g. D00 longitudinal and D10 transverse) -> Similar
    - Pothole (D40) vs Crack (D00, D10, D20) -> NOT similar
    - Null / unknown / general types -> NOT similar (treated as distinct)
    """
    if not class1 or not class2:
        return False

    c1 = class1.strip().upper()
    c2 = class2.strip().upper()

    if c1 == c2:
        return True

    crack_classes = {"D00", "D10"}
    if c1 in crack_classes and c2 in crack_classes:
        return True

    return False


def evaluate_image_similarity(report_a: Report, report_b: Report) -> bool:
    """Optional extension point for perceptual hash or feature embedding image comparison."""
    if not settings.IMAGE_SIMILARITY_ENABLED:
        return False
    # Pluggable extension: e.g. pHash or ResNet embeddings
    return False


def is_valid_coordinate(lat: Optional[float], lon: Optional[float]) -> bool:
    """Checks whether latitude and longitude are valid non-null GPS numbers."""
    if lat is None or lon is None:
        return False
    try:
        f_lat = float(lat)
        f_lon = float(lon)
        return -90.0 <= f_lat <= 90.0 and -180.0 <= f_lon <= 180.0
    except (ValueError, TypeError):
        return False


def get_report_detections_payload(report: Report) -> List[Dict[str, Any]]:
    """Extracts structured detections from report's relational or text fields."""
    if report.detection_results:
        return [
            {
                "class_name": d.detected_class,
                "confidence": d.confidence,
                "bbox": [d.bbox_xmin, d.bbox_ymin, d.bbox_xmax, d.bbox_ymax],
                "bbox_normalized": json.loads(d.bbox_normalized) if isinstance(d.bbox_normalized, str) else d.bbox_normalized,
            }
            for d in report.detection_results
        ]
    elif report.ml_detections:
        try:
            parsed = json.loads(report.ml_detections) if isinstance(report.ml_detections, str) else report.ml_detections
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


def update_single_report_priority(
    report: Report,
    db: Session,
    trigger: str = "recalculated",
    priority_config: Optional[PriorityConfig] = None,
) -> bool:
    """Computes and updates priority, severity, score, and reasons for a single report.
    
    Respects manual priority overrides and appends audit row to priority_history
    whenever severity or priority changes. Returns True if updated.
    """
    try:
        prev_priority = report.priority
        prev_severity = report.severity

        has_coords = is_valid_coordinate(report.latitude, report.longitude)
        detections = get_report_detections_payload(report)

        created_at = report.created_at or datetime.utcnow()
        age_days = (datetime.utcnow() - created_at).total_seconds() / 86400.0

        assessment = calculate_priority(
            detections=detections,
            ml_status=report.ml_status,
            nearby_report_count=report.nearby_report_count or 0,
            report_age_days=age_days,
            has_valid_coordinates=has_coords,
            nearby_distance_meters=settings.NEARBY_DISTANCE_METERS,
            config=priority_config,
        )

        new_severity = assessment["severity"]
        calculated_priority = assessment["priority"]
        score = assessment["score"]
        reasons = assessment["reasons"]

        # Preserve manual priority override if active
        if getattr(report, "is_priority_overridden", False):
            effective_priority = report.priority
            override_reason = getattr(report, "priority_override_reason", "Officer manual override")
            reasons.insert(0, f"Manual override: {override_reason}")
        else:
            effective_priority = calculated_priority

        report.severity = new_severity
        report.priority = effective_priority
        report.priority_score = score
        report.priority_reasons = json.dumps(reasons)
        report.priority_updated_at = datetime.utcnow()

        # Check if history row is warranted:
        # Record whenever priority or severity changed, or if it is an explicit trigger
        needs_history = (
            prev_priority != effective_priority
            or prev_severity != new_severity
            or trigger in ("created", "manual_override", "recalculated")
        )

        if needs_history:
            history_entry = PriorityHistory(
                report_id=report.id,
                previous_priority=prev_priority,
                new_priority=effective_priority,
                previous_severity=prev_severity,
                new_severity=new_severity,
                score=score,
                reasons=json.dumps(reasons),
                trigger=trigger,
                created_at=datetime.utcnow(),
            )
            db.add(history_entry)

        return True
    except Exception as e:
        logger.error(f"[Priority Update] Error computing priority for Report #{report.id}: {e}", exc_info=True)
        # Never crash: store null priority with failure marker
        report.priority = None
        report.priority_reasons = json.dumps(["priority_calculation_failed"])
        report.severity = "UNKNOWN"
        report.priority_score = None
        return False


def process_report_proximity(
    new_report: Report,
    db: Session,
    recalculate_neighbors: bool = True,
    priority_config: Optional[PriorityConfig] = None,
) -> List[ReportRelation]:
    """Scans for nearby and duplicate reports for new_report and synchronizes relations.
    
    Guarantees:
    - Never scans the entire table (spatial bounding-box prefilter)
    - Excludes self and excluded rejected reports
    - Uses unordered pair canonical order (report_id = min, related_report_id = max)
    - Distinguishes POTENTIAL_DUPLICATE from NEARBY_RELATED
    - Updates nearby_report_count on new_report and neighbors
    - Recalculates priority on affected reports without recalculation loops
    - Never throws an unhandled exception that blocks report creation
    """
    created_relations: List[ReportRelation] = []

    try:
        if not is_valid_coordinate(new_report.latitude, new_report.longitude):
            logger.info(f"[Proximity] Report #{new_report.id} coordinates invalid or missing; proximity skipped.")
            new_report.nearby_report_count = 0
            update_single_report_priority(new_report, db, trigger="created", priority_config=priority_config)
            db.commit()
            return []

        lat1 = float(new_report.latitude)
        lon1 = float(new_report.longitude)

        # 1. Bounding box prefilter
        min_lat, max_lat, min_lon, max_lon = get_bounding_box(lat1, lon1, settings.NEARBY_DISTANCE_METERS)

        candidates = (
            db.query(Report)
            .filter(
                Report.id != new_report.id,
                Report.status != ReportStatus.REJECTED,
                Report.latitude.isnot(None),
                Report.longitude.isnot(None),
                Report.latitude.between(min_lat, max_lat),
                Report.longitude.between(min_lon, max_lon),
            )
            .all()
        )

        affected_neighbors: List[Tuple[Report, float]] = []

        for cand in candidates:
            if not is_valid_coordinate(cand.latitude, cand.longitude):
                continue

            dist = haversine_distance(lat1, lon1, float(cand.latitude), float(cand.longitude))

            # Outside nearby boundary -> skip
            if dist > settings.NEARBY_DISTANCE_METERS:
                continue

            affected_neighbors.append((cand, dist))

            # 2. Determine relation type
            is_dup_distance = dist <= settings.DUPLICATE_DISTANCE_METERS
            is_same_class = are_damage_classes_similar(new_report.damage_type, cand.damage_type)
            is_within_time = True

            if settings.DUPLICATE_TIME_WINDOW_DAYS is not None and cand.created_at and new_report.created_at:
                days_diff = abs((new_report.created_at - cand.created_at).total_seconds()) / 86400.0
                if days_diff > settings.DUPLICATE_TIME_WINDOW_DAYS:
                    is_within_time = False

            if is_dup_distance and is_same_class and is_within_time:
                rel_type = "POTENTIAL_DUPLICATE"
            else:
                rel_type = "NEARBY_RELATED"

            # 3. Canonical unordered pair: smaller ID is always report_id
            pair_min = min(new_report.id, cand.id)
            pair_max = max(new_report.id, cand.id)

            existing_rel = (
                db.query(ReportRelation)
                .filter(
                    ReportRelation.report_id == pair_min,
                    ReportRelation.related_report_id == pair_max,
                )
                .first()
            )

            if not existing_rel:
                new_rel = ReportRelation(
                    report_id=pair_min,
                    related_report_id=pair_max,
                    distance_meters=round(dist, 1),
                    relation_type=rel_type,
                    review_status="PENDING",
                    created_at=datetime.utcnow(),
                )
                db.add(new_rel)
                created_relations.append(new_rel)
            else:
                # Update existing relation distance and type if more accurate
                existing_rel.distance_meters = round(dist, 1)
                if existing_rel.review_status == "PENDING":
                    existing_rel.relation_type = rel_type

        # 4. Synchronize nearby_report_count
        new_report.nearby_report_count = len(affected_neighbors)
        update_single_report_priority(new_report, db, trigger="created", priority_config=priority_config)

        # 5. Update neighbors and recalculate their priority (without triggering neighbor cascades)
        if recalculate_neighbors:
            for neighbor, _ in affected_neighbors:
                # Count current non-rejected reports within distance for neighbor
                n_lat = float(neighbor.latitude)
                n_lon = float(neighbor.longitude)
                n_min_lat, n_max_lat, n_min_lon, n_max_lon = get_bounding_box(n_lat, n_lon, settings.NEARBY_DISTANCE_METERS)

                neighbor_candidates = (
                    db.query(Report)
                    .filter(
                        Report.id != neighbor.id,
                        Report.status != ReportStatus.REJECTED,
                        Report.latitude.isnot(None),
                        Report.longitude.isnot(None),
                        Report.latitude.between(n_min_lat, n_max_lat),
                        Report.longitude.between(n_min_lon, n_max_lon),
                    )
                    .all()
                )

                n_count = 0
                for nc in neighbor_candidates:
                    if is_valid_coordinate(nc.latitude, nc.longitude):
                        if haversine_distance(n_lat, n_lon, float(nc.latitude), float(nc.longitude)) <= settings.NEARBY_DISTANCE_METERS:
                            n_count += 1

                neighbor.nearby_report_count = n_count
                update_single_report_priority(
                    neighbor,
                    db,
                    trigger="nearby_report_added",
                    priority_config=priority_config,
                )

        db.commit()
        db.refresh(new_report)
        return created_relations

    except Exception as e:
        logger.error(f"[Proximity] Failed spatial proximity for Report #{new_report.id}: {e}", exc_info=True)
        # Ensure report priority is still computed on fallback
        try:
            update_single_report_priority(new_report, db, trigger="created", priority_config=priority_config)
            db.commit()
        except Exception:
            pass
        return []
