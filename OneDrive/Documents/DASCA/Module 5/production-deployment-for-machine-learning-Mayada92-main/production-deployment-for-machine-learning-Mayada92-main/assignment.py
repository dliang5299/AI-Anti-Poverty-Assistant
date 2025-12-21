from flask import Flask, jsonify, request

# Import the necessary libraries for creating a web application.
# Flask is a lightweight web framework for Python.
# jsonify is a helper function to convert Python dictionaries to JSON responses.
# request is an object that contains the data sent with a request to the server.

def create_flask_app():
  """
  Creates a Flask application with a single endpoint for making predictions.

  Returns:
    A Flask application.
  """
  app = Flask(__name__)

  # Task: Create a route for '/predict' that accepts POST requests.
  # Hint: Use the @app.route() decorator.
  # The function you define for this route should return a JSON response.
  # For this assignment, the JSON can be a simple dummy prediction like {'prediction': 42}.
  # Use the jsonify() function to create the response.

  # Your code here
  @app.route('/predict', methods=['POST'])
  def predict():
    return jsonify({'prediction': 42})

  return app
