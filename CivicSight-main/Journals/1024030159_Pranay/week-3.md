# Week 3 — Dataset Preparation and Authentication Interface

## Work Done This Week
This week, I worked on the RDD2022 dataset preparation along with some frontend work related to the new authentication flow.
For the ML component, I completed the main organization of the dataset into training, validation and testing directories. I checked the annotation files and verified the mapping between the class IDs and the road damage categories being used in CivicSight.

Some random annotated images were also visualized to confirm that the bounding boxes were appearing in the correct locations. This helped verify that the annotation format was suitable for the YOLO-based detection approach.

I also documented the main steps involved in preparing the dataset so that the same process can be repeated later if the dataset needs to be changed or extended.

Along with the ML work, I helped with the frontend authentication screens. I worked on the basic layout and navigation behaviour for registration and login, keeping the design consistent with the existing CivicSight interface.

The frontend was kept ready for connecting with the authentication APIs developed on the backend.

## What I Learned
This week gave me more practical experience with object-detection datasets and the importance of visually checking annotations instead of relying only on the text files.

On the frontend side, I understood how authentication affects the navigation of an application and why the interface needs to be prepared for different types of users.

## Challenges
One challenge during dataset preparation was making sure that the class IDs remained consistent across the annotation files and the YOLO configuration.

On the frontend side, the main challenge was keeping the authentication screens simple while leaving enough flexibility for role-based navigation later.

## Current Status
The RDD2022 dataset is organized and the annotations have been checked using sample images. The registration and login interface is also in place and ready for backend integration.
