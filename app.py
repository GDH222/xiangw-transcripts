from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

# Load chat data (replace with your parser)
def load_chat_data():
    with open('data/chat_log.json', 'r') as f:  # Replace with your file
        return json.load(f)  # For JSON exports

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/chat")
def get_chat():
    messages = load_chat_data()
    return jsonify(messages)  # Send as JSON

if __name__ == "__main__":
    app.run(debug=True)
