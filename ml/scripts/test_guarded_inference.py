import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from app.services.ml_service import run_ml_inference_guarded, process_report_image_ml

sample_img = Path("ml/samples/sample_pothole_d40.jpg")
print("Testing run_ml_inference_guarded on", sample_img)
try:
    res = run_ml_inference_guarded(sample_img)
    print("Success! Result:")
    print("num_detections:", res.get("num_detections"))
    print("detections:", res.get("detections"))
except Exception as e:
    import traceback
    print("Error:", e)
    traceback.print_exc()
