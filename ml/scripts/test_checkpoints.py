import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ml.src.inference import detect_road_damage

for model_name, path in [
    ('experiment2_week5', Path('ml/runs/detect/experiment2_week5/weights/best.pt')),
    ('baseline_week4', Path('ml/runs/detect/baseline_week4/weights/best.pt')),
]:
    print('==============================')
    print('MODEL:', model_name)
    print('==============================')
    for sample in ['sample_road.jpg', 'sample_crack_d10.jpg', 'sample_pothole_d40.jpg']:
        img_path = Path('ml/samples') / sample
        res = detect_road_damage(img_path, model_path=path, confidence_threshold=0.20)
        print(f'-- {sample} --')
        print(f'num_detections: {res["num_detections"]}, primary: {res["primary_damage_type"]}, priority: {res["primary_priority"]}')
        for d in res['detections']:
            print(f'   {d["class_name"]} ({d["description"]}) conf={d["confidence"]:.3f} bbox={d["bbox"]}')
