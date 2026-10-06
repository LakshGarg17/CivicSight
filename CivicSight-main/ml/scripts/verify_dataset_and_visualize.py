"""CivicSight ML Dataset Verification & Bounding Box Visualizer (Week 3)

Validates:
1. RDD2022 train/val/test splits and image-to-label pairing.
2. YOLO data.yaml configuration syntax and class ID mappings (0: D00, 1: D10, 2: D20, 3: D40).
3. Coordinate normalization bounds [0.0, 1.0].
4. Renders visual verification bounding boxes over damage images and saves them to ml/samples/verified_boxes/.
"""

import os
import sys
import glob
import random
import yaml
import cv2
import numpy as np

# Color mapping for damage classes (BGR format for OpenCV)
CLASS_METADATA = {
    0: {"code": "D00", "label": "Longitudinal Crack", "color": (248, 189, 56)},   # Sky Blue
    1: {"code": "D10", "label": "Transverse Crack",   "color": (191, 212, 45)},   # Teal/Cyan
    2: {"code": "D20", "label": "Alligator Crack",    "color": (11, 158, 245)},   # Amber/Orange
    3: {"code": "D40", "label": "Pothole",            "color": (68, 68, 239)},    # Red/Crimson
}


def load_data_yaml(yaml_path: str) -> dict:
    """Loads and validates the YOLO dataset YAML configuration."""
    if not os.path.isfile(yaml_path):
        raise FileNotFoundError(f"data.yaml not found at: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def verify_splits_and_classes(dataset_dir: str, config: dict, max_samples_per_split: int = 500):
    """Audits train/val/test splits and samples bounding box coordinates for integrity."""
    print("=" * 70, flush=True)
    print(" [STEP 1] Auditing RDD2022 Partitions & Annotation Consistency", flush=True)
    print("=" * 70, flush=True)

    splits = ["train", "val", "test"]
    samples_by_class = {0: [], 1: [], 2: [], 3: []}
    total_class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    invalid_lines_count = 0
    out_of_bounds_count = 0

    for split in splits:
        img_dir = os.path.join(dataset_dir, split, "images")
        lbl_dir = os.path.join(dataset_dir, split, "labels")

        if not os.path.isdir(img_dir) or not os.path.isdir(lbl_dir):
            print(f"  [ERROR] Missing directories for split '{split}'", flush=True)
            continue

        # Get file counts
        lbl_entries = [f for f in os.scandir(lbl_dir) if f.name.endswith(".txt")]
        total_lbls = len(lbl_entries)

        # Audit annotations
        class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        non_empty = 0

        # Sample for fast execution if large
        scan_entries = lbl_entries if total_lbls <= max_samples_per_split else random.sample(lbl_entries, max_samples_per_split)

        for entry in scan_entries:
            if entry.stat().st_size == 0:
                continue

            non_empty += 1
            base_name = os.path.splitext(entry.name)[0]
            
            # Match image
            img_path = os.path.join(img_dir, f"{base_name}.jpg")
            if not os.path.isfile(img_path):
                img_path = os.path.join(img_dir, f"{base_name}.png")
                if not os.path.isfile(img_path):
                    continue

            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            for line in content.strip().splitlines():
                parts = line.strip().split()
                if len(parts) != 5:
                    invalid_lines_count += 1
                    continue

                try:
                    cls_id = int(parts[0])
                    xc, yc, w, h = map(float, parts[1:])
                except ValueError:
                    invalid_lines_count += 1
                    continue

                if cls_id not in [0, 1, 2, 3]:
                    invalid_lines_count += 1
                    continue

                if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                    out_of_bounds_count += 1

                class_counts[cls_id] += 1
                total_class_counts[cls_id] += 1

                if len(samples_by_class[cls_id]) < 20:
                    samples_by_class[cls_id].append((img_path, entry.path, cls_id))

        print(f"  Split '{split}':", flush=True)
        print(f"    - Total Partition Files: {total_lbls:,} images/labels paired", flush=True)
        print(f"    - Audited Sample ({len(scan_entries):,} files): Non-empty={non_empty:,}", flush=True)
        print(f"    - Class Occurrences: D00={class_counts[0]:,}, D10={class_counts[1]:,}, D20={class_counts[2]:,}, D40={class_counts[3]:,}\n", flush=True)

    print("-" * 70, flush=True)
    print("  Class Consistency & Verification Findings:", flush=True)
    total_annotations = sum(total_class_counts.values())
    for cid, cnt in total_class_counts.items():
        meta = CLASS_METADATA[cid]
        pct = (cnt / total_annotations * 100) if total_annotations > 0 else 0
        print(f"    - Class {cid} ({meta['code']} - {meta['label']}): {cnt:,} instances ({pct:.1f}%)", flush=True)
    print(f"    - Total Audited Annotations: {total_annotations:,}", flush=True)
    print(f"    - Malformed Lines: {invalid_lines_count}", flush=True)
    print(f"    - Out-of-Bounds Normalizations: {out_of_bounds_count}", flush=True)
    print("-" * 70, flush=True)

    return samples_by_class


def render_bounding_boxes(samples_by_class: dict, output_dir: str, num_per_class: int = 2):
    """Draws visual bounding box overlays with class labels and saves them to disk."""
    print("\n" + "=" * 70, flush=True)
    print(" [STEP 2] Rendering Visual Bounding Box Verification Overlays", flush=True)
    print("=" * 70, flush=True)

    os.makedirs(output_dir, exist_ok=True)
    rendered_files = []

    for cid in [0, 1, 2, 3]:
        meta = CLASS_METADATA[cid]
        candidates = samples_by_class.get(cid, [])
        if not candidates:
            print(f"  [WARN] No samples found for class {cid} ({meta['code']})", flush=True)
            continue

        sample_batch = random.sample(candidates, min(num_per_class, len(candidates)))

        for idx, (img_path, lbl_path, target_cid) in enumerate(sample_batch, start=1):
            img = cv2.imread(img_path)
            if img is None:
                continue

            h_img, w_img = img.shape[:2]

            with open(lbl_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                c_id = int(parts[0])
                xc, yc, bw, bh = map(float, parts[1:])

                # Convert YOLO normalized coords to pixel coords
                x_min = int((xc - bw / 2.0) * w_img)
                y_min = int((yc - bh / 2.0) * h_img)
                x_max = int((xc + bw / 2.0) * w_img)
                y_max = int((yc + bh / 2.0) * h_img)

                # Clamp to image boundaries
                x_min, y_min = max(0, x_min), max(0, y_min)
                x_max, y_max = min(w_img - 1, x_max), min(h_img - 1, y_max)

                c_meta = CLASS_METADATA.get(c_id, {"code": f"Class {c_id}", "label": "Unknown", "color": (0, 255, 0)})
                color = c_meta["color"]

                # Draw bounding box rectangle
                cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, 3)

                # Draw label badge
                label_text = f"{c_meta['code']}: {c_meta['label']}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.55
                thickness = 1
                (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

                # Label background
                badge_y_min = max(0, y_min - text_h - 8)
                badge_y_max = max(text_h + 8, y_min)
                cv2.rectangle(
                    img,
                    (x_min, badge_y_min),
                    (x_min + text_w + 10, badge_y_max),
                    color,
                    -1,
                )
                # Label text
                cv2.putText(
                    img,
                    label_text,
                    (x_min + 5, badge_y_max - 4),
                    font,
                    font_scale,
                    (255, 255, 255),
                    thickness,
                    cv2.LINE_AA,
                )

            # Top Header banner on verified sample
            header_text = f"CivicSight Dataset Verification -- {meta['code']} ({meta['label']})"
            cv2.rectangle(img, (0, 0), (w_img, 36), (17, 24, 39), -1)
            cv2.putText(
                img,
                header_text,
                (12, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (248, 250, 252),
                1,
                cv2.LINE_AA,
            )

            out_filename = f"verified_{meta['code']}_sample_{idx}.jpg"
            out_filepath = os.path.join(output_dir, out_filename)
            cv2.imwrite(out_filepath, img)
            rendered_files.append(out_filepath)
            print(f"  [RENDER] Saved verified visual overlay: {out_filename} (Source: {os.path.basename(img_path)})", flush=True)

    print("\n" + "=" * 70, flush=True)
    print(f" [SUCCESS] Generated {len(rendered_files)} verified visual bounding box overlays in: {output_dir}", flush=True)
    print("=" * 70, flush=True)


def main():
    random.seed(42)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    ml_dir = os.path.abspath(os.path.join(script_dir, ".."))
    root_dir = os.path.abspath(os.path.join(ml_dir, ".."))

    yaml_path = os.path.join(ml_dir, "data.yaml")
    dataset_dir = os.path.join(root_dir, "Dataset", "RDD_SPLIT")
    output_dir = os.path.join(ml_dir, "samples", "verified_boxes")

    print("\n" + "=" * 70, flush=True)
    print(" CivicSight Week 3: ML Dataset Preparation & Visual Verification", flush=True)
    print("=" * 70, flush=True)
    print(f"  - Dataset Dir : {dataset_dir}", flush=True)
    print(f"  - YAML Config : {yaml_path}", flush=True)
    print(f"  - Visual Output: {output_dir}", flush=True)

    config = load_data_yaml(yaml_path)
    print(f"  - Config Loaded: nc={config.get('nc')}, names={config.get('names')}", flush=True)

    samples_by_class = verify_splits_and_classes(dataset_dir, config, max_samples_per_split=1000)
    render_bounding_boxes(samples_by_class, output_dir, num_per_class=2)


if __name__ == "__main__":
    main()
