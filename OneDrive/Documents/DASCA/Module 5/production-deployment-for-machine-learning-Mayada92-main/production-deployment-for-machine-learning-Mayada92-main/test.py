import unittest
from assignment import create_flask_app

class TestFlaskApp(unittest.TestCase):
    def setUp(self):
        app = create_flask_app()
        # Check if routes are registered before creating test client
        if not app.url_map.converters:
            app.add_url_rule('/predict', 'predict', lambda: 'dummy', methods=['POST'])
        self.client = app.test_client()

    def test_predict_endpoint(self):
        response = self.client.post('/predict')
        self.assertEqual(response.status_code, 200)
        # The actual response will depend on the student's implementation
        # This just checks if the endpoint exists and returns a successful status.
        self.assertIn(b'prediction', response.data)

if __name__ == '__main__':
    unittest.main()