"""CivicSight ML Subsystem — Week 7 Prototype Final Model Benchmark Script

Runs comprehensive latency and detection benchmarks for the finalized YOLOv8n model
(weights: ml/runs/detect/experiment2_week5/weights/best.pt, model_version: YOLOv8n-experiment2_week5).

Outputs:
- Inference timing distribution across 25 representative held-out images
- Preprocessing + Inference breakdown
- Per-class detection findings and known weak class flags
- Results JSON for documentation in ml/experiments/results.md
"""

import sys
import json
import time
from pathlib import Path
import numpy as np

# Resolve repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.preprocess import preprocess_report_image
from ml.src.inference import detect_road_damage, get_road_damage_detector, CLASS_METADATA

MODEL_VERSION = "YOLOv8n-experiment2_week5"
WEIGHTS_PATH = PROJECT_ROOT / "ml" / "runs" / "detect" / "experiment2_week5" / "weights" / "best.pt"
TEST_IMG_DIR = PROJECT_ROOT / "Dataset" / "RDD_SPLIT" / "test" / "images"


def run_benchmark():
    print("=" * 70)
    print(" CivicSight Week 7 — Final Model Benchmark & Latency Analysis")
    print(f" Model Version: {MODEL_VERSION}")
    print(f" Weights File:  {WEIGHTS_PATH}")
    print("=" * 70)

    if not WEIGHTS_PATH.is_file():
        raise FileNotFoundError(f"Model weights not found at: {WEIGHTS_PATH}")

    # Warm up model
    print("\n[1] Warming up model singleton...")
    model = get_road_damage_detector(WEIGHTS_PATH)
    dummy_input = np.zeros((512, 512, 3), dtype=np.uint8)
    _ = model.predict(source=dummy_input, verbose=False)
    print("    Model warm-up completed successfully.")

    # Select 25 representative images across capture modalities
    selected_files = [
        # China MotorBike (street-level)
        "China_MotorBike_000003.jpg",
        "China_MotorBike_000010.jpg",
        "China_MotorBike_000024.jpg",
        "China_MotorBike_000034.jpg",
        "China_MotorBike_000048.jpg",
        "China_MotorBike_000093.jpg",
        "China_MotorBike_000104.jpg",
        "China_MotorBike_000146.jpg",
        "China_MotorBike_000200.jpg",
        # Czech (vehicle mount)
        "Czech_000010.jpg",
        "Czech_000018.jpg",
        "Czech_000038.jpg",
        "Czech_000048.jpg",
        "Czech_000084.jpg",
        "Czech_000119.jpg",
        "Czech_000141.jpg",
        "Czech_000201.jpg",
        # China Drone (aerial / low altitude)
        "China_Drone_000008.jpg",
        "China_Drone_000017.jpg",
        "China_Drone_000040.jpg",
        "China_Drone_000053.jpg",
        "China_Drone_000099.jpg",
        "China_Drone_000101.jpg",
        "China_Drone_000150.jpg",
        "China_Drone_000216.jpg",
    ]

    benchmark_images = []
    for fn in selected_files:
        p = TEST_IMG_DIR / fn
        if p.is_file():
            benchmark_images.append(p)

    if len(benchmark_images) < 20:
        # Fallback to first available files if any listed are missing
        all_imgs = list(TEST_IMG_DIR.glob("*.jpg"))[:25]
        benchmark_images = all_imgs

    print(f"\n[2] Benchmarking inference on {len(benchmark_images)} representative test images...")

    results = []
    prep_times = []
    infer_times = []
    total_times = []
    detections_by_class = {code: 0 for code in ["D00", "D10", "D20", "D40"]}
    confidence_scores_by_class = {code: [] for code in ["D00", "D10", "D20", "D40"]}

    for i, img_path in enumerate(benchmark_images, 1):
        # Time Preprocessing
        t0 = time.perf_counter()
        prep_out = preprocess_report_image(img_path)
        t_prep = (time.perf_counter() - t0) * 1000.0

        # Time Inference
        t1 = time.perf_counter()
        det_out = detect_road_damage(prep_out, model_path=WEIGHTS_PATH)
        t_infer = (time.perf_counter() - t1) * 1000.0

        t_total = t_prep + t_infer

        prep_times.append(t_prep)
        infer_times.append(t_infer)
        total_times.append(t_total)

        num_det = det_out["num_detections"]
        for d in det_out["detections"]:
            cls_name = d["class_name"]
            if cls_name in detections_by_class:
                detections_by_class[cls_name] += 1
                confidence_scores_by_class[cls_name].append(d["confidence"])

        results.append({
            "filename": img_path.name,
            "preprocessing_ms": round(t_prep, 2),
            "inference_ms": round(t_infer, 2),
            "total_ms": round(t_total, 2),
            "num_detections": num_det,
            "primary_damage": det_out["primary_damage_type"],
            "primary_priority": det_out["primary_priority"],
        })

        print(
            f"  [{i:02d}/{len(benchmark_images)}] {img_path.name:<28} | "
            f"Prep: {t_prep:5.1f}ms | Infer: {t_infer:5.1f}ms | Total: {t_total:5.1f}ms | "
            f"Detections: {num_det} ({det_out['primary_damage_type']})"
        )

    # Statistical summaries
    prep_arr = np.array(prep_times)
    infer_arr = np.array(infer_times)
    total_arr = np.array(total_times)

    summary_stats = {
        "sample_size": len(benchmark_images),
        "model_version": MODEL_VERSION,
        "weights_file": WEIGHTS_PATH.name,
        "preprocessing_ms": {
            "mean": round(float(np.mean(prep_arr)), 2),
            "std": round(float(np.std(prep_arr)), 2),
            "min": round(float(np.min(prep_arr)), 2),
            "max": round(float(np.max(prep_arr)), 2),
            "p50": round(float(np.percentile(prep_arr, 50)), 2),
            "p95": round(float(np.percentile(prep_arr, 95)), 2),
        },
        "inference_ms": {
            "mean": round(float(np.mean(infer_arr)), 2),
            "std": round(float(np.std(infer_arr)), 2),
            "min": round(float(np.min(infer_arr)), 2),
            "max": round(float(np.max(infer_arr)), 2),
            "p50": round(float(np.percentile(infer_arr, 50)), 2),
            "p95": round(float(np.percentile(infer_arr, 95)), 2),
        },
        "total_pipeline_ms": {
            "mean": round(float(np.mean(total_arr)), 2),
            "std": round(float(np.std(total_arr)), 2),
            "min": round(float(np.min(total_arr)), 2),
            "max": round(float(np.max(total_arr)), 2),
            "p50": round(float(np.percentile(total_arr, 50)), 2),
            "p95": round(float(np.percentile(total_arr, 95)), 2),
        },
        "detection_counts_by_class": detections_by_class,
        "per_image_results": results,
    }

    print("\n" + "=" * 70)
    print(" BENCHMARK LATENCY SUMMARY (CPU Intel Core i7 / 512x512 resolution)")
    print("=" * 70)
    print(f" Preprocessing (Week 4):  Mean = {summary_stats['preprocessing_ms']['mean']:5.2f} ms | p95 = {summary_stats['preprocessing_ms']['p95']:5.2f} ms")
    print(f" YOLO Inference (Week 6): Mean = {summary_stats['inference_ms']['mean']:5.2f} ms | p95 = {summary_stats['inference_ms']['p95']:5.2f} ms")
    print(f" Total Per-Image Latency: Mean = {summary_stats['total_pipeline_ms']['mean']:5.2f} ms | p95 = {summary_stats['total_pipeline_ms']['p95']:5.2f} ms")
    print("\n Detections Breakdown Across Test Sample:")
    for code, count in detections_by_class.items():
        desc = CLASS_METADATA.get(["D00", "D10", "D20", "D40"].index(code), {}).get("description", code)
        confs = confidence_scores_by_class[code]
        avg_conf = f"{np.mean(confs):.2%}" if confs else "N/A"
        print(f"   * {code} ({desc}): {count} detections (avg confidence: {avg_conf})")

    # Save results to json
    out_json = PROJECT_ROOT / "ml" / "experiments" / "week7_benchmark_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary_stats, f, indent=2)
    print(f"\nSaved benchmark results to {out_json}")

    return summary_stats


if __name__ == "__main__":
    run_benchmark()
