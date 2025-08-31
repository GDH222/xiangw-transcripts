from flask import Flask, render_template, send_from_directory, send_file
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Use absolute path to ensure we're looking in the right place
BASE_DIR = Path(__file__).parent
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"

# Create directories immediately
try:
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    print(f"✅ Transcripts directory: {TRANSCRIPTS_DIR.absolute()}")
except Exception as e:
    print(f"❌ Error creating transcripts directory: {e}")

@app.route('/')
def index():
    transcripts = []
    
    print(f"🔍 Looking in: {TRANSCRIPTS_DIR.absolute()}")
    print(f"📁 Directory exists: {TRANSCRIPTS_DIR.exists()}")
    
    if TRANSCRIPTS_DIR.exists():
        files = list(TRANSCRIPTS_DIR.glob('*.html'))
        print(f"📄 Found {len(files)} HTML files: {[f.name for f in files]}")
        
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
    
    print(f"📥 Requested: {filename}")
    print(f"🔍 Looking at: {file_path.absolute()}")
    print(f"✅ Exists: {file_path.exists()}")
    
    # List all files for debugging
    all_files = [f.name for f in TRANSCRIPTS_DIR.glob('*') if f.is_file()]
    print(f"📋 All files: {all_files}")
    
    if not file_path.exists():
        return f"File {filename} not found. Available files: {', '.join(all_files)}", 404
    
    return send_file(file_path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting server on port {port}")
    print(f"📁 Transcripts directory: {TRANSCRIPTS_DIR.absolute()}")
    app.run(host='0.0.0.0', port=port, debug=False)
