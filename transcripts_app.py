from flask import Flask, render_template, send_from_directory, send_file
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Get the absolute path to the transcripts directory
BASE_DIR = Path(__file__).parent
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

@app.route('/')
def index():
    transcripts = []
    
    print(f"Looking for transcripts in: {TRANSCRIPTS_DIR.absolute()}")
    print(f"Directory exists: {TRANSCRIPTS_DIR.exists()}")
    
    if TRANSCRIPTS_DIR.exists() and TRANSCRIPTS_DIR.is_dir():
        files = list(TRANSCRIPTS_DIR.glob('*.html'))
        print(f"Found {len(files)} HTML files")
        
        for file in files:
            if file.is_file():
                stats = file.stat()
                transcripts.append({
                    'filename': file.name,
                    'name': file.stem.replace('transcript-', '').replace('-', ' ').title(),
                    'channel_name': file.stem,
                    'created_date': datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M'),
                    'size': f"{stats.st_size:,}"
                })
    
    transcripts.sort(key=lambda x: x['filename'], reverse=True)
    
    return render_template('index.html', 
                         transcripts=transcripts,
                         current_time=datetime.now().strftime('%Y-%m-%d %H:%M'))

@app.route('/transcripts/<filename>')
def serve_transcript(filename):
    file_path = TRANSCRIPTS_DIR / filename
    
    print(f"Requested file: {filename}")
    print(f"Looking for file at: {file_path.absolute()}")
    print(f"File exists: {file_path.exists()}")
    
    if not file_path.exists():
        # List all available files for debugging
        available_files = [f.name for f in TRANSCRIPTS_DIR.glob('*') if f.is_file()]
        print(f"Available files: {available_files}")
        return f"File {filename} not found. Available files: {', '.join(available_files)}", 404
    
    return send_file(file_path)

# Create directories on startup
@app.before_first_request
def create_directories():
    try:
        TRANSCRIPTS_DIR.mkdir(exist_ok=True)
        print(f"Created/verified transcripts directory: {TRANSCRIPTS_DIR}")
    except Exception as e:
        print(f"Error creating transcripts directory: {e}")
    
    try:
        templates_dir = BASE_DIR / "templates"
        templates_dir.mkdir(exist_ok=True)
        print(f"Created/verified templates directory: {templates_dir}")
    except Exception as e:
        print(f"Error creating templates directory: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

@app.route('/transcripts/<filename>')
def serve_transcript(filename):
    file_path = TRANSCRIPTS_DIR / filename
    
    print(f"Requested file: {filename}")
    print(f"Looking for file at: {file_path.absolute()}")
    print(f"File exists: {file_path.exists()}")
    
    if not file_path.exists():
        available_files = [f.name for f in TRANSCRIPTS_DIR.glob('*') if f.is_file()]
        print(f"Available files: {available_files}")
        return f"File {filename} not found. Available files: {', '.join(available_files)}", 404
    
    # Check if we can read the file
    try:
        with open(file_path, 'r'):
            pass
    except PermissionError:
        print(f"Permission denied for file: {file_path}")
        return "Permission denied", 403
    except Exception as e:
        print(f"Error reading file: {e}")
        return "Server error", 500
    
    return send_file(file_path)
