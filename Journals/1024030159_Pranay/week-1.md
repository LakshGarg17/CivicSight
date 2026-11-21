# Week 1 : Project Setup and Understanding

## Objective

The objective of Week 1 was to understand the road-damage detection requirements of CivicSight, study the selected dataset and prepare the initial machine-learning environment.

## Work Completed

### 1. Understood the Road-Damage Detection Requirement

Studied how computer vision will be used in CivicSight to identify road damage from uploaded photographs.

The initial focus is on identifying common road-damage categories such as:

- Longitudinal cracks
- Transverse cracks
- Alligator cracks
- Potholes

### 2. Studied the RDD2022 Dataset

Studied the Road Damage Dataset 2022 (RDD2022) and its relevance to the CivicSight project.

The dataset provides annotated road images that can be used to develop an object-detection model for road-damage identification.

### 3. Checked Classes and Annotations

Reviewed the available damage classes and annotation structure.

The main classes being considered for CivicSight are:

- D00 — Longitudinal Cracks
- D10 — Transverse Cracks
- D20 — Alligator Cracks
- D40 — Potholes

The annotation format and class structure were studied to understand the preparation required before training.

### 4. Set Up the Python ML Environment

Prepared the initial Python environment required for the machine-learning component.

The environment was configured for working with the selected computer-vision tools and libraries.

### 5. Tested YOLO Locally

Tested YOLO locally using a small sample image to verify that the environment and basic inference workflow are working.

No full-scale model training was performed during this week.

## Challenges / Observations

The main focus was understanding the dataset and model requirements before beginning training.

RDD2022 contains multiple road-damage categories, so the exact dataset preparation and training strategy needs to be finalized before large-scale training begins.

## Learning

This week provided an understanding of how an object-detection model can identify road damage from an image and how annotated datasets are used for training.

I also gained familiarity with the structure of RDD2022 and the initial YOLO inference workflow.

## Week 1 Outcome

The road-damage detection requirements were understood, RDD2022 was studied, the major classes and annotations were reviewed, and the initial ML environment was prepared and tested with YOLO.

Full model training was intentionally not started during Week 1.