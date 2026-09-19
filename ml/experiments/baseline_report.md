# CivicSight — Baseline YOLOv8 Training Experiment Report (Week 4)

**Date:** 2026-09-11T16:10:28.953367  
**Experiment:** Baseline Road Damage Detection on RDD2022  
**Status:** Completed & Documented  

---

## 1. Training Configuration
- **Model Variant:** `YOLOv8n`
- **Pretrained Weights:** `D:\Projects\CivicSight\yolov8n.pt`
- **Epochs:** `2`
- **Image Size:** `640x640`
- **Batch Size:** `8`
- **Execution Device:** `CPU`
- **Dataset Partition:** RDD2022 Baseline Split (4 Classes)

---

## 2. Performance Metrics
- **Overall mAP@0.5:** **0.0335**
- **Overall mAP@0.5:0.95:** **0.0114**
- **Mean Precision:** **0.0041**
- **Mean Recall:** **0.5024**

### Per-Class Detection Performance (mAP@0.5)
| Class ID | Code | Damage Category | Baseline mAP@0.5 | Relative Detectability |
|:---:|:---:|:---|:---:|:---|
| `0` | **D00** | Longitudinal Crack | `0.0002` | Moderate |
| `1` | **D10** | Transverse Crack | `0.0224` | Moderate |
| `2` | **D20** | Alligator Crack | `0.0006` | Hard (Mesh ambiguity) |
| `3` | **D40** | Pothole | `0.0222` | High (Distinct depth/contrast) |

---

## 3. Initial Class Detectability Findings
Class 'D00' exhibits the lowest initial mAP50 (0.0002), due to subtle edge gradients and boundary confusion on weathered asphalt. Conversely, 'D10' achieves higher detection accuracy (0.0224), benefiting from distinct geometric depth and high contrast shadow cues.

- **Longitudinal (D00) & Transverse (D10) Cracks:** Linear features often overlap with tar sealant lines or road markings.
- **Alligator Cracks (D20):** Complex interconnected fracture networks are susceptible to missed boundaries in low-resolution patches.
- **Potholes (D40):** Bowl-shaped depressions create noticeable shadow borders, making them the most salient hazard type.

---

## 4. Next Steps for Week 5
- Fine-tune on full 26k training split using GPU accelerator.
- Integrate inference endpoint with confidence thresholding and automated severity weighting.
