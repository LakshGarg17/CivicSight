# Week 7 — FastAPI and YOLO Integration

## Work Done This Week
This week, I focused on connecting the FastAPI backend with the trained YOLO model and storing the resulting detection information.

### Frontend
- Tested the report page with ML-generated damage results.
- Checked that damage class and confidence were displayed correctly.
- Verified that the ML assessment was shown separately from municipal verification.

### Backend
- Connected the FastAPI report-processing flow with the ML inference function.
- Sent uploaded report images to the detector for processing.
- Added storage for detected class, confidence, and detection information.
- Added basic error handling for model and inference failures.
- Tested the complete image-processing API flow.

### ML
- Worked with the finalized YOLO model weights.
- Tested inference on multiple road images.
- Checked the returned classes, confidence values, and bounding-box information.
- Recorded inference time for sample images.

## Result
The core pipeline is now connected:

Image Upload → FastAPI → YOLO → Detection → Database

The stored ML results can be used by the frontend for displaying the road-damage assessment.
