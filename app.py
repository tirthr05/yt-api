from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os

app = Flask(__name__)
CORS(app, origins="*")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'http_headers': HEADERS,
}


def clean_error(e):
    msg = str(e)
    if 'Sign in' in msg or 'bot' in msg.lower() or 'blocked' in msg.lower():
        return 'YouTube is blocking this request. The server may need cookies configured.'
    if 'unavailable' in msg.lower():
        return 'This video is unavailable or region-restricted.'
    if 'private' in msg.lower():
        return 'This video is private.'
    return msg.split('\n')[0][:200]


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/info', methods=['POST'])
def info():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        with yt_dlp.YoutubeDL(BASE_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
        return jsonify({
            'title': info.get('title', 'Unknown'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', ''),
        })
    except Exception as e:
        return jsonify({'error': clean_error(e)}), 400


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    quality = data.get('quality', '720')
    fmt = data.get('format', 'mp4')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title)s.%(ext)s')

    if fmt == 'mp3':
        ydl_opts = {
            **BASE_OPTS,
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            **BASE_OPTS,
            'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = os.listdir(tmp_dir)
        if not files:
            return jsonify({'error': 'Download failed — no output file produced.'}), 500

        file_path = os.path.join(tmp_dir, files[0])
        mime = 'audio/mpeg' if fmt == 'mp3' else 'video/mp4'
        return send_file(file_path, as_attachment=True, download_name=files[0], mimetype=mime)

    except Exception as e:
        return jsonify({'error': clean_error(e)}), 400


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
