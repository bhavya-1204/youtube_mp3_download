from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os
import glob
import re
import time

app = Flask(__name__)

# In-memory download history (persists during session)
download_history = []

def get_file_size(file_path):
    """Return human-readable file size."""
    try:
        size_bytes = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    except Exception:
        return "Unknown"

def download_youtube_audio(song_name, output_path="."):
    try:
        # Ensure output directory exists
        os.makedirs(output_path, exist_ok=True)

        # Clean up old MP3 files to avoid conflicts
        for old_file in glob.glob(os.path.join(output_path, "*.mp3")):
            os.remove(old_file)

        # Search for the video URL
        search_command = [
            "yt-dlp",
            f"ytsearch1:{song_name}",
            "--get-id",
            "--no-playlist"
        ]

        result = subprocess.run(search_command, capture_output=True, text=True, check=True)
        video_id = result.stdout.strip()

        if not video_id:
            return False, f"No video found for: {song_name}", None

        # Download the audio using the video ID
        download_command = [
          "yt-dlp",
          "--cookies", "cookies.txt",
          "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
          "--js-runtimes", "node",
          "--sleep-interval", "3",
          "--max-sleep-interval", "6",
          "--no-playlist",
          "-f", "bestaudio",
          "--extract-audio",
          "--audio-format", "mp3",
          "-o", os.path.join(output_path, "%(title)s.%(ext)s"),
          f"https://www.youtube.com/watch?v={video_id}"
        ]

        result = subprocess.run(download_command, capture_output=True, text=True, check=True)
        # Find the downloaded file
        mp3_files = glob.glob(os.path.join(output_path, "*.mp3"))
        if mp3_files:
            return True, mp3_files[0], video_id  # Return the first MP3 file found
        return False, "Download completed but no MP3 file found", None

    except subprocess.CalledProcessError as e:
        return False, f"Error downloading {song_name}: {e.stderr}", None
    except Exception as e:
        return False, f"Unexpected error for {song_name}: {str(e)}", None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    song_name = request.form.get('song_name')
    output_directory = "downloads"  # Fixed output directory for simplicity

    if not song_name:
        return jsonify({'success': False, 'message': 'Please enter a song name'})

    success, message, video_id = download_youtube_audio(song_name, output_directory)

    if success:
        file_path = message  # message contains the file path
        file_name = os.path.basename(file_path)
        file_size = get_file_size(file_path)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Save to history
        history_entry = {
            'song_name': song_name,
            'file_name': file_name,
            'file_path': file_path,
            'file_size': file_size,
            'timestamp': timestamp,
            'video_id': video_id
        }
        download_history.insert(0, history_entry)  # Newest first

        return jsonify({
            'success': True,
            'message': f"Successfully downloaded: {song_name}",
            'file_path': file_path,
            'file_name': file_name,
            'file_size': file_size,
            'timestamp': timestamp
        })
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/download_file/<path:file_path>')
def download_file(file_path):
    try:
        return send_file(file_path, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'File not found'})

# ── New Advanced Endpoints ──────────────────────────────────────────────────

@app.route('/history', methods=['GET'])
def get_history():
    """Return the in-session download history."""
    return jsonify({'success': True, 'history': download_history})

@app.route('/history/clear', methods=['POST'])
def clear_history():
    """Clear the in-session download history."""
    download_history.clear()
    return jsonify({'success': True, 'message': 'History cleared'})

@app.route('/queue', methods=['POST'])
def queue_download():
    """Download multiple songs sent as a newline-separated list."""
    raw = request.form.get('songs', '')
    songs = [s.strip() for s in raw.splitlines() if s.strip()]

    if not songs:
        return jsonify({'success': False, 'message': 'No songs provided'})

    output_directory = "downloads"
    results = []

    for song_name in songs:
        success, message, video_id = download_youtube_audio(song_name, output_directory)
        time.sleep(5)
        if success:
            file_path = message
            file_name = os.path.basename(file_path)
            file_size = get_file_size(file_path)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            entry = {
                'song_name': song_name,
                'file_name': file_name,
                'file_path': file_path,
                'file_size': file_size,
                'timestamp': timestamp,
                'video_id': video_id
            }
            download_history.insert(0, entry)
            results.append({'song_name': song_name, 'success': True,
                            'file_name': file_name, 'file_path': file_path,
                            'file_size': file_size})
        else:
            results.append({'song_name': song_name, 'success': False, 'message': message})

    success_count = sum(1 for r in results if r['success'])
    return jsonify({
        'success': True,
        'results': results,
        'summary': f"{success_count}/{len(songs)} songs downloaded successfully"
    })

@app.route('/check_file', methods=['POST'])
def check_file():
    """Check whether a previously downloaded file still exists on disk."""
    file_path = request.form.get('file_path', '')
    exists = os.path.isfile(file_path)
    return jsonify({'success': True, 'exists': exists, 'file_path': file_path})

# ────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True)
