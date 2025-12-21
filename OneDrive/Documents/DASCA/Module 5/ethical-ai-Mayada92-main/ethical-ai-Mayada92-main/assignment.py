import numpy as np
import pandas as pd
from aif360.metrics import BinaryLabelDatasetMetric
from aif360.datasets import BinaryLabelDataset

# Import the necessary libraries.
# AIF360 is a library for detecting and mitigating bias in machine learning models.

def create_mock_dataset():
    """
    Creates a mock dataset for testing when the Adult dataset is not available.
    This simulates a dataset with gender bias for educational purposes.
    """
    np.random.seed(42)
    n_samples = 1000
    
    # Create mock data with gender bias
    gender = np.random.choice([0, 1], size=n_samples, p=[0.4, 0.6])  # 40% female, 60% male
    # Simulate bias: males have higher positive outcome rates
    positive_rate_male = 0.7
    positive_rate_female = 0.4
    
    labels = np.zeros(n_samples)
    for i in range(n_samples):
        if gender[i] == 1:  # male
            labels[i] = np.random.choice([0, 1], p=[1-positive_rate_male, positive_rate_male])
        else:  # female
            labels[i] = np.random.choice([0, 1], p=[1-positive_rate_female, positive_rate_female])
    
    # Create features
    features = np.random.randn(n_samples, 5)
    
    # Create feature names
    feature_names = [f'feature_{i}' for i in range(5)]
    
    # Create DataFrame with features, labels, and protected attributes
    df = pd.DataFrame(features, columns=feature_names)
    df['income'] = labels  # Add labels to DataFrame
    df['sex'] = gender     # Add protected attributes to DataFrame
    
    # Create protected attribute names
    protected_attribute_names = ['sex']
    
    dataset = BinaryLabelDataset(
        favorable_label=1,
        unfavorable_label=0,
        df=df,
        label_names=['income'],
        protected_attribute_names=protected_attribute_names,
        privileged_protected_attributes=[[1]],
        unprivileged_protected_attributes=[[0]]
    )
    
    return dataset

def calculate_disparate_impact(dataset, protected_attribute_name):
  """
  Calculates the disparate impact for a given dataset.

  Args:
    dataset: An AIF360 BinaryLabelDataset.
    protected_attribute_name: The name of the protected attribute (e.g., 'sex').

  Returns:
    The disparate impact value.
  """
  # Task 1: Define the privileged and unprivileged groups.
  # Hint: These are lists of dictionaries. For the 'sex' attribute in the Adult dataset,
  # the privileged group (male) is represented as [{protected_attribute_name: 1}] and
  # the unprivileged group (female) as [{protected_attribute_name: 0}].
  privileged_groups = [{protected_attribute_name: 1}]
  unprivileged_groups = [{protected_attribute_name: 0}]
  # Your code here

  # Task 2: Create a BinaryLabelDatasetMetric instance.
  # Hint: Pass the dataset, unprivileged_groups, and privileged_groups to the constructor.
  metric = BinaryLabelDatasetMetric(dataset,
                                    unprivileged_groups=unprivileged_groups,
                                    privileged_groups=privileged_groups)
  # Your code here

  # Task 3: Calculate and return the disparate impact.
  # Hint: Call the disparate_impact() method on the metric object.
  disparate_impact = metric.disparate_impact()
  # Your code here

  return disparate_impact

