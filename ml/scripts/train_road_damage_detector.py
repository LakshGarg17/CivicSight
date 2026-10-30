"""CivicSight ML Subsystem — Production YOLOv8n 4-Class Road Damage Detector Training

Trains YOLOv8n on the verified 4-class RDD2022 dataset:
  - D00: Longitudinal Crack
  - D10: Transverse Crack
  - D20: Alligator Crack
  - D40: Pothole (remapped from raw 4)
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
import yaml
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parents[2]
ML_DIR = ROOT_DIR / "ml"
EXPERIMENTS_DIR = ML_DIR / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

YAML_PATH = ML_DIR / "data_4class.yaml"
BASE_WEIGHTS = ROOT_DIR / "yolov8n.pt"


def train_model(epochs: int = 5, batch_size: int = 16, imgsz: int = 512, lr0: float = 0.01):
    print("=" * 70, flush=True)
    print("CivicSight — 4-Class Road Damage Detector (YOLOv8n) Training", flush=True)
    print("=" * 70, flush=True)

    weights_src = str(BASE_WEIGHTS) if BASE_WEIGHTS.exists() else "yolov8n.pt"
    print(f"[INIT] Initializing YOLOv8n model from: {weights_src}", flush=True)
    model = YOLO(weights_src)

    run_name = "civicsight_yolov8n_4class"
    output_project = str(ML_DIR / "runs" / "detect")

    print(f"\n[TRAIN] Commencing training on {YAML_PATH}...", flush=True)
    print(f"  Epochs:     {epochs}", flush=True)
    print(f"  Batch size: {batch_size}", flush=True)
    print(f"  Image size: {imgsz}", flush=True)
    print(f"  LR0:        {lr0} (cosine annealing)", flush=True)
    print(f"  Classes:    D00, D10, D20, D40\n", flush=True)

    train_results = model.train(
        data=str(YAML_PATH),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device="cpu",
        lr0=lr0,
        cos_lr=True,
        project=output_project,
        name=run_name,
        workers=0,
        exist_ok=True,
        verbose=True,
        save=True,
        plots=True,
    )

    print("\n[EVAL] Running validation evaluation on held-out val set...", flush=True)
    val_results = model.val(
        data=str(YAML_PATH),
        imgsz=imgsz,
        batch=batch_size,
        device="cpu",
        workers=0,
        plots=True,
    )

    box_metrics = val_results.box
    map50 = float(box_metrics.map50)
    map50_95 = float(box_metrics.map)
    precision = float(box_metrics.mp)
    recall = float(box_metrics.mr)

    maps_per_class = box_metrics.maps.tolist() if hasattr(box_metrics, "maps") else [0.0] * 4
    class_names = ["D00", "D10", "D20", "D40"]
    class_map50 = {}
    for i, name in enumerate(class_names):
        if i < len(maps_per_class):
            class_map50[name] = round(float(maps_per_class[i]), 4)
        else:
            class_map50[name] = 0.0

    best_weights_path = Path(output_project) / run_name / "weights" / "best.pt"
    compat_weights_dir = ML_DIR / "runs" / "detect" / "experiment2_week5" / "weights"
    compat_weights_dir.mkdir(parents=True, exist_ok=True)
    if best_weights_path.exists():
        shutil.copy2(best_weights_path, compat_weights_dir / "best.pt")
        print(f"\n[OK] Best weights copied to compatibility path: {compat_weights_dir / 'best.pt'}", flush=True)

    results_data = {
        "model_name": "CivicSight YOLOv8n 4-Class Road Damage Detector",
        "timestamp": datetime.utcnow().isoformat(),
        "checkpoint": str(best_weights_path),
        "configuration": {
            "epochs": epochs,
            "imgsz": imgsz,
            "batch_size": batch_size,
            "lr0": lr0,
            "cos_lr": True,
            "classes": ["D00", "D10", "D20", "D40"],
            "dataset": "RDD2022 4-Class Balanced Partition (680 train / 190 val / 190 test)",
        },
        "metrics": {
            "overall_mAP50": round(map50, 4),
            "overall_mAP50_95": round(map50_95, 4),
            "mean_precision": round(precision, 4),
            "mean_recall": round(recall, 4),
            "per_class_mAP50": class_map50,
        },
    }

    out_json = EXPERIMENTS_DIR / "retrained_4class_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print("\n" + "=" * 70, flush=True)
    print(" 4-CLASS DETECTOR RETRAINING RESULTS", flush=True)
    print("=" * 70, flush=True)
    print(f" Mean Precision: {precision:.4f}", flush=True)
    print(f" Mean Recall:    {recall:.4f}", flush=True)
    print(f" mAP@0.5:        {map50:.4f}", flush=True)
    print(f" mAP@0.5:0.95:   {map50_95:.4f}", flush=True)
    print(" Per-Class mAP@0.5:", flush=True)
    for cname, v in class_map50.items():
        print(f"   {cname}: {v:.4f}", flush=True)
    print(f"\n Results saved to: {out_json}", flush=True)
    print(f" Canonical Checkpoint: {best_weights_path}", flush=True)
    return best_weights_path, results_data


if __name__ == "__main__":
    train_model(epochs=5, batch_size=16, imgsz=512)
