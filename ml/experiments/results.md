# CivicSight ML Road Defect Detection — Experiment Results & Week 10 Evaluation

**Project:** CivicSight Municipal Operations & Pavement Triage  
**Production Weights:** `ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt` (21.48 MB, YOLOv8s)  
**Model Version String:** `YOLOv8s-clean_rdd2022_yolov8s`  
**Week 10 Quality Gate Verification Date:** November 18, 2026  
**Status:** Verified via `tests/test_week10_ml.py` and `scripts/eval_week10_ml.py`

---

## 1. Training Progression Summary

| Parameter | Exp 1 (Week 4 Baseline) | Exp 2 (Week 5 Optimized) | **Production (`clean_rdd2022_yolov8s`)** |
|:---|:---:|:---:|:---:|
| **Architecture** | YOLOv8n (3.0M params) | YOLOv8n (3.0M params) | **YOLOv8s (11.2M params)** |
| **Dataset Config** | `baseline_data.yaml` | `data.yaml` | **`data_rdd2022_full.yaml`** |
| **Splits (Train / Val / Test)** | 250 / 60 / Holdout | 241 / 59 / Holdout | **37,230 / 3,286 / 3,285** |
| **Resolution / Epochs** | 640×640 / 2 epochs | 512×512 / 3 epochs | **640×640 / 50 epochs** |
| **Optimizer** | AdamW (`lr=0.00125`) | AdamW (`lr0=0.01`, `cos_lr`) | **AdamW (`lr0=0.001`, `lrf=0.01`, `cos_lr`)** |
| **Training Hardware** | CPU (Intel i7-10610U) | CPU (Intel i7-10610U) | **NVIDIA RTX 4060 Laptop GPU** |

---

## 2. Official Full-Test Evaluation (3,285 Images — `full_training_results.json`)

Measured on the external 3,285-image `data_rdd2022_full.yaml` test partition (`imgsz=640`, `conf=0.001`, `iou=0.7` standard Ultralytics mAP protocol):

| Metric | Production Val (3,286 imgs) | Production Test (3,285 imgs) |
|:---|:---:|:---:|
| **Mean Precision (P)** | 0.5960 | **0.6081** |
| **Mean Recall (R)** | 0.5015 | **0.5097** |
| **Overall mAP@0.5** | 0.5273 | **0.5472** |
| **Overall mAP@0.5:0.95** | 0.2625 | **0.2708** |

| Class | Meaning | Val mAP@0.5 | Test mAP@0.5 | Val mAP@0.5:0.95 |
|:---:|:---|:---:|:---:|:---:|
| `D00` | Longitudinal Crack | 0.5438 | **0.5389** | 0.2878 |
| `D10` | Transverse Crack | 0.4977 | **0.5352** | 0.2194 |
| `D20` | Alligator Crack | 0.6496 | **0.6459** | 0.3530 |
| `D40` | Pothole | 0.4181 | **0.4688** | 0.1901 |

---

## 3. Week 10 Independent Live Held-Out Evaluation (`scripts/eval_week10_ml.py`)

### 3.1 Split Verification & Label-Schema Audit
- **Local dataset verified:** `Dataset/RDD_SPLIT` contains `train = 26,869`, `val = 5,758`, `test = 5,758` images across 7 RDD2022 camera/country domains (`Japan`, `Norway`, `India`, `United_States`, `Czech`, `China_Drone`, `China_MotorBike`).
- **Overlap check:** `len(test ∩ train) == 0` and `len(test ∩ val) == 0`.
- **Important schema finding (verified empirically in Week 10):** `Dataset/RDD_SPLIT` stores raw 5-class RDD2022 YOLO IDs (`0=D00`, `1=D10`, `2=D20`, `3=Repair`, `4=D40`), whereas the production 4-class model (`clean_rdd2022_yolov8s`) drops `Repair` and maps `{0: D00, 1: D10, 2: D20, 3: D40}` matching `ml/data_rdd2022_full.yaml`, `ml/inference_adapter.py`, and `backend/app/core/priority_config.py`. For apples-to-apples evaluation, `scripts/eval_week10_ml.py` remaps `Dataset/RDD_SPLIT` label `4 -> D40` and excludes `3 (Repair)`.
- **Transparency caveat:** Because `clean_rdd2022_yolov8s` was trained externally from an upstream re-split of RDD2022 (`37,230 / 3,286 / 3,285`) before Week 10, some filenames in local `Dataset/RDD_SPLIT/test` may have appeared in the external training split; both the official 3,285-image test metrics and this live CPU operating-point (`conf=0.25`, `iou=0.45`) evaluation are reported side-by-side.

