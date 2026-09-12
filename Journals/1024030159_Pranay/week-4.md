# Week 4 — Citizen Reporting

## Work Done This Week
This week, I worked on the report creation backend while also contributing to the ML input pipeline and frontend-backend integration.

For the backend, I implemented and tested the basic report creation API. The API accepts the required report information, including the uploaded road image, description and latitude/longitude values. Each submitted report is assigned a unique report ID, while its status and submission timestamp are stored along with the other report information.

I connected the report creation flow with PostgreSQL and tested the database operations to make sure that submitted reports are stored correctly. Required fields are also validated before a report is accepted.

On the ML side, I worked with sample road images and checked how images uploaded through the application can be prepared as input for the YOLO detection component. This helped establish the connection between the report image and the future automated damage detection stage.

I also helped test the frontend reporting form with the backend API. Different cases such as missing information, image submission and location data were checked to make sure that the API responds appropriately.

## What I Learned
I got a better understanding of how file uploads work in an API and how an uploaded image can be associated with a database record without storing the entire image directly inside the database.

I also learned that the ML model needs a consistent image input process so that images received from the application can later be analysed reliably.

## Challenges
Handling image uploads along with normal form data required some additional API testing. Location values also needed validation because incorrect coordinates could result in an inaccurate report location.

Another challenge was keeping the report database structure flexible enough for information that will be added later, such as damage classification, severity and repair status.

## Current Status
The basic report creation API is working with PostgreSQL. Reports can store their image reference, description, coordinates, status, timestamp and unique report ID. The frontend reporting flow has also been tested against the API.
