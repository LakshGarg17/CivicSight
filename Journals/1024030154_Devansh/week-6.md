# Week 6 — Initial Model Finalization and Report Workflow

## Work Done This Week

This week, I focused on finalizing the initial road-damage detection model while also helping test the report lifecycle across the application.

### Frontend
- Tested the new report status display and report history.
- Checked the verify, reject, duplicate, and assignment actions in the municipal dashboard.
- Verified that status changes were reflected correctly in the interface.

### Backend
- Tested the report status-transition workflow through the APIs.
- Checked verification, rejection, duplicate marking, and assignment operations.
- Verified that status history was being maintained for reports.

### ML
- Finalized the initial YOLO model for the current project stage.
- Created an inference function for running the model on an image.
- Tested the model on images that were not used during training.
- Recorded examples of false positives and missed detections to understand current limitations.

## Result
The initial ML model is ready for integration, while the application now supports a basic report lifecycle from submission through verification and assignment.
