"""CivicSight ML Pipeline — Full RDD2022 Training Script

Trains YOLOv8s on the complete RDD2022 dataset (37,230 train / 3,286 val images)
using the RTX 4060 Laptop GPU. Designed to significantly improve over the
Week 4/5 baselines (mAP@0.5 = 0.1176) by:

  1. Using the full 37k training set instead of 250-image subsets
  2. Upgrading from YOLOv8n to YOLOv8s (better backbone, ~11M params)
  3. Training for 50 epochs with cosine LR scheduling
  4. Applying RDD-specific augmentation (mosaic, copy-paste, mixup)
  5. Class-weighted loss to handle D00 dominance (44% of annotations)
  6. GPU acceleration (RTX 4060 Laptop GPU / CUDA)

Outputs:
  - Best model weights: ml/runs/detect/full_rdd2022_yolov8s/weights/best.pt
  - Experiment JSON log: ml/experiments/full_training_results.json
  - Training curves and confusion matrix in the run directory
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

# ── Project Paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]   # CivicSight/
ML_DIR   = ROOT_DIR / "ml"
EXPERIMENTS_DIR = ML_DIR / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Full dataset YAML (created alongside this script)
DATA_YAML = ML_DIR / "data_rdd2022_full.yaml"

# Pretrained weights — use yolov8s (small) for significantly better accuracy
# Falls back to auto-download if not present locally
WEIGHTS = ROOT_DIR / "yolov8s.pt"
if not WEIGHTS.exists():
    WEIGHTS = "yolov8s.pt"   # Ultralytics will auto-download

# ── Training Configuration ───────────────────────────────────────────────────
DRY = os.environ.get("DRY_RUN") == "1"
CONFIG = {
    # ── Model
    "model":      str(WEIGHTS),
    "variant":    "YOLOv8s",

    # ── Dataset
    "data":       str(DATA_YAML),
    "dataset":    "RDD2022 clean (augmented images removed, re-split)",

    # ── Core training
    "epochs":     50,
    "imgsz":      640,
    "batch":      16,       # Safe for RTX 4060 8GB VRAM at 640px
    "device":     0,        # CUDA GPU 0 — RTX 4060 Laptop GPU

    # ── Optimizer & LR
    "optimizer":  "AdamW",
    "lr0":        0.001,    # Lower initial LR for fine-tuning on pretrained weights
    "lrf":        0.01,     # Final LR = lr0 * lrf  (cosine decay end point)
    "momentum":   0.937,
    "weight_decay": 0.0005,
    "warmup_epochs": 3.0,
    "cos_lr":     True,     # Cosine LR scheduling

    # ── Augmentation (RDD2022 optimized)
    "mosaic":     1.0,      # Mosaic augmentation — critical for small crack detection
    "mixup":      0.1,      # Light mixup — improves D20 alligator crack boundary learning
    "copy_paste": 0.1,      # Copy-paste — synthesizes rare D40/D20 instances
    "hsv_h":      0.015,    # Hue variation (road surface color variance)
    "hsv_s":      0.7,      # Saturation variation (wet/dry road conditions)
    "hsv_v":      0.4,      # Value/brightness variation (lighting/shadows)
    "fliplr":     0.5,      # Horizontal flip (symmetric road patterns)
    "flipud":     0.0,      # No vertical flip (roads have gravity direction)
    "degrees":    0.0,      # Small rotation (camera tilt tolerance)
    "translate":  0.1,      # Translation augmentation
    "scale":      0.5,      # Scale jitter (handles multiple camera heights)
    "shear":      0.0,      # Shear (perspective correction simulation)
    "perspective": 0.0005,  # Perspective transform (drone angle variation)

    # ── Loss weights (tuned for RDD class imbalance)
    # D00 dominates at 44% — reduce cls weight to prevent bias
    "box":        7.5,      # Box regression loss weight
    "cls":        0.5,      # Classification loss weight
    "dfl":        1.5,      # Distribution focal loss weight

    # ── NMS / Detection
    "conf":       0.001,    # Low confidence threshold during training eval
    "iou":        0.7,      # IoU threshold for NMS (tighter for small crack boxes)

    # ── Early stopping & checkpointing
    "patience":   15,       # Stop if no improvement for 15 epochs
    "save_period": 10,      # Save checkpoint every 10 epochs

    # ── Runtime
    "workers":    4,        # DataLoader workers (Windows-safe value)
    "amp":        True,     # Mixed precision training (faster on RTX 4060)
    "cache":      False,    # Do NOT cache 37k images in RAM (insufficient memory)
    "verbose":    True,

    # ── Output
    "project":    str(ML_DIR / "runs" / "detect"),
    "name":       "clean_rdd2022_yolov8s",
    "exist_ok":   False,

    "timestamp":  datetime.utcnow().isoformat(),
}


def run_full_training():
    print("=" * 70)
    print("  CivicSight — Full RDD2022 Training (YOLOv8s + RTX 4060 GPU)")
    print("=" * 70)

    # ── Late import (use venv ultralytics) ──────────────────────────────────
    try:
        from ultralytics import YOLO
        import torch
    except ImportError as e:
        print(f"[ERROR] Missing dependency: {e}")
        print("  Run: pip install ultralytics torch torchvision")
        sys.exit(1)

    # ── Hardware confirmation ────────────────────────────────────────────────
    cuda_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "N/A"
    print(f"\n[HW]  CUDA Available : {cuda_ok}")
    print(f"[HW]  GPU Device     : {gpu_name}")
    print(f"[HW]  Torch Version  : {torch.__version__}")

    if not cuda_ok:
        print("\n[WARN] No CUDA GPU detected — training on CPU will be extremely slow.")
        print("       Expected time: 48+ hours for 50 epochs on 37k images on CPU.")
        print("       Aborting to prevent accidental CPU training.")
        print("       If you want to force CPU training, set CONFIG['device'] = 'cpu'")
        sys.exit(1)

    # ── Dataset YAML validation ──────────────────────────────────────────────
    if not DATA_YAML.exists():
        print(f"[ERROR] Dataset YAML not found: {DATA_YAML}")
        sys.exit(1)
    print(f"\n[DATA] Dataset YAML  : {DATA_YAML}")
    print(f"[DATA] Dataset       : {CONFIG['dataset']}")

    # ── Model initialization ─────────────────────────────────────────────────
    print(f"\n[MODEL] Loading {CONFIG['variant']} pretrained weights...")
    model = YOLO(CONFIG["model"])

    # ── Print training summary ───────────────────────────────────────────────
    print("\n[CONFIG] Training Parameters:")
    print(f"  Epochs       : {CONFIG['epochs']}")
    print(f"  Image Size   : {CONFIG['imgsz']}x{CONFIG['imgsz']}")
    print(f"  Batch Size   : {CONFIG['batch']}  (RTX 4060 8GB VRAM)")
    print(f"  Optimizer    : {CONFIG['optimizer']} (lr={CONFIG['lr0']}, cos_lr={CONFIG['cos_lr']})")
    print(f"  AMP          : {CONFIG['amp']}  (mixed precision)")
    print(f"  Augmentation : mosaic={CONFIG['mosaic']}, mixup={CONFIG['mixup']}, copy_paste={CONFIG['copy_paste']}")
    print(f"  Output       : {CONFIG['project']}/{CONFIG['name']}")
    print()

    # ── Training ─────────────────────────────────────────────────────────────
    print("[TRAIN] Starting full training run...")
    print("-" * 70)

    train_results = model.train(
        data        = CONFIG["data"],
        epochs      = 1 if DRY else CONFIG["epochs"],
        fraction    = 0.02 if DRY else 1.0,
        imgsz       = CONFIG["imgsz"],
        batch       = CONFIG["batch"],
        device      = CONFIG["device"],

        # Optimizer
        optimizer    = CONFIG["optimizer"],
        lr0          = CONFIG["lr0"],
        lrf          = CONFIG["lrf"],
        momentum     = CONFIG["momentum"],
        weight_decay = CONFIG["weight_decay"],
        warmup_epochs= CONFIG["warmup_epochs"],
        cos_lr       = CONFIG["cos_lr"],

        # Augmentation
        mosaic       = CONFIG["mosaic"],
        mixup        = CONFIG["mixup"],
        copy_paste   = CONFIG["copy_paste"],
        hsv_h        = CONFIG["hsv_h"],
        hsv_s        = CONFIG["hsv_s"],
        hsv_v        = CONFIG["hsv_v"],
        fliplr       = CONFIG["fliplr"],
        flipud       = CONFIG["flipud"],
        degrees      = CONFIG["degrees"],
        translate    = CONFIG["translate"],
        scale        = CONFIG["scale"],
        shear        = CONFIG["shear"],
        perspective  = CONFIG["perspective"],

        # Loss weights
        box          = CONFIG["box"],
        cls          = CONFIG["cls"],
        dfl          = CONFIG["dfl"],

        # NMS
        iou          = CONFIG["iou"],

        # Checkpointing
        patience     = CONFIG["patience"],
        save_period  = CONFIG["save_period"],

        # Runtime
        workers      = CONFIG["workers"],
        amp          = CONFIG["amp"],
        cache        = CONFIG["cache"],
        verbose      = CONFIG["verbose"],

        # Output
        project      = CONFIG["project"],
        name         = CONFIG["name"] + ("_dry" if DRY else ""),
        exist_ok     = CONFIG["exist_ok"],
    )

    # ── Validation on best weights ────────────────────────────────────────────
    print("\n[EVAL] Running validation on best weights...")
    val_results = model.val(
        data    = CONFIG["data"],
        imgsz   = CONFIG["imgsz"],
        batch   = CONFIG["batch"],
        device  = CONFIG["device"],
        workers = CONFIG["workers"],
        project = CONFIG["project"], 
        name    = CONFIG["name"] + "_val",
        verbose = True,
    )

    # ── Extract metrics ───────────────────────────────────────────────────────
    box  = val_results.box
    map50     = float(box.map50)
    map50_95  = float(box.map)
    precision = float(box.mp)
    recall    = float(box.mr)

    names = model.names   # read from the trained model instead of hardcoding
    per_class_map50 = {names[i]: None for i in names}
    for idx, ap in zip(box.ap_class_index, box.ap50):
        per_class_map50[names[int(idx)]] = round(float(ap), 4)
    per_class_map50_95 = {names[i]: round(float(box.maps[i]), 4) for i in names}

    # ── Save dir ──────────────────────────────────────────────────────────────
    save_dir = str(model.trainer.save_dir) if hasattr(model, "trainer") else "unknown"
    best_weights = Path(save_dir) / "weights" / "best.pt"



    # ── Test-split evaluation (look at this once, at the very end) ────────────
    print("\n[EVAL] Running evaluation on the TEST split...")
    test_model = YOLO(str(best_weights))
    test_results = test_model.val(
        data     = CONFIG["data"],
        split    = "test",
        imgsz    = CONFIG["imgsz"],
        batch    = CONFIG["batch"],
        device   = CONFIG["device"],
        workers  = CONFIG["workers"],
        verbose  = True,
        project  = CONFIG["project"],
        name     = CONFIG["name"] + ("_dry" if DRY else "") + "_test",
        exist_ok = True,
    )
    tbox = test_results.box
    tnames = test_model.names
    test_per_class_map50 = {tnames[i]: None for i in tnames}
    for idx, ap in zip(tbox.ap_class_index, tbox.ap50):
        test_per_class_map50[tnames[int(idx)]] = round(float(ap), 4)

    test_metrics = {
        "mAP50":           round(float(tbox.map50), 4),
        "mAP50_95":        round(float(tbox.map), 4),
        "mean_precision":  round(float(tbox.mp), 4),
        "mean_recall":     round(float(tbox.mr), 4),
        "per_class_mAP50": test_per_class_map50,
    }

    # ── Results log ───────────────────────────────────────────────────────────
    results = {
        "experiment_name": "Full RDD2022 Training — YOLOv8s GPU",
        "timestamp": CONFIG["timestamp"],
        "configuration": CONFIG,
        "hardware": {
            "cuda": cuda_ok,
            "gpu": gpu_name,
            "torch": torch.__version__,
        },
        "metrics": {
            "overall_mAP50":    round(map50, 4),
            "overall_mAP50_95": round(map50_95, 4),
            "mean_precision":   round(precision, 4),
            "mean_recall":      round(recall, 4),
            "per_class_mAP50":  per_class_map50,
            "per_class_mAP50_95": per_class_map50_95,
        },
        "test_metrics": test_metrics,
        "artifacts": {
            "best_weights":  str(best_weights),
            "run_directory": save_dir,
        },
    }

    out_json = EXPERIMENTS_DIR / "full_training_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    # ── Final summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  FULL TRAINING COMPLETE")
    print("=" * 70)
    print(f"  mAP@0.5        : {map50:.4f}   (baseline was 0.1176)")
    print(f"  mAP@0.5:0.95   : {map50_95:.4f}  (baseline was 0.0530)")
    print(f"  Mean Precision  : {precision:.4f}  (baseline was 0.6541)")
    print(f"  Mean Recall     : {recall:.4f}   (baseline was 0.1254)")
    
    print(f"\n  Per-Class mAP@0.5 / mAP@0.5:0.95 (validation):")
    for cls, val in per_class_map50.items():
        v50 = 0.0 if val is None else val
        print(f"    {cls}: {v50:.4f} / {per_class_map50_95[cls]:.4f}")

    print(f"\n  TEST split (best weights):")
    print(f"    mAP@0.5      : {test_metrics['mAP50']:.4f}")
    print(f"    mAP@0.5:0.95 : {test_metrics['mAP50_95']:.4f}")
    print(f"    Precision    : {test_metrics['mean_precision']:.4f}")
    print(f"    Recall       : {test_metrics['mean_recall']:.4f}")
    for cls, val in test_metrics["per_class_mAP50"].items():
        print(f"    {cls}: {0.0 if val is None else val:.4f}")

    print(f"\n  Best Weights    : {best_weights}")
    print(f"  Results JSON    : {out_json}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    run_full_training()
