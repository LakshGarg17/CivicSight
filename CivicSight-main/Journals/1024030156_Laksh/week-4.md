# Week 4 — Citizen Reporting

## Work Done This Week
This week, I worked mainly on the first YOLO training experiment while also contributing to the citizen reporting interface and testing the backend report workflow.

For the ML component, I ran the first baseline YOLO training experiment using the prepared road-damage dataset. I recorded the basic training configuration and observed the initial results rather than immediately trying to optimize the model.

The first results were checked to see whether the model was producing reasonable detections and whether some damage classes were noticeably harder to detect than others. This gave us an initial reference point for future training experiments.

On the frontend side, I helped improve the citizen reporting page and worked on the submission status section. The user can now get feedback about whether the report is being submitted successfully or whether an error occurred.

I also tested the complete reporting flow from the frontend side and checked whether the submitted information reached the backend correctly. This included checking the image, description and location data.

## What I Learned
The first training experiment gave me a better understanding of the difference between simply running a model and actually evaluating whether its detections are useful.

I also learned more about how an ML component fits into a larger application. The model is only one part of the system and eventually needs to receive images from the backend and return results that can be stored and displayed.

## Challenges
The main challenge with the baseline experiment was the amount of time required for training on the available hardware. Since this was the first experiment, the focus was on getting a working baseline and recording its behaviour rather than trying to achieve the best possible accuracy immediately.

On the application side, testing the complete submission flow required checking both successful and unsuccessful API requests.

## Current Status
The first YOLO baseline experiment has been completed and its initial results have been recorded for comparison with future experiments. The citizen reporting workflow is also functional at the basic level, with image submission, location information and submission status connected to the backend.
