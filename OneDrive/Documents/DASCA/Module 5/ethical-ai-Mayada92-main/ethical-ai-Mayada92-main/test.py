import unittest
import numpy as np
from assignment import calculate_disparate_impact, create_mock_dataset

class TestEthicalAI(unittest.TestCase):
    def test_calculate_disparate_impact(self):
        # Use mock dataset instead of AdultDataset to avoid download issues
        dataset = create_mock_dataset()
        disparate_impact = calculate_disparate_impact(dataset, 'sex')
        
        # Test that the result is a float
        self.assertIsInstance(disparate_impact, float)
        
        # Test that disparate impact is between 0 and 1 (or slightly above 1 for slight bias)
        self.assertGreaterEqual(disparate_impact, 0.0)
        self.assertLessEqual(disparate_impact, 2.0)  # Allow for some bias
        
        # Test that we can detect bias in our mock dataset
        # Our mock dataset has bias (males have 70% positive rate, females have 40%)
        # So disparate impact should be around 0.4/0.7 ≈ 0.57
        expected_disparate_impact = 0.4 / 0.7  # approximately 0.57
        self.assertAlmostEqual(disparate_impact, expected_disparate_impact, delta=0.1)

if __name__ == '__main__':
    unittest.main()