# Week 2 — Database Design and Backend Foundation

## Work Done This Week
This week, I focused on designing the initial database structure for CivicSight and preparing the backend to work with it.

Based on the requirements identified during the previous week, I finalized the initial ER design and identified the main entities required for the first version of the system. The initial database focuses mainly on users and road damage reports.

The report structure includes information such as the reporter, description of the reported damage, location details and the current status of the report. Location-related fields were included because the geographical position of a report will be an important part of CivicSight.

I created the initial database models and set up the database initialization process. Basic CRUD operations were also tested to make sure that reports and user-related records can be created, retrieved, updated and deleted correctly.

At this stage, authentication and advanced role management have not been added yet. These will be handled after the basic database and API structure is stable.

## What I Learned
This week helped me understand how the database design affects the rest of the application. Decisions about entities, relationships and fields need to be made before implementing the complete API because the frontend and backend will both depend on this structure.

I also became more familiar with connecting the backend application to PostgreSQL and working with database models through SQLAlchemy.

## Challenges
One challenge was deciding which information should be stored directly in the report and which information should be separated into its own entity.

Another part that required attention was designing the report status so that it can later support the complete workflow, from a newly submitted report to verification, repair and closure.

## Current Status
The initial database structure is ready and basic CRUD operations have been tested successfully. The backend is now prepared for the next stage of development.
