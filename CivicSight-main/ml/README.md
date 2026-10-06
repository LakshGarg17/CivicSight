# CivicSight ML Subsystem — Computer Vision Foundation

This subsystem houses the computer vision and deep learning components for **CivicSight**, focused on detecting and categorizing road surface damages from mobile camera inputs and municipal drone footage.

---

## 📊 Dataset: Road Damage Dataset 2022 (RDD2022)

The **RDD2022** dataset is a multi-national benchmark for automated road damage detection, featuring thousands of asphalt road images captured across varied weather conditions, camera angles, and geographical regions (e.g., India, Japan, Czech Republic, China, United States, Norway).

### Relevance to CivicSight
Citizen-submitted photos and municipal survey imagery contain diverse noise (shadows, varying lighting, glare, weather). RDD2022 provides real-world ground truth annotations that enable high-precision object detection for automated triage in the CivicSight workflow (`Report → Detect → Prioritize`).

---

## 🏷️ Target Damage Taxonomy

CivicSight focuses on the four primary structural pavement damage classes:

| Class Code | Damage Category | Description | Severity Impact |
|:---|:---|:---|:---|
| **`D00`** | **Longitudinal Cracks** | Cracks running parallel to the direction of vehicle travel. Often caused by paving joint flaws or early subgrade settlement. | Medium |
| **`D10`** | **Transverse Cracks** | Cracks running perpendicular to the roadway centerline. Typically caused by thermal shrinkage or base layer fatigue. | Medium |
| **`D20`** | **Alligator (Fatigue) Cracks**| Series of interconnected cracks resembling crocodile skin. Indicates severe base layer structural failure. | High |
| **`D40`** | **Potholes** | Bowl-shaped pavement depressions caused by moisture penetration and heavy traffic loading. High risk to vehicle safety. | Critical |

---

## 📐 Annotation Format

### 1. YOLO Format (`.txt`)
CivicSight models are trained using standard normalized YOLO bounding box annotations:

```text
<class_id> <x_center> <y_center> <width> <height>
```
- `<class_id>`: Zero-indexed integer (`0`: D00, `1`: D10, `2`: D20, `3`: D40)
- `<x_center>`, `<y_center>`: Center coordinates of the bounding box relative to image dimensions (normalized `0.0 - 1.0`).
- `<width>`, `<height>`: Width and height of the bounding box relative to image dimensions (normalized `0.0 - 1.0`).

### 2. Raw Pascal VOC Format (`.xml`)
Original RDD2022 files provided in VOC XML format are converted to YOLO `.txt` labels during data preprocessing using `<bndbox>` (`xmin`, `ymin`, `xmax`, `ymax`).

---

## 🧪 Pipeline Verification

A test inference script (`scripts/test_inference.py`) is provided to verify that PyTorch, Ultralytics YOLO, and OpenCV are properly configured:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run test inference on sample image
python scripts/test_inference.py
```

Outputs will be saved in `ml/runs/detect/` to confirm end-to-end model execution.
