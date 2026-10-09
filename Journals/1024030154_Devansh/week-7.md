# Week 7 — YOLO Model Integration and Inference

## Work Done This Week
This week, I focused mainly on integrating the trained YOLO model into the CivicSight workflow while also helping with frontend and backend testing.

### Frontend
- Tested the report page with detection results returned from the backend.
- Checked the display of damage class, confidence, and bounding boxes.
- Verified that the ML assessment remained separate from municipal verification.

### Backend
- Helped test the FastAPI-to-ML inference flow.
- Verified that uploaded report images were passed correctly to the detector.
- Checked that detection results and confidence values were returned in the expected format.
- Tested basic error cases during inference.

### ML
- Integrated the finalized YOLO model weights with the inference function.
- Tested the model on multiple road images.
- Recorded inference times for different samples.
- Reviewed detection outputs and confirmed that the model could return classes, confidence, and bounding-box information.

## Result
The trained YOLO model is now connected to the CivicSight application workflow. Detection results can be generated from uploaded road images and passed to the backend for storage and display.

The model is used as decision support, while the final municipal verification remains a separate step.
