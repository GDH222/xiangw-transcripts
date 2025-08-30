from flask import Flask, render_template, send_from_directory
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    transcripts_dir = Path('transcripts')
    transcripts = []
    
    # Check if directory exists and has files
    if transcripts_dir.exists() and transcripts_dir.is_dir():
        for file in transcripts_dir.glob('*.html'):
            if file.is_file():  # Make sure it's a file, not a directory
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
    return send_from_directory('transcripts', filename)

if __name__ == '__main__':
    # Create directories only if they don't exist (safe method)
    try:
        Path('transcripts').mkdir(exist_ok=True)
    except FileExistsError:
        pass  # Directory already exists, which is fine
    
    try:
        Path('templates').mkdir(exist_ok=True)
    except FileExistsError:
        pass
    
    try:
        Path('static').mkdir(exist_ok=True)
    except FileExistsError:
        pass
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
