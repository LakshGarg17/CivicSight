# Week 7 — ML Results in the CivicSight Dashboard

## Work Done This Week
This week, I worked on displaying the road-damage detection results in the CivicSight interface and helped test the complete ML workflow.

### Frontend
- Added a section on the report page to display detected damage.
- Added damage class and confidence information.
- Displayed the detection image with bounding boxes where available.
- Kept the ML assessment separate from the municipal verification status.

### Backend
- Tested the report flow after the image was processed by the backend.
- Helped verify that detection results received from the ML service were displayed correctly.
- Tested the report page with different detection results and handled cases where no detection was returned.

### ML
- Tested YOLO detections on multiple road-damage images.
- Reviewed bounding boxes and confidence values to identify incorrect detections.
- Helped compare the model output with the original road images.

## Result
CivicSight can now show the computer-vision assessment alongside the citizen report while keeping municipal verification as a separate decision.
