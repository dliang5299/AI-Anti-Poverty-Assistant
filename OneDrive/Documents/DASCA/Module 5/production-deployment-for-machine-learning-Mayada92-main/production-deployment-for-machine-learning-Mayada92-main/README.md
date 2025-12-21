[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=21927850&assignment_repo_type=AssignmentRepo)
# Production Deployment for Machine Learning Assignment

## Problem Description

In this assignment, you will create a simple Flask API to serve a machine learning model. Your task is to complete a Python function that creates a Flask application with a single endpoint.

## Instructions

1.  Open the `assignment.py` file.
2.  You will find a function definition: `create_flask_app()`.
3.  Your task is to:
    *   Create a Flask application.
    *   Define a route `/predict` that accepts POST requests.
    *   The `/predict` route should return a JSON response with a dummy prediction.

## Hints

*   You can use the `flask` library to create the web application.
*   Use `@app.route('/predict', methods=['POST'])` to define the route.
*   Use `jsonify` to return a JSON response.

## Further Exploration (Optional)

*   How would you load a real, pre-trained machine learning model (e.g., from a `.pkl` file) when the Flask app starts?
*   Modify the `/predict` endpoint to accept JSON data in the request body. You can access this data with `request.get_json()`.
*   How could you use the data from the request to make a prediction with your loaded model?