# Week 8 — ML Assessment and Priority Testing

## Work Done This Week
This week, I focused on evaluating the YOLO model's outputs and helping connect damage detection with the priority and duplicate-report workflow.

### Frontend
- Tested how damage class, confidence, severity, and priority were displayed on report pages.
- Checked the visibility of priority explanations and related-report indicators.
- Reviewed the dashboard filters for high-priority reports.

### Backend
- Tested the priority calculation with reports containing different damage assessments.
- Checked how nearby reports were identified and flagged as potentially related.
- Helped verify that ML results could be used as inputs to the priority workflow without replacing municipal verification.

### ML
- Tested how different damage classes affected the proposed severity and priority rules.
- Reviewed confidence values and checked sample detections for false positives or missed damage.
- Improved the model only where a clear issue was identified.
- Documented the available model evaluation results and remaining limitations.

## Result
The initial model assessment is better connected to the report-priority workflow. The system can use detection results as decision-support information while leaving final verification to municipal officers.

