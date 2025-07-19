from flask import Flask, render_template
from datetime import datetime
import os

app = Flask(__name__)

# Parse chat export (adapt to your format)
def parse_chat_export():
    messages = []
    with open('data/chat_log.txt', 'r') as f:  # Replace with your file
        for line in f:
            # Customize parsing for your export format!
            if ":" in line:  # Simple TXT format (e.g., "Alice: Hello")
                sender, text = line.split(":", 1)
                messages.append({
                    "sender": sender.strip(),
                    "text": text.strip(),
                    "time": datetime.now().strftime("%H:%M")  # Fake timestamp
                })
    return messages

@app.route("/")
def home():
    messages = parse_chat_export()
    return render_template("index.html", messages=messages)

if __name__ == "__main__":
    app.run(debug=True)
