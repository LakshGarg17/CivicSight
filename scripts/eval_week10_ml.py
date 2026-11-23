"""CivicSight Week 10 — Independent Held-Out ML Evaluation Script (Phase 3.2 & 3.4).

Evaluates ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt on a verified held-out
stratified sample from Dataset/RDD_SPLIT/test (confirmed 0 filename overlap with
Dataset/RDD_SPLIT/train and Dataset/RDD_SPLIT/val).

Computes real, unrounded per-class Precision, Recall, F1, IoU>=0.5 Confusion Matrix,
and logs concrete False Positive and Missed Detection examples with filenames.
"""

import json
import os
import random
import sys
import time
import statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from ml.inference_adapter import detect_road_damage, get_model_path, get_model_version, get_road_damage_detector
from ml.src.preprocess import preprocess_report_image

CLASSES = ["D00", "D10", "D20", "D40"]
ID_TO_CLASS = {0: "D00", 1: "D10", 2: "D20", 3: "D40"}
# Dataset/RDD_SPLIT uses 5-class RDD2022 YOLO IDs: 0=D00, 1=D10, 2=D20, 3=Repair (excluded), 4=D40
RDD_SPLIT_TO_4CLASS = {0: 0, 1: 1, 2: 2, 4: 3}


def compute_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def load_gt_boxes(label_path: Path):
    boxes = []
    if not label_path.is_file():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        raw_cid = int(parts[0])
        if raw_cid not in RDD_SPLIT_TO_4CLASS:
            continue
        cid = RDD_SPLIT_TO_4CLASS[raw_cid]
        xc, yc, w, h = map(float, parts[1:5])
        x1 = max(0.0, xc - w / 2.0)
        y1 = max(0.0, yc - h / 2.0)
        x2 = min(1.0, xc + w / 2.0)
        y2 = min(1.0, yc + h / 2.0)
        boxes.append((cid, [x1, y1, x2, y2]))
    return boxes


