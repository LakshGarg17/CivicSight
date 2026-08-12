# CivicSight: Smart Road Damage Detection and Municipal Repair Management System

CivicSight is a web-based road infrastructure management platform
designed to connect citizen road-damage reporting with municipal
maintenance workflows. It transforms a road-damage complaint into a
traceable maintenance case containing the reported location, damage
assessment, priority, responsible team, repair progress, and final
resolution.

> **Project:** UCS503 Software Engineering\
> **Institution:** Thapar Institute of Engineering and Technology

## Overview

Road damage such as potholes and pavement cracks can cause accidents,
vehicle damage, traffic disruption, and increased maintenance costs.
CivicSight aims to make the reporting and repair process more organized,
transparent, and data-driven.

Instead of treating every pothole report as an isolated complaint,
CivicSight provides an end-to-end workflow:

**Citizen Report → Image & Location → Damage Assessment → Priority
Scoring → Municipal Verification → Assignment → Repair → Verification →
Closure**

## Key Features

### Citizen Reporting

-   Citizen registration and login
-   Upload photographs of road damage
-   Capture location using browser geolocation
-   Select a location manually on a map when GPS is unavailable
-   Generate a unique road-damage report

### Road-Damage Assessment

-   Computer-vision-assisted assessment of road images
-   Initial focus on potholes and pavement cracks
-   Detection confidence recorded with the report
-   Automated results serve as decision-support and can be verified or
    rejected by authorized municipal users

### Priority Management

Reports can receive a priority level based on predefined business rules,
considering factors such as: - Type and severity of damage - Multiple
detected damage types - Confidence of automated assessment - Importance
of the reported location - Previous unresolved reports from the same
location

### Municipal Dashboard

Authorized municipal personnel can: - View submitted reports - View
reports on a map - Filter and review reports - Verify or reject
reports - Mark duplicate reports - Assign reports to maintenance teams -
Track report status

### Repair Tracking

-   Maintenance teams can update repair progress
-   Upload after-repair photographs
-   Maintain assignment and repair history
-   Allow authorized personnel to verify completed repairs
-   Close reports after successful verification

### Analytics

The system is designed to provide visibility into: - Pending repairs -
High-priority locations - Repair progress - Historical road-damage
trends - Report and workflow status

## System Workflow

``` text
Citizen
   |
   v
Submit Road-Damage Report
   |
   +---- Upload Photo
   |
   +---- GPS / Map Location
   |
   v
Validate Submission
   |
   v
Create Unique Report
   |
   v
Central Database
   |
   v
Computer Vision
(Damage Detection)
   |
   v
Priority / Severity Score
   |
   v
Municipal Dashboard
   |
   +---- Reject / Duplicate
   |
   +---- Verify
           |
           v
   Assign Maintenance Team
           |
           v
        Repair
           |
           v
   Upload Repair Evidence
           |
           v
      Verify Repair
           |
           v
       Close Report
```

## Architecture

CivicSight follows a three-tier architecture:

``` text
+------------------------------+
|          Frontend            |
| Citizens | Municipal | Teams |
+--------------+---------------+
               |
               v
+------------------------------+
|           Backend            |
| Authentication               |
| Report Management            |
| Image Analysis Requests      |
| Location Handling            |
| Priority Calculation         |
| Assignment & Status          |
+--------------+---------------+
               |
               v
+------------------------------+
|     Database & Storage       |
| Users | Reports | Locations  |
| Assessments | Repairs        |
| Assignments | Status History |
+------------------------------+

          +----------------+
          | Computer Vision|
          | Damage Model   |
          +----------------+
```

## Technology Direction

The project is designed around open-source and freely available
technologies. The proposed implementation includes:

-   Web application and REST API development
-   Relational database
-   Browser-based geolocation
-   Map visualization
-   Open-source computer-vision libraries and models
-   Local or free storage during development
-   Authentication and role-based access control
-   Automated testing
-   Source control with Git

