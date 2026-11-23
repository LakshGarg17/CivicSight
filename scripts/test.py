import cv2, random
from pathlib import Path
from ultralytics import YOLO

try:
    from ml.inference_adapter import get_model_path
    WEIGHTS = str(get_model_path())
except Exception:
    WEIGHTS = r"ml\runs\detect\clean_rdd2022_yolov8s\weights\best.pt"

DS = Path(r"C:\Users\thapa\Downloads\archive (1)\datasets_clean\valid")
OUT = Path("pothole_check"); OUT.mkdir(exist_ok=True)
NAMES = ["D00", "D10", "D20", "D40"]

if __name__ == "__main__":
    model = YOLO(WEIGHTS)
    files = [f for f in (DS / "labels").glob("*.txt")
             if any(l.split()[0] == "3" for l in f.read_text().splitlines() if l.strip())]
    random.seed(0)
    for f in random.sample(files, min(40, len(files))):
        img_path = next((p for ext in (".jpg", ".jpeg", ".png")
                         if (p := DS / "images" / (f.stem + ext)).exists()), None)
        if img_path is None:
            continue
        img = cv2.imread(str(img_path)); h, w = img.shape[:2]
        for l in f.read_text().splitlines():
            q = l.split()
            if len(q) != 5:
                continue
            c = int(q[0]); x, y, bw, bh = map(float, q[1:])
            p1 = (int((x - bw/2) * w), int((y - bh/2) * h))
            p2 = (int((x + bw/2) * w), int((y + bh/2) * h))
            cv2.rectangle(img, p1, p2, (0, 255, 0), 2)
            cv2.putText(img, "GT " + NAMES[c], (p1[0], max(p1[1] - 6, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        r = model.predict(str(img_path), conf=0.10, imgsz=640, device=0, verbose=False)[0]
        for b in r.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(img, f"{NAMES[int(b.cls)]} {float(b.conf):.2f}", (x1, min(y2 + 18, h - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imwrite(str(OUT / img_path.name), img)
    print("saved to", OUT.resolve())