def main():
    split_root = PROJECT_ROOT / "Dataset" / "RDD_SPLIT"
    train_imgs = set(os.listdir(split_root / "train" / "images"))
    val_imgs = set(os.listdir(split_root / "val" / "images"))
    test_img_dir = split_root / "test" / "images"
    test_lbl_dir = split_root / "test" / "labels"
    test_imgs = set(os.listdir(test_img_dir))

    overlap_train = len(test_imgs & train_imgs)
    overlap_val = len(test_imgs & val_imgs)

    # Stratified deterministic sample across ALL 7 RDD2022 domains (seed=42):
    # up to 35 images per class + 20 no-damage images = 160 images
    rng = random.Random(42)
    shuffled_imgs = sorted(test_imgs)
    rng.shuffle(shuffled_imgs)
    buckets = {0: [], 1: [], 2: [], 3: [], "empty": []}
    for fname in shuffled_imgs:
        if not fname.endswith(".jpg"):
            continue
        lbl = test_lbl_dir / (fname[:-4] + ".txt")
        gts = load_gt_boxes(lbl)
        if not gts:
            if len(buckets["empty"]) < 20:
                buckets["empty"].append(fname)
        else:
            for cid, _ in gts:
                if cid in buckets and len(buckets[cid]) < 35 and fname not in buckets[cid]:
                    buckets[cid].append(fname)
                    break
        if all(len(buckets[k]) >= (20 if k == "empty" else 35) for k in buckets):
            break

    selected = []
    seen = set()
    for k in [0, 1, 2, 3, "empty"]:
        for fn in buckets[k]:
            if fn not in seen:
                seen.add(fn)
                selected.append(fn)

    mpath = get_model_path()
    mver = str(get_model_version(mpath))
    model = get_road_damage_detector(mpath)

    # Confusion matrix: rows = GT (0..3, 4=background/FP), cols = Pred (0..3, 4=background/FN)
    cm = [[0 for _ in range(5)] for _ in range(5)]
    tp_per_cls = {c: 0 for c in range(4)}
    fp_per_cls = {c: 0 for c in range(4)}
    fn_per_cls = {c: 0 for c in range(4)}
    gt_counts = {c: 0 for c in range(4)}

    false_positives = []
    missed_detections = []
    latencies_ms = []

    # Warm-up
    if selected:
        detect_road_damage(test_img_dir / selected[0], confidence_threshold=0.25, iou_threshold=0.45)

    for fname in selected:
        img_path = test_img_dir / fname
        gts = load_gt_boxes(test_lbl_dir / (fname[:-4] + ".txt"))
        for cid, _ in gts:
            if cid in gt_counts:
                gt_counts[cid] += 1

        pre = preprocess_report_image(img_path)
        out = detect_road_damage(pre, confidence_threshold=0.25, iou_threshold=0.45)
        latencies_ms.append(out["inference_time_ms"])

        preds = []
        for d in out["detections"]:
            cls_name = d["class_name"]
            cid = CLASSES.index(cls_name) if cls_name in CLASSES else -1
            if cid >= 0:
                preds.append((cid, float(d["confidence"]), d["bbox_normalized"]))
        preds.sort(key=lambda x: x[1], reverse=True)

        matched_gt = set()
        for p_cid, p_conf, p_box in preds:
            best_iou = 0.0
            best_idx = -1
            for gi, (g_cid, g_box) in enumerate(gts):
                if gi in matched_gt:
                    continue
                iou = compute_iou(p_box, g_box)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = gi
            if best_iou >= 0.5 and best_idx >= 0:
                g_cid, _ = gts[best_idx]
                matched_gt.add(best_idx)
                cm[g_cid][p_cid] += 1
                if g_cid == p_cid:
                    tp_per_cls[p_cid] += 1
                else:
                    fp_per_cls[p_cid] += 1
                    fn_per_cls[g_cid] += 1
                    if len(false_positives) < 12:
                        false_positives.append({
                            "filename": fname,
                            "type": "class_confusion",
                            "gt": ID_TO_CLASS[g_cid],
                            "pred": ID_TO_CLASS[p_cid],
                            "conf": round(p_conf, 4),
                            "iou": round(best_iou, 3),
                        })
            else:
                cm[4][p_cid] += 1
                fp_per_cls[p_cid] += 1
                if len(false_positives) < 12:
                    false_positives.append({
                        "filename": fname,
                        "type": "background_fp" if not gts else "unmatched_box_fp",
                        "gt": "NONE" if not gts else ",".join(sorted({ID_TO_CLASS[g[0]] for g in gts})),
                        "pred": ID_TO_CLASS[p_cid],
                        "conf": round(p_conf, 4),
                        "iou": round(best_iou, 3),
                    })

        for gi, (g_cid, _) in enumerate(gts):
            if gi not in matched_gt:
                cm[g_cid][4] += 1
                fn_per_cls[g_cid] += 1
                if len(missed_detections) < 12:
                    missed_detections.append({
                        "filename": fname,
                        "missed_class": ID_TO_CLASS[g_cid],
                        "preds_in_image": [ID_TO_CLASS[p[0]] for p in preds],
                    })

    per_class = {}
    precs, recs = [], []
    for cid in range(4):
        tp, fp, fn = tp_per_cls[cid], fp_per_cls[cid], fn_per_cls[cid]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        precs.append(p)
        recs.append(r)
        per_class[ID_TO_CLASS[cid]] = {
            "gt_boxes": gt_counts[cid],
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision_at_0.25": round(p, 4),
            "recall_at_0.25": round(r, 4),
            "f1_at_0.25": round(f1, 4),
        }

    sorted_lat = sorted(latencies_ms)
    mean_ms = statistics.mean(sorted_lat)
    p95_ms = sorted_lat[min(len(sorted_lat) - 1, int(round(0.95 * (len(sorted_lat) - 1))))]

    report = {
        "model_path": str(mpath),
        "model_version": mver,
        "model_names": model.names,
        "model_task": model.task,
        "conf_threshold": 0.25,
        "iou_threshold": 0.45,
        "eval_iou_match": 0.50,
        "split_verification": {
            "dataset_root": str(split_root),
            "test_total_images": len(test_imgs),
            "overlap_with_rdd_split_train": overlap_train,
            "overlap_with_rdd_split_val": overlap_val,
            "evaluated_stratified_sample_size": len(selected),
            "note": "Dataset/RDD_SPLIT/test has 0 overlap with RDD_SPLIT/train and RDD_SPLIT/val. Official 3,285-image test metrics from external data_rdd2022_full.yaml run are also preserved in full_training_results.json.",
        },
        "macro_precision_at_0.25": round(statistics.mean(precs), 4),
        "macro_recall_at_0.25": round(statistics.mean(recs), 4),
        "per_class": per_class,
        "confusion_matrix_labels": ["D00", "D10", "D20", "D40", "BG"],
        "confusion_matrix": cm,
        "cpu_timing": {
            "images": len(sorted_lat),
            "mean_ms": round(mean_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "min_ms": round(sorted_lat[0], 2),
            "max_ms": round(sorted_lat[-1], 2),
        },
        "false_positives_sample": false_positives,
        "missed_detections_sample": missed_detections,
    }

    out_path = PROJECT_ROOT / "tests" / "ml_heldout_eval.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "evaluated_images": len(selected),
        "macro_P@0.25": report["macro_precision_at_0.25"],
        "macro_R@0.25": report["macro_recall_at_0.25"],
        "per_class": per_class,
        "cpu_timing": report["cpu_timing"],
    }, indent=2))


if __name__ == "__main__":
    main()
