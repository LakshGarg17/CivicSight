# CivicSight ML Subsystem — Research Notes & Dataset Verification (Week 2)

**Author / Maintainer:** Pranay (ML Lead)  
**Phase:** Week 2 — Dataset Inspection, Annotation Validation & Class-Distribution Analysis  
**Status:** ✅ Dataset Verified & Documented

---

## 1. RDD2022 Dataset Structure Verification

The **RDD2022 (Road Damage Dataset 2022)** split was verified under `Dataset/RDD_SPLIT/` across the `train/`, `val/`, and `test/` partitions.

### Key Verification Findings
- **Image-to-Annotation Pairing:** 100% match. Every image file (`.jpg` / `.png`) corresponds directly to its target YOLO annotation `.txt` file by basename.
- **Annotation Format:** Standard zero-indexed YOLO normalized bounding box format:
  ```text
  <class_id> <x_center> <y_center> <width> <height>
  ```
  - `class_id`: Integer identifier `0` to `3`.
  - `x_center`, `y_center`, `width`, `height`: Float values normalized strictly between `0.0` and `1.0` relative to image dimensions.
- **Malformed Annotations:** 0 errors encountered during sample batch parsing.

---

## 2. Target Class Taxonomy & Distribution Analysis

We sampled and analyzed the dataset using `ml/scripts/analyze_dataset.py` across the 4 core municipal road damage categories:

| Class ID | Code | Damage Category | Sampled Annotations | Distribution (%) | Severity Impact |
|:---:|:---:|:---|:---:|:---:|:---|
| `0` | **`D00`** | **Longitudinal Crack** | 1,433 | **41.0%** | Medium (Water ingress risk) |
| `1` | **`D10`** | **Transverse Crack** | 1,083 | **31.0%** | Medium (Thermal / Joint fatigue) |
| `2` | **`D20`** | **Alligator Crack** | 303 | **8.7%** | High (Base layer failure) |
| `3` | **`D40`** | **Pothole** | 576 | **16.5%** | Critical (Immediate traffic hazard) |
| **Total** | — | — | **3,498** | **100.0%** | — |

### Observations & Data Imbalance
1. **Class Distribution Skew:** Longitudinal (`D00`) and Transverse (`D10`) cracks together constitute **72.0%** of all detected damage instances in the sample.
2. **Underrepresented Classes:** Alligator Cracks (`D20` at 8.7%) and Potholes (`D40` at 16.5%) are less frequent but carry the highest municipal priority and severity risk.
3. **Training Strategy Recommendation (Upcoming):**
   - Utilize class-weighted loss (focal loss / bounding box weighting) during YOLO fine-tuning to prevent the model from under-detecting potholes and alligator cracks.
   - Implement data augmentations (e.g., Mosaic, MixUp, HSV color jitter, random perspective shifts) to bolster pothole generalization under varying lighting conditions.

---

## 3. Compute Benchmarks & Hardware Requirements

### Benchmark Summary
- **CPU Inference Test:** Lightweight inference (`yolov8n.pt` baseline) runs adequately on CPU (~40–90ms per image) for localized development.
- **CPU Training Trial:** Local test epochs on CPU proved prohibitively slow for the complete multi-thousand image RDD2022 corpus (~45+ minutes per epoch on standard multi-core CPU).

### Open Engineering Item / Recommendation (Upcoming Stages)
> [!IMPORTANT]
> **GPU-Accelerated Training Required:** Full model training and hyperparameter sweeps on the RDD2022 dataset must be performed on CUDA-enabled GPU hardware (e.g., NVIDIA T4 / V100 / A100 / RTX 3080+ or Google Colab / cloud GPU instances). Model training and fine-tuning are intentionally deferred to subsequent weeks.

---

## 4. Verification Artifacts

- **Analysis Script:** [`ml/scripts/analyze_dataset.py`](file:///d:/Projects/CivicSight/ml/scripts/analyze_dataset.py)
- **Visual Distribution Chart:** [`ml/runs/dataset_distribution.png`](file:///d:/Projects/CivicSight/ml/runs/dataset_distribution.png)
- **Baseline Inference Script:** [`ml/scripts/test_inference.py`](file:///d:/Projects/CivicSight/ml/scripts/test_inference.py)
