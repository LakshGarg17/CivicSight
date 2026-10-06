"""CivicSight ML Subsystem — Baseline Inference Pipeline Verification (Week 1)

This script loads a pretrained Ultralytics YOLO model and executes inference
on a sample road image to confirm that the PyTorch/YOLO environment is fully functional.
"""

import sys
from pathlib import Path

# Paths definition
SCRIPT_DIR = Path(__file__).resolve().parent
ML_DIR = SCRIPT_DIR.parent
SAMPLE_IMAGE = ML_DIR / "samples" / "sample_road.jpg"


def run_test_inference():
    print("=" * 60)
    print("[INFO] CivicSight ML Subsystem: Baseline Environment Verification")
    print("=" * 60)

    # 1. Verify sample image existence
    if not SAMPLE_IMAGE.exists():
        print(f"[ERROR] Sample image not found at '{SAMPLE_IMAGE}'")
        sys.exit(1)
    print(f"[OK] Found sample road image: {SAMPLE_IMAGE}")

    # 2. Check and import Ultralytics YOLO
    try:
        from ultralytics import YOLO
        import torch
        print(f"[OK] PyTorch {torch.__version__} initialized (CUDA available: {torch.cuda.is_available()})")
    except ImportError as e:
        print(f"[ERROR] Dependency Error: {e}")
        print("[HINT] Please install ML dependencies: pip install -r ml/requirements.txt")
        sys.exit(1)

    # 3. Load YOLO model (yolov8n baseline weights)
    print("\n[INFO] Loading pretrained YOLOv8n model...")
    try:
        model = YOLO("yolov8n.pt")
        print("[OK] YOLOv8n model loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load YOLO model: {e}")
        sys.exit(1)

    # 4. Run inference on sample image
    print(f"\n[INFO] Running inference on sample image: {SAMPLE_IMAGE.name}")
    try:
        results = model.predict(
            source=str(SAMPLE_IMAGE),
            conf=0.25,
            save=True,
            project=str(ML_DIR / "runs" / "detect"),
            name="week1_verification",
            exist_ok=True,
            verbose=False
        )

        print("\n[INFO] Inference Results Summary:")
        for r in results:
            boxes = r.boxes
            print(f"   - Total detected objects: {len(boxes)}")
            for idx, box in enumerate(boxes):
                cls_id = int(box.cls[0].item())
                cls_name = model.names[cls_id]
                conf = float(box.conf[0].item())
                coords = [round(x, 1) for x in box.xyxy[0].tolist()]
                print(f"     [{idx + 1}] Class: {cls_name} (ID: {cls_id}) | Conf: {conf:.2%} | Box: {coords}")

        output_dir = ML_DIR / "runs" / "detect" / "week1_verification"
        print(f"\n[OK] Pipeline verification complete! Annotated image saved to: {output_dir}")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Inference execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_test_inference()
