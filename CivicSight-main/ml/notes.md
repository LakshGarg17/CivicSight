# CivicSight ML Subsystem — Research Notes & Dataset Preparation (Week 3)

**Author / Maintainer:** Pranay (ML Lead)  
**Phase:** Week 3 — Dataset Preparation, YOLO Config (`data.yaml`), Class ID Verification & Visual Annotation Auditing  
**Status:** ✅ Splits Organized, Configuration Validated & Visual Ground Truth Verified

---

## 1. RDD2022 Dataset Split Organization

The **RDD2022 (Road Damage Dataset 2022)** has been structured into standard Ultralytics YOLO partitions under `Dataset/RDD_SPLIT/`:

```text
Dataset/RDD_SPLIT/
├── train/
│   ├── images/     # 26,869 training images (.jpg / .png) (~70%)
│   └── labels/     # 26,869 YOLO annotation files (.txt)
├── val/
│   ├── images/     # 5,758 validation images (.jpg / .png) (~15%)
│   └── labels/     # 5,758 YOLO annotation files (.txt)
└── test/
    ├── images/     # 5,758 holdout test images (.jpg / .png) (~15%)
    └── labels/     # 5,758 YOLO annotation files (.txt)
```

### Split Integrity & Pairing
- **Total Paired Samples:** **38,385** image-annotation pairs across all partitions.
- **Image-to-Annotation Mapping:** 100% paired by basename across all three partitions.
- **Annotation Format:** Zero-indexed normalized YOLO coordinates:
  ```text
  <class_id> <x_center> <y_center> <width> <height>
  ```
  where `x_center`, `y_center`, `width`, `height` are float values strictly bounded within `[0.0, 1.0]`.

---

## 2. YOLO Dataset Configuration (`ml/data.yaml`)

The dataset configuration file [`ml/data.yaml`](file:///d:/Projects/CivicSight/ml/data.yaml) connects YOLOv8 to the organized dataset splits:

```yaml
# CivicSight — Road Damage Detection YOLO Dataset Configuration (Week 3)
path: ../Dataset/RDD_SPLIT
train: train/images
val: val/images
test: test/images

nc: 4

names:
  0: D00  # Longitudinal Crack (parallel to road direction)
  1: D10  # Transverse Crack (perpendicular to road direction)
  2: D20  # Alligator Crack (fatigue mesh / structural base damage)
  3: D40  # Pothole (critical cavity / high traffic hazard)
```

---

## 3. Class ID Consistency Verification

Automated verification was conducted via [`ml/scripts/verify_dataset_and_visualize.py`](file:///d:/Projects/CivicSight/ml/scripts/verify_dataset_and_visualize.py):

| Class ID | Code | Damage Category | Full Dataset Annotations | Distribution (%) | Severity Impact |
|:---:|:---:|:---|:---:|:---:|:---|
| `0` | **`D00`** | **Longitudinal Crack** | 26,016 | **44.0%** | Medium (Water ingress risk) |
| `1` | **`D10`** | **Transverse Crack** | 11,830 | **20.0%** | Medium (Thermal / Joint fatigue) |
| `2` | **`D20`** | **Alligator Crack** | 10,617 | **17.9%** | High (Base layer failure) |
| `3` | **`D40`** | **Pothole** | 10,705 | **18.1%** | Critical (Immediate traffic hazard) |
| **Total** | — | — | **59,168** | **100.0%** | — |

### Verification Assertions
1. **Class ID Range:** All non-empty label lines strictly contain integer class IDs in `{0, 1, 2, 3}`.
2. **Coordinate Bounds:** 100% of bounding box normalized coordinates satisfy `0.0 <= x_center, y_center, width, height <= 1.0`.
3. **Zero Malformed Lines:** No formatting deviations or unparseable tokens detected in the annotation corpus.

---

## 4. Visual Verification & Bounding Box Overlays

Visual inspection was performed by rendering bounding boxes with class color coding directly over road surface photographs:

### Color Palette Coding:
- **D00 (Longitudinal):** Sky Blue (`RGB: 56, 189, 248`)
- **D10 (Transverse):** Teal / Cyan (`RGB: 45, 212, 191`)
- **D20 (Alligator):** Amber / Orange (`RGB: 245, 158, 11`)
- **D40 (Pothole):** Crimson Red (`RGB: 239, 68, 68`)

### Output Artifacts
Verified samples with visual bounding box overlays and metadata banners are stored in:
- [`ml/samples/verified_boxes/`](file:///d:/Projects/CivicSight/ml/samples/verified_boxes/)
  - `verified_D00_sample_*.jpg`
  - `verified_D10_sample_*.jpg`
  - `verified_D20_sample_*.jpg`
  - `verified_D40_sample_*.jpg`

### Repeatable Verification Workflow
To re-run dataset verification and generate fresh visual overlays at any time:
```bash
cd ml
python scripts/verify_dataset_and_visualize.py
```

---

## 5. Model Training Roadmap (Deferred to Week 4)

> [!IMPORTANT]
> **No Model Training in Week 3:** In strict compliance with the Week 3 scope, all dataset preparation, directory structuring, YAML configuration, and bounding box auditing are complete. Full YOLOv8 model fine-tuning will begin in **Week 4** using GPU-accelerated compute (e.g., CUDA / Google Colab / cloud GPU instances).