The specific implementation technologies can be selected according to
project requirements and development constraints.

## Project Scope

### Initial Deliverables

-   Citizen registration and login
-   Road-damage reporting
-   Image upload
-   Location capture
-   Unique report creation
-   Database storage
-   Basic municipal dashboard
-   Report verification and assignment
-   Testing of validation, authorization, report creation, and status
    transitions

### Subsequent Deliverables

-   Fine-tuned road-damage detection model
-   Backend integration of the detection model
-   Automated damage classification
-   Confidence recording
-   Severity and priority scoring
-   Map-based dashboard with filters
-   Maintenance-team assignment
-   Repair tracking
-   Before/after repair evidence
-   Final repair verification
-   Analytics and administrative reports
-   Deployment-ready documentation

## Evaluation

CivicSight will be evaluated using both system-level and computer-vision
metrics.

### Primary Metrics

**Report Processing Success Rate** - Target: at least 95% successful
processing for valid test submissions - Measures successful image
upload, location capture, report creation, and database storage

**Road-Damage Detection Performance** - Precision - Recall - Mean
Average Precision (mAP)

### Secondary Metrics

-   Workflow correctness
-   Priority consistency
-   System response time
-   Report traceability
-   Interface usability
-   Database consistency
-   Role and authorization correctness

## Testing Strategy

Testing will cover individual components as well as complete workflows:

-   Unit testing for validation and priority logic
-   API and integration testing
-   Database consistency testing
-   Role and authorization testing
-   Report lifecycle testing
-   Image-upload validation
-   Location validation
-   Computer-vision performance evaluation

## Scalability and Future Scope

Although CivicSight is designed as a student prototype, its architecture
allows future expansion.

Potential future enhancements include:

-   Additional road-damage categories
-   Dedicated mobile applications
-   Vehicle or dashcam-based reporting
-   Historical road-condition analysis
-   Integration with municipal systems
-   Database indexing and pagination for larger datasets
-   Asynchronous image processing
-   Expanded analytics and reporting

## Privacy and Security

CivicSight is designed to collect only information required for
reporting and workflow management. Role-based access control can be used
to restrict access to sensitive information.

The system also provides alternatives when users do not grant GPS
permission by allowing map-based location selection.

## Risks and Mitigation

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Model accuracy                      Evaluate on held-out data and keep
                                      final decisions with authorized
                                      users

  GPS unavailable                     Provide manual map-based location
                                      selection

  Duplicate reports                   Use location and time information
                                      to identify possible duplicates

  Privacy concerns                    Collect necessary information only
                                      and use role-based access

  Scope expansion                     Prioritize the core
                                      reporting-to-resolution workflow

  Computing limitations               Use transfer learning and
                                      appropriately sized models

  External dependencies               Prefer open-source and local
                                      alternatives
  -----------------------------------------------------------------------

## Project Structure

The exact implementation structure may evolve as development progresses.
A suggested organization is:

``` text
CivicSight/
│
├── frontend/          # Citizen and municipal interfaces
├── backend/           # APIs and business logic
├── model/             # Computer-vision model and inference code
├── database/          # Database schema and related scripts
├── tests/             # Unit, integration, and workflow tests
├── docs/              # Project documentation
├── assets/            # Project images and other resources
└── README.md
```

## Core Objective

The primary objective of CivicSight is not simply to detect potholes. It
is to connect:

**Reporting + Location + Assessment + Prioritization + Assignment +
Repair Tracking + Verification**

into one reliable and traceable workflow.

This makes CivicSight primarily a software engineering system, with
computer vision serving as an intelligent component within the overall
platform.

## Team

-   **Laksh Garg** --- Roll No. 1024030156
-   **Pranay Mittal** --- Roll No. 1024030159
-   **Devansh Thapar** --- Roll No. 1024030154

**Thapar Institute of Engineering and Technology**

## Status

**Project Stage:** Development / Prototype

The system is intended to be developed incrementally, with each
development stage producing a working and testable part of the platform.
