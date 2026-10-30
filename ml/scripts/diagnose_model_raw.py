"""CivicSight ML Subsystem — Phase 2: Raw YOLO Model Diagnostic & Forensic Script

Evaluates the exact checkpoint loaded by the application on canonical test images
and user-submitted images (including pot1.webp, alig1.webp, road1.webp) independently of the UI.
Saves annotated images and outputs full forensic metrics for each image.
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO
from ml.src.inference import resolve_model_weights_path, CLASS_METADATA

DIAG_OUT_DIR = PROJECT_ROOT / "ml" / "diagnostic_output"
DIAG_OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def run_diagnostics():
    print("=" * 80)
    print("PHASE 2: RAW YOLO PREDICTION DIAGNOSTIC & ROOT-CAUSE ANALYSIS")
    print("=" * 80)

    # 1. Resolve and verify checkpoint
    weights_path = resolve_model_weights_path()
    weights_sha = get_file_sha256(weights_path)
    weights_size = weights_path.stat().st_size

    print(f"\n[MODEL CHECKPOINT AUDIT]")
    print(f"  Absolute Path:  {weights_path}")
    print(f"  File Size:      {weights_size:,} bytes")
    print(f"  SHA-256:        {weights_sha}")

    model = YOLO(str(weights_path))
    class_names = model.names
    print(f"  Model Classes:  {class_names}")
    print(f"  Total Classes:  {len(class_names)}")
    tax_codes = [f"{k}:{v['code']}" for k, v in CLASS_METADATA.items()]
    print(f"  Taxonomy Codes: {tax_codes}")

    # 2. Define Diagnostic Images
    test_suite = [
        {
            "name": "pot1.webp",
            "path": PROJECT_ROOT / "ml" / "samples" / "user_tests" / "pot1.webp",
            "ground_truth": "D40 (Pothole - User Submitted from Screenshot)",
        },
        {
            "name": "alig1.webp",
            "path": PROJECT_ROOT / "ml" / "samples" / "user_tests" / "alig1.webp",
            "ground_truth": "D20 (Alligator Crack - User Submitted)",
        },
        {
            "name": "road1.webp",
            "path": PROJECT_ROOT / "ml" / "samples" / "user_tests" / "road1.webp",
            "ground_truth": "CLEAN (Highway View - User Submitted)",
        },
        {
            "name": "sample_road.jpg",
            "path": PROJECT_ROOT / "ml" / "samples" / "sample_road.jpg",
            "ground_truth": "CLEAN (Clean Road Surface)",
        },
        {
            "name": "sample_crack_d10.jpg",
            "path": PROJECT_ROOT / "ml" / "samples" / "sample_crack_d10.jpg",
            "ground_truth": "D10 (Transverse Crack)",
        },
        {
            "name": "China_Drone_000264.jpg",
            "path": PROJECT_ROOT / "ml" / "data_4class" / "test" / "images" / "China_Drone_000264.jpg",
            "ground_truth": "D00 (Longitudinal Crack - RDD2022 Test)",
        },
        {
            "name": "China_MotorBike_001293.jpg",
            "path": PROJECT_ROOT / "ml" / "data_4class" / "test" / "images" / "China_MotorBike_001293.jpg",
            "ground_truth": "D40 (Pothole - RDD2022 Test)",
        },
        {
            "name": "Czech_000521.jpg",
            "path": PROJECT_ROOT / "ml" / "data_4class" / "test" / "images" / "Czech_000521.jpg",
            "ground_truth": "CLEAN (Clean Road - RDD2022 Test)",
        },
    ]

    print("\n" + "=" * 80)
    print(f"RUNNING INFERENCE ON {len(test_suite)} DIAGNOSTIC IMAGES")
    print("=" * 80)

    summary_results = []

    for item in test_suite:
        p = item["path"]
        if not p.is_file():
            print(f"\n[WARNING] Image not found: {p}")
            continue

        # Load image with PIL to check dimensions
        with Image.open(p) as img_pil:
            orig_w, orig_h = img_pil.size

        # Run inference at multiple confidence thresholds:
        # 1. configured production threshold: 0.25
        # 2. sensitive diagnostic threshold: 0.10
        # 3. raw candidate threshold: 0.01
        # 4. floor threshold: 0.001
        
        t0 = time.perf_counter()
        raw_res = model.predict(source=str(p), conf=0.001, iou=0.45, device="cpu", verbose=False)[0]
        inf_time_ms = (time.perf_counter() - t0) * 1000.0

        all_boxes = raw_res.boxes
        total_raw_candidates = len(all_boxes)

        boxes_001 = []
        boxes_010 = []
        boxes_025 = []

        max_conf = 0.0
        top_prediction = ("NONE", 0.0, [])

        if total_raw_candidates > 0:
            for b in all_boxes:
                cls_id = int(b.cls.item())
                conf = float(b.conf.item())
                xyxy = [round(v, 1) for v in b.xyxy[0].tolist()]
                cname = model.names.get(cls_id, f"D{cls_id}")

                box_info = {
                    "class_id": cls_id,
                    "class_name": cname,
                    "confidence": round(conf, 4),
                    "bbox": xyxy,
                }

                if conf > max_conf:
                    max_conf = conf
                    top_prediction = (cname, round(conf, 4), xyxy)

                if conf >= 0.01:
                    boxes_001.append(box_info)
                if conf >= 0.10:
                    boxes_010.append(box_info)
                if conf >= 0.25:
                    boxes_025.append(box_info)

        # Save annotated image at conf=0.01 for visual verification
        annotated_bgr = raw_res.plot(conf=True, boxes=True, labels=True)
        annotated_path = DIAG_OUT_DIR / f"diag_{item['name']}.jpg"
        cv2.imwrite(str(annotated_path), annotated_bgr)

        print(f"\nImage: {item['name']} ({orig_w}x{orig_h})")
        print(f"  Ground Truth:           {item['ground_truth']}")
        print(f"  Latency:                {inf_time_ms:.1f} ms")
        print(f"  Raw Candidates (>=0.001): {total_raw_candidates}")
        print(f"  Highest Model Confidence: {max_conf:.4f} ({top_prediction[0]})")
        print(f"  Detections @ conf>=0.25:  {len(boxes_025)} -> {[b['class_name'] + ':' + str(b['confidence']) for b in boxes_025]}")
        print(f"  Detections @ conf>=0.10:  {len(boxes_010)} -> {[b['class_name'] + ':' + str(b['confidence']) for b in boxes_010]}")
        print(f"  Detections @ conf>=0.01:  {len(boxes_001)} -> {[b['class_name'] + ':' + str(b['confidence']) for b in boxes_001[:5]]}")
        print(f"  Annotated Image Saved:  {annotated_path.name}")

        summary_results.append({
            "image": item["name"],
            "ground_truth": item["ground_truth"],
            "dimensions": f"{orig_w}x{orig_h}",
            "max_confidence": max_conf,
            "top_class": top_prediction[0],
            "dets_at_025": len(boxes_025),
            "dets_at_010": len(boxes_010),
            "dets_at_001": len(boxes_001),
            "latency_ms": round(inf_time_ms, 1),
        })

    # Save summary report JSON
    with open(DIAG_OUT_DIR / "phase2_diagnostic_report.json", "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    print("\n" + "=" * 80)
    print("PHASE 2 DIAGNOSTIC COMPLETE — REPORT SAVED TO ml/diagnostic_output/")
    print("=" * 80)


if __name__ == "__main__":
    run_diagnostics()