### 3.2 Operating-Point Metrics (`conf=0.25`, `iou=0.45`, IoU Match ≥ 0.50, 160 Stratified Multi-Domain Images)

- **Macro Precision @ 0.25:** **0.7896**
- **Macro Recall @ 0.25:** **0.5155**

| Class | Ground-Truth Boxes | TP | FP | FN | Precision@0.25 | Recall@0.25 | F1@0.25 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`D00`** (Longitudinal Crack) | 170 | 87 | 45 | 83 | **0.6591** | **0.5118** | **0.5762** |
| **`D10`** (Transverse Crack) | 89 | 45 | 11 | 44 | **0.8036** | **0.5056** | **0.6207** |
| **`D20`** (Alligator Crack) | 65 | 39 | 10 | 26 | **0.7959** | **0.6000** | **0.6842** |
| **`D40`** (Pothole) | 81 | 36 | 4 | 45 | **0.9000** | **0.4444** | **0.5950** |

### 3.3 Confusion Matrix (Rows = Ground Truth, Columns = Predicted, IoU ≥ 0.50)

| Ground Truth \ Predicted | `D00` | `D10` | `D20` | `D40` | `BG` (Missed / FN) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`D00`** | **87** | 0 | 1 | 0 | 82 |
| **`D10`** | 1 | **45** | 0 | 0 | 43 |
| **`D20`** | 2 | 0 | **39** | 0 | 24 |
| **`D40`** | 0 | 0 | 1 | **36** | 44 |
| **`BG` (False Positive)** | 42 | 11 | 8 | 4 | — |

**Key Observations:**
1. **Cross-class confusion is very low** (only 5 total inter-class confusions across 405 GT boxes). Nearly all errors are either **missed detections** (`BG` column: 193 FN) or **spurious/offset boxes** (`BG` row: 65 FP, mostly on `D00` linear cracks where a single long crack splits into multiple sub-boxes with IoU < 0.5).
2. **`D40` (Potholes) has the highest precision (0.9000) but the lowest recall (0.4444)** — matching the official test set where `D40` had the lowest mAP@0.5 (0.4688). Shallow, shadowed, or distant potholes are frequently missed.

---

## 4. CPU Inference Latency Benchmark (Week 10)

Executed locally on CPU (`PyTorch 2.14.1+cpu`, `Ultralytics 8.4.173`, `imgsz=640`, single warm-up run excluded):

