# Week 10 — ML Evaluation and System Integration Testing

## Work Done This Week
This week, I focused on evaluating the road-damage detection model and testing its integration with the CivicSight application.

### Frontend
- Tested the report page with different detection results.
- Checked the display of damage classes, confidence values, and bounding boxes.
- Verified that the interface handled missing detection results without breaking the report workflow.

### Backend
- Tested the connection between FastAPI and the YOLO inference function.
- Checked how inference errors and invalid image inputs were handled.
- Verified that detection results were stored and returned with the correct report.

### ML
- Tested the model on held-out road images not used during training.
- Recorded final available precision, recall, and mAP metrics.
- Reviewed false detections and missed damage.
- Tested inference failures and documented the model's limitations.
- Prepared the ML evaluation results for project documentation.

## Result
The ML component was evaluated on separate images, and its integration with the backend was tested. Known limitations and evaluation results were documented for the final project report.

