"""CivicSight Week 8 ML Evaluation & Priority Mapping Script

Runs the finalized YOLOv8n detector across representative test images (including clean road),
measures confidence distribution per class, maps class + confidence to severity and priority,
and generates structured documentation for ml/experiments/results.md.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add workspace roots to path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "backend"))

from ml.src.inference import detect_road_damage
from app.services.priority import PriorityConfig, calculate_priority, calculate_severity


def run_evaluation():
    print("=" * 70)
    print("CIVICSIGHT WEEK 8: ML EVALUATION & PRIORITY ENGINE MAPPING")
    print("=" * 70)

    # 1. Target Images (Sample set + Held-out RDD test images)
    test_images = []
    
    # Samples in ml/samples
    sample_dir = WORKSPACE_ROOT / "ml" / "samples"
    for img_name in ["sample_pothole_d40.jpg", "sample_crack_d10.jpg", "sample_road.jpg"]:
        p = sample_dir / img_name
        if p.exists():
            test_images.append(p)

    # Held out RDD images
    rdd_test_dir = WORKSPACE_ROOT / "Dataset" / "RDD_SPLIT" / "test" / "images"
    if rdd_test_dir.exists():
        rdd_files = list(rdd_test_dir.glob("*.jpg"))[:15]
        test_images.extend(rdd_files)

    print(f"[*] Total test images assembled: {len(test_images)}")

    class_confidences: Dict[str, List[float]] = {"D00": [], "D10": [], "D20": [], "D40": []}
    evaluation_records: List[Dict[str, Any]] = []

    cfg = PriorityConfig()

    for img_path in test_images:
        res = detect_road_damage(str(img_path), confidence_threshold=0.10)
        detections = res.get("detections", [])

        # Priority calculation with ML detections
        p_res = calculate_priority(
            detections=detections,
            ml_status=res.get("ml_status", "ML_COMPLETE" if detections else "ML_NO_DETECTIONS"),
            nearby_report_count=0,
            report_age_days=0.0,
            config=cfg,
        )

        for d in detections:
            cls_name = d.get("class_name")
            conf = d.get("confidence", 0.0)
            if cls_name in class_confidences:
                class_confidences[cls_name].append(conf)

        evaluation_records.append({
            "image": img_path.name,
            "num_detections": len(detections),
            "detections": detections,
            "severity": p_res["severity"],
            "priority": p_res["priority"],
            "score": p_res["score"],
            "reasons": p_res["reasons"],
        })

    print("\n--- 1. Confidence Distribution per Class ---")
    conf_stats = {}
    for cls_name, confs in class_confidences.items():
        if confs:
            min_c = min(confs)
            mean_c = sum(confs) / len(confs)
            max_c = max(confs)
            count = len(confs)
            conf_stats[cls_name] = {"min": min_c, "mean": mean_c, "max": max_c, "count": count}
            print(f"Class {cls_name} (n={count:2d}): Min={min_c:.3f} | Mean={mean_c:.3f} | Max={max_c:.3f}")
        else:
            conf_stats[cls_name] = {"min": 0.0, "mean": 0.0, "max": 0.0, "count": 0}
            print(f"Class {cls_name} (n= 0): No detections at conf >= 0.10")

    print("\n--- 2. Priority Engine Class + Confidence Mapping ---")
    mapping_scenarios = [
        # (class, conf, bbox_area, label)
        ("D40", 0.92, 0.08, "High-Confidence Pothole"),
        ("D40", 0.55, 0.04, "Moderate Pothole"),
        ("D40", 0.22, 0.03, "Sub-threshold Pothole (<0.25)"),
        ("D20", 0.78, 0.09, "Confident Alligator Cracking"),
        ("D20", 0.35, 0.05, "Low-Conf Alligator Cracking"),
        ("D10", 0.65, 0.03, "Transverse Crack"),
        ("D00", 0.60, 0.02, "Longitudinal Crack"),
        ("None", 0.00, 0.00, "Clean Road (Zero Detections)"),
    ]

    mapping_table = []
    for cls_name, conf, area, desc in mapping_scenarios:
        if cls_name == "None":
            dets = []
            status = "ML_NO_DETECTIONS"
        else:
            dets = [{"class": cls_name, "class_name": cls_name, "confidence": conf, "bbox_area": area, "bbox": [0,0,100,100]}]
            status = "ML_COMPLETE"

        p_out = calculate_priority(dets, ml_status=status, nearby_report_count=0, report_age_days=0.0, config=cfg)
        mapping_table.append({
            "scenario": desc,
            "class": cls_name,
            "confidence": f"{conf:.2f}" if conf > 0 else "N/A",
            "severity": p_out["severity"],
            "priority": p_out["priority"],
            "score": f"{p_out['score']:.1f}",
            "primary_reason": p_out["reasons"][0] if p_out["reasons"] else "",
        })
        print(f"[{cls_name:4s} @ {conf:.2f}] => Severity: {p_out['severity']:7s} | Priority: {p_out['priority']:6s} | Score: {p_out['score']:4.1f} | Reason: {p_out['reasons'][0]}")

    return conf_stats, mapping_table, evaluation_records


if __name__ == "__main__":
    run_evaluation()
