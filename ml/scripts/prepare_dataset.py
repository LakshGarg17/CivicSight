"""CivicSight ML Subsystem — Fast 4-Class Dataset Preparation & Remapping

Extracts, remaps, and balances the RDD2022 dataset for the 4 target road damage classes:
  - 0: D00 (Longitudinal Crack)
  - 1: D10 (Transverse Crack)
  - 2: D20 (Alligator Crack)
  - 3: D40 (Pothole — remapped from raw class 4)
"""

import os
import shutil
import random
from pathlib import Path
from collections import defaultdict, Counter
import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_RDD_DIR = ROOT_DIR / "RDD_SPLIT"
OUTPUT_DATASET_DIR = ROOT_DIR / "ml" / "data_4class"
YAML_OUTPUT_PATH = ROOT_DIR / "ml" / "data_4class.yaml"

CLASS_NAMES = {
    0: "D00",
    1: "D10",
    2: "D20",
    3: "D40",
}

RAW_TO_TARGET = {
    0: 0,
    1: 1,
    2: 2,
    4: 3,
}


def build_4class_dataset(
    train_samples_per_class: int = 150,
    train_clean_samples: int = 80,
    val_samples_per_class: int = 40,
    val_clean_samples: int = 30,
    test_samples_per_class: int = 40,
    test_clean_samples: int = 30,
    seed: int = 42,
):
    random.seed(seed)
    print("=" * 70, flush=True)
    print("CivicSight — Fast 4-Class Dataset Preparation", flush=True)
    print("=" * 70, flush=True)

    for split in ["train", "val", "test"]:
        os.makedirs(OUTPUT_DATASET_DIR / split / "images", exist_ok=True)
        os.makedirs(OUTPUT_DATASET_DIR / split / "labels", exist_ok=True)

    def process_split(split_name: str, target_per_class: int, target_clean: int):
        src_img_dir = RAW_RDD_DIR / split_name / "images"
        src_lbl_dir = RAW_RDD_DIR / split_name / "labels"
        dst_img_dir = OUTPUT_DATASET_DIR / split_name / "images"
        dst_lbl_dir = OUTPUT_DATASET_DIR / split_name / "labels"

        # Clear existing
        for entry in os.scandir(dst_img_dir):
            os.remove(entry.path)
        for entry in os.scandir(dst_lbl_dir):
            os.remove(entry.path)

        lbl_entries = [e for e in os.scandir(src_lbl_dir) if e.name.endswith(".txt")]
        random.shuffle(lbl_entries)

        class_files = defaultdict(list)
        clean_files = []

        for entry in lbl_entries:
            # Check if all quotas reached
            if (
                len(class_files[0]) >= target_per_class
                and len(class_files[1]) >= target_per_class
                and len(class_files[2]) >= target_per_class
                and len(class_files[3]) >= target_per_class
                and len(clean_files) >= target_clean
            ):
                break

            try:
                with open(entry.path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
            except Exception:
                continue

            boxes = []
            if content:
                for line in content.splitlines():
                    parts = line.strip().split()
                    if len(parts) != 5:
                        continue
                    try:
                        raw_c = int(parts[0])
                        xc, yc, w, h = map(float, parts[1:])
                    except ValueError:
                        continue

                    if raw_c in RAW_TO_TARGET:
                        tc = RAW_TO_TARGET[raw_c]
                        xc = max(0.0, min(1.0, xc))
                        yc = max(0.0, min(1.0, yc))
                        w = max(0.0001, min(1.0, w))
                        h = max(0.0001, min(1.0, h))
                        boxes.append((tc, xc, yc, w, h))

            stem = entry.name[:-4]
            img_name = f"{stem}.jpg"
            img_path = src_img_dir / img_name
            if not img_path.exists():
                img_name = f"{stem}.png"
                img_path = src_img_dir / img_name
            if not img_path.exists():
                continue

            if not boxes:
                if len(clean_files) < target_clean:
                    clean_files.append((img_path, entry.path, []))
            else:
                classes_present = {b[0] for b in boxes}
                if 3 in classes_present and len(class_files[3]) < target_per_class:
                    class_files[3].append((img_path, entry.path, boxes))
                elif 2 in classes_present and len(class_files[2]) < target_per_class:
                    class_files[2].append((img_path, entry.path, boxes))
                elif 1 in classes_present and len(class_files[1]) < target_per_class:
                    class_files[1].append((img_path, entry.path, boxes))
                elif 0 in classes_present and len(class_files[0]) < target_per_class:
                    class_files[0].append((img_path, entry.path, boxes))

        print(f"[Split: {split_name.upper()}] Selected: D00={len(class_files[0])}, D10={len(class_files[1])}, D20={len(class_files[2])}, D40={len(class_files[3])}, Clean={len(clean_files)}", flush=True)

        selected_images = set()
        box_counts = Counter()

        for c in range(4):
            for img_p, lbl_p, boxes in class_files[c]:
                if img_p.name in selected_images:
                    continue
                selected_images.add(img_p.name)

                shutil.copyfile(img_p, dst_img_dir / img_p.name)
                dst_lbl = dst_lbl_dir / f"{img_p.stem}.txt"
                with open(dst_lbl, "w", encoding="utf-8") as f:
                    for b in boxes:
                        f.write(f"{b[0]} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}\n")
                        box_counts[b[0]] += 1

        for img_p, lbl_p, _ in clean_files:
            if img_p.name in selected_images:
                continue
            selected_images.add(img_p.name)

            shutil.copyfile(img_p, dst_img_dir / img_p.name)
            dst_lbl = dst_lbl_dir / f"{img_p.stem}.txt"
            dst_lbl.touch()

        print(f"  -> Built '{split_name}': {len(selected_images)} total images. Boxes: D00={box_counts[0]}, D10={box_counts[1]}, D20={box_counts[2]}, D40={box_counts[3]}", flush=True)

    process_split("train", train_samples_per_class, train_clean_samples)
    process_split("val", val_samples_per_class, val_clean_samples)
    process_split("test", test_samples_per_class, test_clean_samples)

    yaml_config = {
        "path": str(OUTPUT_DATASET_DIR.resolve()).replace("\\", "/"),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": 4,
        "names": {
            0: "D00",
            1: "D10",
            2: "D20",
            3: "D40",
        },
    }

    with open(YAML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(yaml_config, f, sort_keys=False)

    print(f"\n[OK] 4-class dataset configuration saved to: {YAML_OUTPUT_PATH}", flush=True)
    return YAML_OUTPUT_PATH


if __name__ == "__main__":
    build_4class_dataset()
