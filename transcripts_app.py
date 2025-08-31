from flask import Flask, render_template, send_from_directory
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    transcripts_dir = Path('transcripts')
    transcripts = []
    
    print(f"Looking for transcripts in: {transcripts_dir.absolute()}")
    print(f"Directory exists: {transcripts_dir.exists()}")
    
    if transcripts_dir.exists() and transcripts_dir.is_dir():
        files = list(transcripts_dir.glob('*.html'))
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
    transcripts_dir = Path('transcripts')
    file_path = transcripts_dir / filename
    
    print(f"Requested file: {filename}")
    print(f"Looking for file at: {file_path.absolute()}")
    print(f"File exists: {file_path.exists()}")
    
    if not file_path.exists():
        return f"File {filename} not found", 404
    
    return send_from_directory('transcripts', filename)

if __name__ == '__main__':
    # Safe directory creation
    try:
        Path('transcripts').mkdir(exist_ok=True)
    except FileExistsError:
        pass
    
    try:
        Path('templates').mkdir(exist_ok=True)
    except FileExistsError:
        pass
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)  # debug=True for better error messages
