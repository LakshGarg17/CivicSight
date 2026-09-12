# Week 4 — Citizen Reporting

## Work Done This Week
This week, I worked on the citizen reporting workflow and also contributed to the backend and ML parts needed to make the workflow usable from end to end.

On the frontend, I completed the basic citizen reporting page. The page allows a user to select a road image, enter a short description and provide the location of the reported damage. I added browser location permission handling and integrated a Leaflet map so that the user can see and confirm the selected location before submitting the report.

I also worked on the submission flow and connected the reporting form with the backend API. The interface now provides feedback when a report is being submitted and when the submission is successful or fails.

On the backend side, I helped test the report creation API from the frontend and checked that the uploaded image, description and location information were being sent in the expected format.

I also spent some time understanding how the uploaded road image will eventually be passed to the ML model. I tested sample images with the initial YOLO setup to understand the type of output that can be expected from the detection component.

## What I Learned
This week helped me understand how different parts of the application have to work together for a feature to actually be usable. A reporting page by itself is not enough; the frontend, API, database and ML pipeline have to agree on the format of the data.

I also became more familiar with Leaflet and browser-based location permissions.

## Challenges
Getting the location flow right required some testing because users can either allow or deny browser location access. The interface therefore needs to handle both cases without breaking the report submission process.

Another challenge was making sure the frontend sends the image and location data in a format that the backend can process correctly.

## Current Status
The citizen reporting interface is functional at the basic level. Image selection, description entry, location selection and submission feedback have been implemented, and the frontend has been connected to the initial report API.
