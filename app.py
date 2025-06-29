from flask import Flask, request, jsonify
from flask_cors import CORS # This module is crucial for allowing your frontend (on a different port/origin) to talk to your backend
from bot_logic import ISROBot # Imports your bot's core logic
import logging

# Configure logging for better visibility of what the backend is doing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Enable CORS (Cross-Origin Resource Sharing). This allows your browser-based frontend
# (which might be running on a different port, e.g., file:/// or a simple server on port 8000)
# to make requests to your Flask backend (e.g., on port 5000).
# Without this, browsers would block the requests due to security policies.
CORS(app) 

# Initialize your ISRO bot instance. This sets up the NLU processor and Knowledge Graph manager.
isro_bot = ISROBot()

# Define the API endpoint for your chatbot interactions
# The frontend's JavaScript will send POST requests to 'http://localhost:5000/chat'
@app.route('/chat', methods=['POST'])
def chat():
    # Get the JSON data sent from the frontend. The frontend sends '{ "message": "user's text" }'.
    user_message = request.json.get('message')

    # Basic validation: ensure a message was actually sent
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    logging.info(f"Received message from frontend: {user_message}")

    # Call your bot's core logic to generate a response based on the user's message
    # This is where the NLU, KG query, and response generation happen (as defined in bot_logic.py)
    bot_response = isro_bot.generate_response(user_message)

    logging.info(f"Sending response to frontend: {bot_response}")
    # Return the bot's response as a JSON object to the frontend
    # The frontend JavaScript will then read this 'response' field.
    return jsonify({"response": bot_response})

# This is an optional endpoint to check if your backend is running and connected to Neo4j
@app.route('/status', methods=['GET'])
def status():
    try:
        # Attempt a dummy query to check if the Knowledge Graph connection is active
        test_query = "MATCH (n) RETURN count(n) AS nodeCount"
        count_result = isro_bot.kg_manager._execute_query(test_query)
        kg_status = "Connected" if count_result else "Disconnected/Error"
    except Exception as e:
        kg_status = f"Error: {e}" # Catch any connection errors

    # Return the status of different backend components
    return jsonify({
        "status": "Backend is running!",
        "knowledge_graph_status": kg_status,
        "nlu_processor_status": "Ready" if isro_bot.nlu_processor.nlp else "Not Loaded"
    })

# Main entry point for running the Flask application
if __name__ == '__main__':
    try:
        logging.info("Starting Flask application...")
        # Run the Flask app on all available network interfaces (0.0.0.0) and port 5000.
        # debug=True provides detailed error messages during development.
        # This address (http://0.0.0.0:5000 or http://127.0.0.1:5000) must match the API_URL in index.html.
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        logging.critical(f"Failed to start Flask application: {e}")
    finally:
        # Ensure that the database connection is properly closed when the application shuts down
        logging.info("Shutting down bot resources.")
        isro_bot.close()

