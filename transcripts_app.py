from flask import Flask, send_file, render_template_string
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Use absolute path
BASE_DIR = Path(__file__).parent
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

# Create directories
try:
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    print(f"✅ Transcripts directory: {TRANSCRIPTS_DIR.absolute()}")
except Exception as e:
    print(f"❌ Error creating directory: {e}")

# Simple HTML template for single transcript view
SIMPLE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Transcript #{{ channel_name }}</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .header { 
            text-align: center; 
            margin-bottom: 20px; 
            padding-bottom: 15px; 
            border-bottom: 2px solid #eee; 
        }
        .message { 
            margin: 10px 0; 
            padding: 12px; 
            border-left: 4px solid #007bff; 
            background: #f8f9fa; 
            border-radius: 5px; 
        }
        .timestamp { 
            color: #6c757d; 
            font-size: 0.9em; 
            margin-bottom: 3px; 
        }
        .author { 
            font-weight: bold; 
            color: #495057; 
        }
        .content { 
            margin: 5px 0; 
            line-height: 1.4; 
        }
        .attachments { 
            margin-top: 8px; 
        }
        .attachment { 
            display: block; 
            color: #007bff; 
            text-decoration: none; 
            margin: 3px 0; 
            font-size: 0.9em; 
        }
        .attachment:hover { 
            text-decoration: underline; 
        }
        .back-button { 
            display: inline-block; 
            margin: 15px 0; 
            padding: 8px 16px; 
            background: #6c757d; 
            color: white; 
            text-decoration: none; 
            border-radius: 5px; 
            font-size: 0.9em; 
        }
        .back-button:hover { 
            background: #5a6268; 
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Transcript #{{ channel_name }}</h1>
            <p>Generated on {{ generated_time }}</p>
        </div>
        
        <a href="javascript:history.back()" class="back-button">← Go Back</a>
        
        <div class="messages">
            {% for msg in messages %}
            <div class="message">
                <div class="timestamp">{{ msg.timestamp }}</div>
                <div class="author">{{ msg.author }}</div>
                <div class="content">{{ msg.content }}</div>
                {% if msg.attachments %}
                <div class="attachments">
                    {% for att in msg.attachments %}
                    <a href="{{ att.url }}" class="attachment" target="_blank">📎 {{ att.filename }}</a>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <a href="javascript:history.back()" class="back-button">← Go Back</a>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    """Simple homepage redirect or message"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Transcript Viewer</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 40px; 
                background: #f5f5f5; 
                text-align: center; 
            }
            .container { 
                max-width: 600px; 
                margin: 100px auto; 
                background: white; 
                padding: 40px; 
                border-radius: 10px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            }
            h1 { color: #333; }
            p { color: #666; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Transcript Viewer</h1>
            <p>This service displays individual Discord channel transcripts.</p>
            <p>Access specific transcripts via direct URLs provided by the bot.</p>
        </div>
    </body>
    </html>
    """, 200

@app.route('/transcripts/<filename>')
def serve_transcript(filename):
    """Serve a single transcript without any navigation to others"""
    file_path = TRANSCRIPTS_DIR / filename
    
    print(f"📥 Requested: {filename}")
    print(f"🔍 Path: {file_path.absolute()}")
    print(f"✅ Exists: {file_path.exists()}")
    
    if not file_path.exists():
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Transcript Not Found</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 40px; 
                    background: #f5f5f5; 
                    text-align: center; 
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 100px auto; 
                    background: white; 
                    padding: 40px; 
                    border-radius: 10px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
                }}
                h1 {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Transcript Not Found</h1>
                <p>The transcript <strong>{filename}</strong> could not be found.</p>
                <p>It may have been deleted or the URL may be incorrect.</p>
                <p><a href="javascript:history.back()">← Go Back</a></p>
            </div>
        </body>
        </html>
        """, 404
    
    try:
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract channel name from filename
        channel_name = filename.replace('transcript-', '').replace('.html', '')
        channel_name = channel_name.split('-2025')[0]  # Remove timestamp
        
        # Parse the HTML to extract messages for the simple template
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        messages = []
        for message_div in soup.find_all('div', class_='message'):
            timestamp = message_div.find('div', class_='timestamp')
            author = message_div.find('div', class_='author')
            content = message_div.find('div', class_='content')
            attachments = message_div.find('div', class_='attachments')
            
            message_data = {
                'timestamp': timestamp.get_text() if timestamp else '',
                'author': author.get_text() if author else '',
                'content': content.get_text() if content else '',
                'attachments': []
            }
            
            if attachments:
                for attachment in attachments.find_all('a', class_='attachment'):
                    message_data['attachments'].append({
                        'filename': attachment.get_text(),
                        'url': attachment.get('href')
                    })
            
            messages.append(message_data)
        
        # Render using simple template
        return render_template_string(
            SIMPLE_TEMPLATE,
            channel_name=channel_name,
            generated_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            messages=messages
        )
        
    except Exception as e:
        print(f"❌ Error processing transcript: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 40px; 
                    background: #f5f5f5; 
                    text-align: center; 
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 100px auto; 
                    background: white; 
                    padding: 40px; 
                    border-radius: 10px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
                }}
                h1 {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Error Loading Transcript</h1>
                <p>There was an error processing the transcript file.</p>
                <p><a href="javascript:history.back()">← Go Back</a></p>
            </div>
        </body>
        </html>
        """, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting transcript server on port {port}")
    print(f"📁 Transcripts directory: {TRANSCRIPTS_DIR.absolute()}")
    app.run(host='0.0.0.0', port=port, debug=False)
