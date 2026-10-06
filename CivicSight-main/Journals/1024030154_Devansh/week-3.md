# Week 3 — Authentication and User Roles

## Work Done This Week
This week, I worked on both the frontend authentication screens and part of the backend authentication flow.

On the frontend side, I created the registration and login pages for CivicSight. The registration form collects the basic information required for creating an account, while the login page allows an existing user to access the application. Basic validation was added to make sure that required fields are not left empty and that the entered information follows the expected format.

I also worked on the navigation structure after login. The frontend is being prepared so that different users can eventually see the parts of the application relevant to their role.

Along with the frontend work, I helped with the backend registration flow. I worked on connecting the registration form structure with the backend API and checked how user data will be passed between the frontend and backend.

The authentication-related API requests were also tested locally to make sure that the frontend and backend can communicate correctly.

## What I Learned
This week helped me understand the connection between frontend forms and backend APIs more clearly. Authentication is not just a login page; the frontend needs to send the correct information and the backend has to validate and process it securely.

I also got a better idea of how user roles can affect the navigation and features shown to a user.

## Challenges
One challenge was making sure that the frontend validation and backend validation do not depend on each other. The frontend should provide immediate feedback, but the backend still needs to validate the request independently.

Another issue was keeping the authentication flow flexible enough to support multiple roles later.

## Current Status
The registration and login interfaces are in place, and the frontend structure is prepared for authenticated API requests. Initial backend registration integration has also been tested.
