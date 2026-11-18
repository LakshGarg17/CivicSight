# CivicSight ML Subsystem — Computer Vision & Deep Learning Subsystem

This subsystem houses the computer vision and deep learning components for **CivicSight**, focused on detecting and categorizing road surface damages from citizen mobile uploads, dashboard cameras, and municipal drone surveys.

---

## 📊 Dataset: Road Damage Dataset 2022 (RDD2022 Clean Full)

The **RDD2022** dataset is a multi-national benchmark for automated road damage detection, featuring thousands of asphalt road images captured across varied weather conditions, camera angles, and geographical regions (e.g., India, Japan, Czech Republic, China, United States, Norway).

### Reference Configuration: `data_rdd2022_full.yaml`
- **Dataset Partitioning:**
  - **Train:** 37,230 images (cleaned, augmented duplicates removed)
  - **Validation:** 3,286 images
  - **Test:** 3,285 images
- **Note on Absolute Paths:** The training config `ml/data_rdd2022_full.yaml` references the local dataset root `C:/Users/thapa/Downloads/archive (1)/datasets_clean` used during the GPU training run. For local evaluation or retraining on another machine, update the `path:` key to point to your local dataset root, or use the relative `ml/data.yaml` pointing to `../Dataset/RDD_SPLIT`.

---

## 🏷️ Standardized Damage Taxonomy & Severity

CivicSight uses the standardized 4-class RDD2022 pavement damage taxonomy:

| Class ID | Code | Damage Category | Description | Severity Impact | Class Weight |
|:---:|:---|:---|:---|:---:|:---:|
| `0` | **`D00`** | **Longitudinal Crack** | Parallel to roadway travel direction; paving joint or subgrade settlement | Medium | 0.40 |
| `1` | **`D10`** | **Transverse Crack** | Perpendicular to roadway travel direction; thermal shrinkage or joint fatigue | Medium | 0.55 |
| `2` | **`D20`** | **Alligator Crack** | Interconnected fatigue mesh; structural subgrade/base layer failure | High | 0.85 |
| `3` | **`D40`** | **Pothole** | Cavity/depression from moisture penetration & heavy traffic loading; critical hazard | Critical | 1.00 |

---

## 🚀 Production Model Architecture & Weights

- **Model Variant:** YOLOv8s (Small) — 11.2M parameters (vs 3.0M for YOLOv8n)
- **Active Production Weights:** `ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt` (22.5 MB)
- **Model Version Identifier:** `YOLOv8s-clean_rdd2022_yolov8s`
- **Training Hyperparameters:**
  - **Epochs:** 50 epochs (fully converged)
  - **Image Resolution:** 640 × 640 (`imgsz: 640`)
  - **Batch Size:** 16
  - **Optimizer:** AdamW (`lr0: 0.001`, `lrf: 0.01`, cosine decay `cos_lr: true`)
  - **Augmentations:** Mosaic (1.0), Mixup (0.1), Copy-Paste (0.1), HSV-H/S/V scaling, horizontal flip (0.5)
  - **Loss Weights:** Box: 7.5, Class: 0.5, DFL: 1.5

---

## 📈 Performance Summary (Full RDD2022 vs Previous Baselines)

| Metric | Experiment 1 (Week 4 Baseline) | Experiment 2 (Week 5 Optimized) | **Production (YOLOv8s Full RDD2022)** |
|:---|:---:|:---:|:---:|
| **Model** | YOLOv8n (3.0M) | YOLOv8n (3.0M) | **YOLOv8s (11.2M)** |
| **Dataset Size** | 250 train / 60 val | 241 train / 59 val | **37,230 train / 3,286 val / 3,285 test** |
| **Input Resolution** | 640 × 640 | 512 × 512 | **640 × 640** |
| **Epochs** | 2 | 3 | **50** |
| **Mean Precision (P)** | 0.0041 | 0.6541 | **0.5960 (Val) / 0.6081 (Test)** |
| **Mean Recall (R)** | 0.5024 | 0.1254 | **0.5015 (Val) / 0.5097 (Test)** |
| **Overall mAP@0.5** | 0.0335 | 0.1176 | **0.5273 (Val) / 0.5472 (Test)** |
| **Overall mAP@0.5:0.95** | 0.0114 | 0.0530 | **0.2625 (Val) / 0.2708 (Test)** |
| **D00 mAP@0.5** | 0.0002 | 0.0419 | **0.5438 (Val) / 0.5389 (Test)** |
| **D10 mAP@0.5** | 0.0224 | 0.0419 | **0.4977 (Val) / 0.5352 (Test)** |
| **D20 mAP@0.5** | 0.0006 | 0.0001 | **0.6496 (Val) / 0.6459 (Test)** |
| **D40 mAP@0.5** | 0.0222 | 0.1281 | **0.4181 (Val) / 0.4688 (Test)** |

---

## 🔌 Unified Adapter & Integration Interface

The backend connects to the ML subsystem via `ml/inference_adapter.py`:

```python
from ml.inference_adapter import detect_road_damage

# Polymorphic input: image path, PIL Image, OpenCV BGR/RGB array, or preprocessed dict
result = detect_road_damage("path/to/road_photo.jpg", confidence_threshold=0.25)

print(result["model_version"])        # "YOLOv8s-clean_rdd2022_yolov8s"
print(result["num_detections"])       # e.g., 2
print(result["primary_damage_type"])  # "D40"
print(result["primary_priority"])     # "HIGH"
print(result["detections"])           # List of detections with bboxes, confidence, severity
```

### Environment Variable Overrides:
- `MODEL_PATH`: Custom path to model weights (defaults to `ml/runs/detect/clean_rdd2022_yolov8s/weights/best.pt`)
- `DETECTION_CONFIDENCE_THRESHOLD`: Minimum confidence threshold (default: `0.25`)
- `DETECTION_IOU_THRESHOLD`: NMS IoU threshold (default: `0.45`)
- `DETECTION_IMGSZ`: Image inference resolution (default: `640`)

---

## 🛠️ Verification & Testing

To run inference and pipeline verification:

```bash
# 1. Run basic pipeline verification
python ml/scripts/test_inference.py

# 2. Run inference module on held-out test split
python ml/scripts/test_inference_module.py

# 3. Run full pytest suite across backend and ML integration
pytest backend/ -v
```
