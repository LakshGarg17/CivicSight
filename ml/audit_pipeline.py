import os
import sys
import hashlib
from pathlib import Path
from collections import Counter
import yaml
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
print("=" * 75)
print("PHASE 1 — FORENSIC ML PIPELINE AUDIT")
print("=" * 75)

# --- 1A: Checkpoint Inspection ---
print("\n[1A] Checkpoint Forensic Analysis")
candidates = [
    PROJECT_ROOT / "ml" / "runs" / "detect" / "civicsight_yolov8n_4class" / "weights" / "best.pt",
    PROJECT_ROOT / "ml" / "runs" / "detect" / "experiment2_week5" / "weights" / "best.pt",
    PROJECT_ROOT / "ml" / "weights" / "best.pt",
    PROJECT_ROOT / "best.pt",
    PROJECT_ROOT / "yolov8n.pt",
]

for c in candidates:
    if c.is_file():
        sha = hashlib.sha256(c.read_bytes()).hexdigest()
        print(f"  Checkpoint: {c.relative_to(PROJECT_ROOT)}")
        print(f"    Size: {c.stat().st_size} bytes")
        print(f"    SHA256: {sha}")
        try:
            from ultralytics import YOLO
            m = YOLO(str(c))
            print(f"    Loaded successfully! Classes count: {len(m.names)}")
            print(f"    Classes: {m.names}")
        except Exception as e:
            print(f"    Failed to load: {e}")
    else:
        print(f"  Checkpoint (MISSING): {c.relative_to(PROJECT_ROOT)}")

# --- 1B: Dataset Inspection (RDD_SPLIT vs data_4class) ---
print("\n[1B] Dataset and Splits Forensic Analysis")
rdd_dir = PROJECT_ROOT / "RDD_SPLIT"
print(f"  Raw RDD_SPLIT Directory: {rdd_dir.is_dir()}")
if rdd_dir.is_dir():
    rdd_yaml = rdd_dir / "data.yaml"
    if rdd_yaml.is_file():
        print(f"  Raw RDD data.yaml:\n{rdd_yaml.read_text().strip()}")
    
    for split in ["train", "val", "test"]:
        s_lbl = rdd_dir / split / "labels"
        s_img = rdd_dir / split / "images"
        lbl_count = len(list(s_lbl.glob("*.txt"))) if s_lbl.is_dir() else 0
        img_count = len(list(s_img.glob("*.jpg"))) if s_img.is_dir() else 0
        print(f"    RDD_SPLIT {split}: {lbl_count} labels, {img_count} images")

data_4class_dir = PROJECT_ROOT / "ml" / "data_4class"
print(f"\n  data_4class Directory: {data_4class_dir.is_dir()}")
if data_4class_dir.is_dir():
    for split in ["train", "val", "test"]:
        s_lbl = data_4class_dir / split / "labels"
        s_img = data_4class_dir / split / "images"
        classes = Counter()
        total_boxes = 0
        empty_files = 0
        total_files = 0
        for f in s_lbl.glob("*.txt"):
            total_files += 1
            lines = f.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            if not lines:
                empty_files += 1
            for l in lines:
                parts = l.strip().split()
                if len(parts) >= 5:
                    classes[int(parts[0])] += 1
                    total_boxes += 1
        img_count = len(list(s_img.glob("*.jpg"))) if s_img.is_dir() else 0
        print(f"    data_4class {split}: {total_files} labels ({empty_files} empty), {img_count} images, {total_boxes} boxes")
        print(f"      Classes: {dict(sorted(classes.items()))}")

# --- 1C: Training History Inspection ---
print("\n[1C] Training Run Artifacts Inspection")
runs_dir = PROJECT_ROOT / "ml" / "runs" / "detect"
if runs_dir.is_dir():
    for run in runs_dir.iterdir():
        if run.is_dir():
            args_file = run / "args.yaml"
            res_file = run / "results.csv"
            print(f"  Run Directory: {run.name}")
            if args_file.is_file():
                with open(args_file, "r") as f:
                    args = yaml.safe_load(f)
                print(f"    Model base: {args.get('model')}")
                print(f"    Data: {args.get('data')}")
                print(f"    Epochs: {args.get('epochs')}")
                print(f"    Batch: {args.get('batch')}")
                print(f"    Imgsz: {args.get('imgsz')}")
                print(f"    Device: {args.get('device')}")
            if res_file.is_file():
                lines = res_file.read_text().strip().splitlines()
                print(f"    Total recorded epochs in results.csv: {len(lines) - 1}")
                if len(lines) > 1:
                    print(f"    Final epoch stats: {lines[-1]}")
