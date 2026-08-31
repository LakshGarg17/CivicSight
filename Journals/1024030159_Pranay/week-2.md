# Week 2 — RDD2022 Dataset Analysis

## Work Done This Week
This week, I focused on understanding and inspecting the RDD2022 road damage dataset that will be used for the road damage detection component of CivicSight.
I went through the image and annotation structure and checked how the road damage information is represented. The dataset contains images along with corresponding text annotation files, which can be used for object detection training.
The four main damage classes planned for CivicSight were studied:

- D00 — Longitudinal Crack
- D10 — Transverse Crack
- D20 — Alligator Crack
- D40 — Pothole

I also checked the distribution of the different classes to understand whether some types of damage occur much more frequently than others. This is important because an uneven class distribution can affect how well a model learns the different types of damage.
The annotation format was also inspected. The dataset annotations follow the YOLO bounding-box format, where each annotation contains the class ID and normalized bounding-box coordinates. This means that the annotations can be used directly with a YOLO-based object detection workflow with the appropriate class configuration.
A small sample of the dataset was selected for local testing so that the complete dataset does not have to be processed while experimenting with the model setup.

## What I Learned
This week gave me a clearer understanding of how an object detection dataset is structured. I also learned why the image files and their corresponding annotation files have to be matched correctly before training.

I also explored how YOLO uses class IDs and bounding-box coordinates to learn where different types of road damage appear in an image.

## Challenges
The main challenge was understanding the annotation format and making sure that the class IDs were mapped correctly to the intended road damage categories.

Another practical issue was the computational requirement for training an object detection model. Initial local testing showed that CPU-based training on the complete dataset would be considerably slower, so GPU-based training will be considered for the actual training stage.

## Current Status
The RDD2022 dataset structure and annotations have been inspected and verified. The required classes have been identified, and a small local sample is ready for testing.
