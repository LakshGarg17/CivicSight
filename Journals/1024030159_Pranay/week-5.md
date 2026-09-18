# Week 5 — Municipal Dashboard and Report Management

## Work Done This Week

This week, I worked on the municipal side of CivicSight and helped connect the dashboard with the existing reporting and ML workflow.

### Frontend
- Built the basic municipal dashboard for viewing submitted citizen reports.
- Added a reports table with report ID, location, status, and priority.
- Created a basic report details view showing the uploaded road image and location.
- Added simple filtering options for reports.

### Backend
- Tested the report listing and report-detail APIs with the dashboard.
- Connected frontend requests with the backend report data.
- Added basic validation for the report information displayed to municipal users.

### ML
- Reviewed the initial YOLO detection results on sample road images.
- Checked whether the detected damage classes and bounding boxes were reasonable.
- Compared a few sample predictions to identify cases where detection could be improved.

## Result
A municipal user can log in and view submitted reports, open their details, and see important information such as the image, location, status, and priority.

