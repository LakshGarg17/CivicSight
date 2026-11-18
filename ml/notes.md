# CivicSight ML Subsystem — Technical Notes & Full RDD2022 Integration (Week 8+)

**Phase:** Week 8+ Full Dataset Training & Architecture Upgrade  
**Status:** ✅ 50-Epoch YOLOv8s Model Trained, Evaluated & Integrated via Adapter  

---

## 1. Evolution of Dataset & Modeling Strategy

CivicSight began with a 250-image balanced baseline subset for pipeline feasibility testing in Weeks 3–5. In Week 8+, the complete, multi-national **RDD2022 Clean Dataset** was integrated:

- **Total Clean Partitioned Corpus:** 43,801 images
  - **Train Split:** 37,230 images (~85%)
  - **Validation Split:** 3,286 images (~7.5%)
  - **Holdout Test Split:** 3,285 images (~7.5%)
- **Data Configuration:** `ml/data_rdd2022_full.yaml`
- **Class Label Distribution:**
  - `0`: `D00` — Longitudinal Cracks (Medium Severity)
  - `1`: `D10` — Transverse Cracks (Medium Severity)
  - `2`: `D20` — Alligator (Fatigue) Cracks (High Severity)
  - `3`: `D40` — Potholes / Cavities (Critical Severity)

---

## 2. Model Architecture Upgrade: YOLOv8n → YOLOv8s

To handle real-world diversity across 6 international geographies, the detector was upgraded from YOLOv8n (nano, 3.0M parameters) to **YOLOv8s (small, 11.2M parameters)**:

- **Capacity Increase:** 3.7× parameter increase enables capturing multi-scale crack textures, subtle pavement depressions, and low-contrast surface cavities.
- **Resolution:** Upgraded to standard **640 × 640** input resolution (`imgsz: 640`), preserving fine-grained fracture details.
- **Augmentation Pipeline:**
  - Mosaic augmentation (1.0) with copy-paste (0.1) and mixup (0.1)
  - Random perspective, translation, and scale jitter
  - HSV color jitter for robust handling of sunlight glare, shade, and wet asphalt
- **Convergence:** Trained for 50 full epochs on NVIDIA GeForce RTX 4060 Laptop GPU with AdamW and cosine learning rate decay (`cos_lr=True`).

---

## 3. Evaluation Findings & Metrics

### Key Metric Milestones:
- **Validation mAP@0.5:** `0.5273` (52.73% vs 11.76% in Exp 2 — **+348% relative gain**)
- **Validation mAP@0.5:0.95:** `0.2625` (26.25% vs 5.30% in Exp 2 — **+395% relative gain**)
- **Test Set mAP@0.5:** `0.5472`
- **Test Set mAP@0.5:0.95:** `0.2708`
- **Mean Precision:** `0.5960` (Val) / `0.6081` (Test)
- **Mean Recall:** `0.5015` (Val) / `0.5097` (Test)

### Per-Class Detection Breakdown (mAP@0.5):
- `D20` (Alligator Crack): **0.6496 (Val) / 0.6459 (Test)** — Highest detectability due to distinct interconnected polygonal network textures.
- `D00` (Longitudinal Crack): **0.5438 (Val) / 0.5389 (Test)** — Robust localization along travel trajectory.
- `D10` (Transverse Crack): **0.4977 (Val) / 0.5352 (Test)** — Reliable detection across lateral road sections.
- `D40` (Pothole): **0.4181 (Val) / 0.4688 (Test)** — Consistent detection on ground-level vehicle/phone camera inputs.

---

## 4. Edge Cases, Failure Patterns & Domain Limitations

Evaluations across representative held-out test splits revealed distinct failure patterns:

1. **High-Altitude Aerial / Drone Imagery vs Ground Photography:**
   - In drone-captured survey footage (e.g., `China_Drone_000099.jpg`), shallow potholes lack visible depth shadows and are often classified as linear or alligator surface cracks (`D00`/`D20`).
   - Ground-level mobile phone photos (typical citizen submissions) provide strong oblique shadows that assist pothole cavity discrimination.
2. **Wet Pavement & Rain Puddles:**
   - Standing water reflections can mimic dark pothole cavities or obscure fine transverse crack lines.
3. **Pavement Sealing & Fresh Asphalt Patches:**
   - Dark, tarred crack-seal strips sometimes trigger low-confidence `D00` (longitudinal crack) false positives.
   - Guarded by the priority engine's `PRIORITY_MIN_CONFIDENCE=0.25` threshold.
4. **Severe Tree Canopy Shadows:**
   - Strong alternating shadow lines on sunny days can introduce edge artifacts resembling longitudinal fractures.
