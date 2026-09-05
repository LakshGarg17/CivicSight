# Week 3 — Authentication, Roles and Dataset Preparation

## Work Done This Week
This week, I worked mainly on the backend authentication system while also continuing the preparation of the road damage dataset.

For the backend, I worked on the registration and login flow and added password hashing so that passwords are not stored directly in the database. Authentication was tested using local API requests to check whether valid and invalid login attempts are handled correctly.

I also worked on the role structure for CivicSight. The initial roles were defined as Citizen, Municipal Officer, Maintenance Staff and Admin. The backend will use these roles to control which operations a particular user is allowed to perform.

On the ML side, I continued organizing the RDD2022 dataset and checked the annotation files against the corresponding images. The dataset was arranged into the required training, validation and testing structure, and the class mapping was checked before moving towards model training.

I also looked at randomly selected annotated images to make sure that the bounding boxes were being interpreted correctly and that the damage classes were mapped as expected.

## What I Learned
I learned more about why passwords should never be stored directly and how authentication and authorization are separate parts of the system.

The dataset work also made it clearer that checking the annotations before training is important. A model can only learn properly if the images, labels and class IDs are organized correctly.

## Challenges
The main backend challenge was making sure that authentication and role checking are handled separately. A user being logged in should not automatically give them access to every operation.

For the dataset, checking a large number of images manually is not practical, so a smaller set of randomly selected samples was used for visual verification.

## Current Status
The initial authentication and role structure is working locally, and the RDD2022 dataset has been organized and checked for the main training workflow.
