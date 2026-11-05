# Week 8 — Priority Calculation and Duplicate Detection

## Work Done This Week
This week, I focused on implementing understandable backend rules for report prioritization and identifying potentially related reports.

### Frontend
- Tested priority and severity information on the municipal dashboard.
- Checked the display of priority explanations and repeated-report counts.
- Verified that high-priority filters returned the expected reports.

### Backend
- Implemented a basic rule-based priority calculation using damage severity, repeated reports, persistence, and location risk where data was available.
- Added severity information and repeated-report counts to report records or responses.
- Implemented geographic proximity checks to find nearby reports.
- Added flags for potentially duplicate or related reports.
- Reviewed whether priority history was needed to track changes over time.

### ML
- Tested how detected damage classes and confidence values could contribute to severity assessment.
- Reviewed model outputs for sample road images.
- Helped identify cases where low-confidence detections should be treated cautiously rather than automatically determining priority.

## Result
Reports can receive a rule-based priority assessment, and nearby reports can be flagged for municipal review. The priority calculation remains understandable rather than relying on a complicated or hidden algorithm.

