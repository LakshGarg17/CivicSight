"""CivicSight ML Pipeline — Week 5 Training Experiment 2

Compares against Week 4 Baseline run with deliberate changes:
1. Image Resolution: Changed from 640x640 to 512x512 (compute efficiency & spatial feature density).
2. Training Duration: Increased from 2 epochs to 3 epochs (+50% optimization steps).
3. Learning Rate Scheduler: Enabled cosine learning rate scheduling (cos_lr=True) with lr0=0.01.

Evaluates:
- Precision, Recall, mAP@0.5, mAP@0.5:0.95
- Per-class performance (D00, D10, D20, D40)
- Training loss trajectories
Outputs structured results for ml/experiments/results.md.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import yaml
from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parents[2]
ML_DIR = ROOT_DIR / "ml"
EXPERIMENTS_DIR = ML_DIR / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

YAML_PATH = ML_DIR / "baseline_data.yaml"


def run_experiment2():
    print("=" * 65)
    print(" CivicSight Week 5: ML Training Experiment 2")
    print("=" * 65)

    weights_path = ROOT_DIR / "yolov8n.pt"
    if not weights_path.exists():
        weights_path = "yolov8n.pt"

    print(f"\n[INIT] Loading base YOLOv8n weights from: {weights_path}")
    model = YOLO(str(weights_path))

    config = {
        "experiment_name": "Experiment 2: 512px Cosine-LR Optimization",
        "model_variant": "YOLOv8n",
        "pretrained_weights": str(weights_path),
        "epochs": 3,
        "imgsz": 512,
        "batch_size": 8,
        "device": "cpu",
        "lr0": 0.01,
        "cos_lr": True,
        "classes": ["D00", "D10", "D20", "D40"],
        "dataset": "RDD2022 Baseline Partition (250 train / 60 val)",
        "timestamp": datetime.utcnow().isoformat(),
        "deliberate_changes": [
            "Resolution changed from 640 to 512 to test faster spatial receptive field convergence",
            "Epoch count increased from 2 to 3 (+50% training updates)",
            "Cosine learning rate annealing enabled (cos_lr=True) to prevent gradient overshoot"
        ]
    }

    print("\n[CONFIG] Training parameters:")
    for k, v in config.items():
        print(f"  {k}: {v}")

    print("\n[TRAIN] Commencing Experiment 2 training...")
    train_results = model.train(
        data=str(YAML_PATH),
        epochs=config["epochs"],
        imgsz=config["imgsz"],
        batch=config["batch_size"],
        device=config["device"],
        lr0=config["lr0"],
        cos_lr=config["cos_lr"],
        project=str(ML_DIR / "runs" / "detect"),
        name="experiment2_week5",
        workers=0,
        exist_ok=True,
        verbose=True,
    )

    print("\n[EVAL] Evaluating model on validation split...")
    val_results = model.val(
        data=str(YAML_PATH),
        imgsz=config["imgsz"],
        batch=config["batch_size"],
        device=config["device"],
        workers=0,
    )

    box_metrics = val_results.box
    map50 = float(box_metrics.map50)
    map50_95 = float(box_metrics.map)
    precision = float(box_metrics.mp)
    recall = float(box_metrics.mr)

    # Per-class metrics
    maps_per_class = box_metrics.maps.tolist() if hasattr(box_metrics, "maps") else [0.0] * 4
    class_names = ["D00", "D10", "D20", "D40"]
    class_map50 = {}
    for i, name in enumerate(class_names):
        if i < len(maps_per_class):
            class_map50[name] = round(float(maps_per_class[i]), 4)
        else:
            class_map50[name] = 0.0

    # Extract final training losses from train_results if available
    loss_metrics = {}
    try:
        # train_results often has results_dict or fitness
        if hasattr(train_results, "results_dict"):
            for k, v in train_results.results_dict.items():
                loss_metrics[k] = round(float(v), 4)
    except Exception as e:
        print(f"[WARN] Could not parse detailed loss dict: {e}")

    results_data = {
        "experiment_name": config["experiment_name"],
        "timestamp": config["timestamp"],
        "configuration": config,
        "metrics": {
            "overall_mAP50": round(map50, 4),
            "overall_mAP50_95": round(map50_95, 4),
            "mean_precision": round(precision, 4),
            "mean_recall": round(recall, 4),
            "per_class_mAP50": class_map50,
        },
        "loss_metrics": loss_metrics,
        "save_dir": str(model.trainer.save_dir) if hasattr(model, "trainer") and hasattr(model.trainer, "save_dir") else "",
    }

    out_json = EXPERIMENTS_DIR / "experiment2_results.json"
    with open(out_json, "w") as f:
        json.dump(results_data, f, indent=2)

    print("\n" + "=" * 65)
    print(" EXPERIMENT 2 RESULTS SUMMARY")
    print("=" * 65)
    print(f" Mean Precision:   {results_data['metrics']['mean_precision']:.4f}")
    print(f" Mean Recall:      {results_data['metrics']['mean_recall']:.4f}")
    print(f" mAP@0.5:          {results_data['metrics']['overall_mAP50']:.4f}")
    print(f" mAP@0.5:0.95:     {results_data['metrics']['overall_mAP50_95']:.4f}")
    print(" Per-Class mAP@0.5:")
    for cls_name, val in class_map50.items():
        print(f"   {cls_name}: {val:.4f}")
    print(f"\n Results saved to: {out_json}")


if __name__ == "__main__":
    run_experiment2()