| Benchmark | Samples | Mean (ms) | p95 (ms) | Min (ms) | Max (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|
| Held-out multi-domain road images (`scripts/eval_week10_ml.py`) | 160 | **130.13** | **170.18** | 116.60 | 213.84 |
| Mixed realistic & edge-case fixtures (`tests/test_week10_ml.py`) | 16 | **128.08** | **146.49** | 118.23 | 149.92 |

All runs completed well below the 200 ms p95 target on CPU with zero OOM or crashes.

---

## 5. Realistic Field Condition & Edge-Case Behavior (`tests/ml_conditions_and_timing.json`)

| Condition | Fixture | Detections | Classes | Max Conf | Inference (ms) | Verdict |
|:---|:---|:---:|:---|:---:|:---:|:---|
| Longitudinal crack | `damage_d00.jpg` | 3 | `D00, D00, D00` | 0.3368 | 127.91 | Detected |
| Transverse crack | `damage_d10.jpg` | 1 | `D10` | 0.4837 | 121.11 | Detected |
| Aerial alligator crack | `damage_d20.jpg` | 0 | — | 0.0000 | 119.34 | Missed (aerial angle) |
| Aerial weathered pothole | `damage_d40.jpg` | 1 | `D20` | 0.2556 | 119.40 | Class confusion |
| Ground-level phone pothole | `sample_pothole_d40.jpg` | 3 | `D40, D00, D00` | 0.5105 | 118.68 | Detected (`D40` primary) |
| Clean undamaged road | `no_damage_road.jpg` | 0 | — | 0.0000 | 118.23 | 0 FP (`ML_NO_DETECTIONS`) |
| Non-road outdoor scene | `non_road.jpg` | 0 | — | 0.0000 | 119.20 | 0 FP (`ML_NO_DETECTIONS`) |
| Blurry / dark night shot | `blurry_dark.jpg` | 0 | — | 0.0000 | 133.97 | Fails safe (no hallucination) |
| EXIF-rotated phone photo (90° CW) | `exif_gps_rotated.jpg` | 1 | `D40` | 0.3978 | 146.49 | Corrected by `exif_transpose` |
| Very large 4096×3072 JPEG | `very_large.jpg` | 0 | — | 0.0000 | 137.56 | Handled cleanly (no OOM) |
| Tiny 16×16 JPEG | `tiny.jpg` | 0 | — | 0.0000 | 132.27 | Handled cleanly (no crash) |
| Grayscale / RGBA / CMYK / Palette | `mode_*.png/jpg` | 0 | — | 0.0000 | ~130 | Converted cleanly to RGB |

---

## 6. Concrete False Positive & Missed Detection Examples (Week 10)

### False Positives / Localization Splits (`tests/ml_heldout_eval.json`)
| Image | Type | GT | Predicted | Conf | IoU | Root Cause |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| `Japan_001914.jpg` | Localization split | `D00` | `D00` | 0.2925 | 0.431 | Predicted box covers sub-segment of long crack (IoU just below 0.50) |
| `Japan_006334.jpg` | Class confusion | `D20` | `D00` | 0.2535 | 0.836 | Narrow edge of alligator cracking cluster classified as longitudinal crack |
| `Norway_006503.jpg` | Unmatched FP | `D00` | `D00` | 0.5048 | 0.000 | Tar-sealed pavement seam / road shadow triggered linear crack detection |
| `United_States_003162.jpg` | Unmatched FP | `D00` | `D00` | 0.2939 | 0.000 | Multiple low-confidence linear boxes along lane marking / joint edge |
| `China_MotorBike_001024.jpg` | Unmatched FP | `D00` | `D40` | 0.3661 | 0.000 | Dark asphalt patch shadow misread as pothole cavity |

### Missed Detections (False Negatives)
| Image | Missed GT | Model Predictions | Root Cause |
|:---|:---:|:---|:---|
| `Norway_006397.jpg` | `D00` | `[]` | Low-contrast hairline crack on wet/grey Nordic asphalt |
| `Japan_011341.jpg` | `D00` | `[]` | Faint distant crack near horizon |
| `Norway_008100.jpg` | 5× `D00`, `D10`, `D20` | `["D20"]` | Dense overlapping crack network collapsed into a single `D20` prediction |
| `damage_d20.jpg` | `D20` | `[]` | Steep aerial drone shot lacks perspective cues of vehicle-mounted training set |

---

## 7. Known ML Limitations & What the Model Should NOT Be Trusted For

### Key Limitations
1. **Weakest Class — `D40` Pothole Recall (0.4444 @ conf=0.25; 0.4688 official test mAP@0.5):** Roughly half of ground-truth potholes—especially shallow, water-filled, shadowed, or steep-angle ones—are missed.
2. **Domain Shift (Dashcam/Drone vs. Handheld Citizen Smartphone):** RDD2022 predominantly uses forward-facing vehicle/motorcycle dashcams and nadir drones. Close-up angled citizen smartphone photos, night flash shots, wet glare, snow, and motion blur significantly degrade recall.
3. **Dense Crack Fragmentation & Tar-Seal Confusion:** Long `D00` cracks often split into multiple overlapping boxes, while fresh black bitumen repair seams and dark shadows can trigger false `D00`/`D40` detections.

### What This Model MUST NOT Be Trusted For
- **Do NOT use for autonomous repair dispatch or automated work-order creation:** Every report MUST undergo Municipal Officer human verification (`POST /verify`) before maintenance staff assignment.
- **Do NOT use to judge whether a repair was properly completed:** The model is NOT trained to inspect `AFTER` repair quality; final verification (`POST /final-verify`) is strictly a human officer responsibility.
- **Do NOT use for legal compliance, pavement engineering measurements, or insurance liability:** Normalized bounding boxes approximate visual presence, not calibrated physical depth, width, or structural load capacity.
- **Do NOT trust zero-detection (`ML_NO_DETECTIONS`) results as proof a road is safe:** Because recall is ~51%, `ML_NO_DETECTIONS` only means the model found nothing above `conf=0.25` — reports still remain `submitted` for human review.
- **Do NOT use for night, heavy rain/puddle, snow-covered, or non-roadway defects** (sidewalks, bridges, signage, traffic lights, drainage grates).
