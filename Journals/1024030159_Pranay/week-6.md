# Week 6 — Report Status and Workflow APIs

## Work Done This Week

This week, I focused on implementing the backend workflow required to move reports through the CivicSight lifecycle.

### Frontend
- Tested the verification, rejection, duplicate, and assignment actions from the municipal dashboard.
- Updated the interface to show the current report status.
- Tested the report history display after status changes.

### Backend
- Implemented report status transitions for the main workflow.
- Added verification and rejection functionality.
- Implemented duplicate marking and report assignment.
- Added status history storage so previous actions can be tracked.
- Tested the basic flow from submitted report to verification and assignment.

### ML
- Worked with the finalized initial YOLO model and tested its inference output.
- Checked detections on images that were not part of the training samples.
- Recorded examples of false positives and missed detections for future improvement.

## Result
CivicSight now has a basic report lifecycle:

Submitted → Pending Verification → Verified → Assigned → Under Repair

The system can record important actions and status changes for each report.
