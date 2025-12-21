[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=21927912&assignment_repo_type=AssignmentRepo)
# Ethical AI Assignment

## Problem Description

In this assignment, you will use the AIF360 library to detect bias in a dataset. Your task is to complete a Python function that calculates the disparate impact for a given dataset.

## Instructions

1.  Open the `assignment.py` file.
2.  You will find a function definition: `calculate_disparate_impact(dataset, protected_attribute_name)`.
3.  The function takes an AIF360 dataset and the name of a protected attribute as input.
4.  Your task is to:
    *   Define the privileged and unprivileged groups.
    *   Create a BinaryLabelDatasetMetric instance.
    *   Calculate the disparate impact.
    *   Return the disparate impact value.

## Dataset

This assignment uses a mock dataset that simulates gender bias in income prediction:
- 40% of the population is female (unprivileged group)
- 60% of the population is male (privileged group)
- Males have a 70% positive outcome rate
- Females have a 40% positive outcome rate
- This creates a disparate impact of approximately 0.57 (0.4/0.7)

## Hints

*   You can use the `aif360.metrics.BinaryLabelDatasetMetric` class to work with the dataset.
*   For the 'sex' attribute, the privileged group (male) is represented as `[{protected_attribute_name: 1}]`.
*   For the 'sex' attribute, the unprivileged group (female) is represented as `[{protected_attribute_name: 0}]`.
*   Use the `disparate_impact()` method to calculate the metric.

## Running the Assignment

1. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Complete the `calculate_disparate_impact` function in `assignment.py`.

3. Test your solution:
   ```bash
   python test.py
   ```

4. Check the sample solution in `sample_submission.py` if you need help.

## Further Exploration (Optional)

*   AIF360 has many other fairness metrics. Can you calculate the `Equal Opportunity Difference`?
*   Disparate impact is a group fairness metric. What are individual fairness metrics and why are they important?
*   AIF360 also includes algorithms to *mitigate* bias. Look up the `Reweighing` algorithm. How does it work?
*   What does a disparate impact value of 1.0 mean? What about values less than 1.0 or greater than 1.0?