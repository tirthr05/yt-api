from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os

app = Flask(__name__)
CORS(app)

# Common yt-dlp options to bypass bot detection
COMMON_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    },
    # Uncomment below if you have a cookies.txt file exported from your browser
    # 'cookiefile': 'cookies.txt',
}


@app.route('/info', methods=['POST'])
def info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL required'}), 400

    try:
        opts = {**COMMON_OPTS}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
            })
    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        if 'Sign in' in err or 'bot' in err.lower():
            return jsonify({'error': 'YouTube is blocking this request. Please add a cookies.txt file to your server. See README.'}), 403
        return jsonify({'error': err}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', '1080')
    fmt = data.get('format', 'mp4')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    tmp_dir = tempfile.mkdtemp()
    output_path = os.path.join(tmp_dir, '%(title)s.%(ext)s')

    if fmt == 'mp3':
        ydl_opts = {
            **COMMON_OPTS,
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            **COMMON_OPTS,
            'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # Find the actual output file (extension may differ after merge)
        for f in os.listdir(tmp_dir):
            file_path = os.path.join(tmp_dir, f)
            mime = 'audio/mpeg' if fmt == 'mp3' else 'video/mp4'
            return send_file(file_path, as_attachment=True, download_name=f, mimetype=mime)

        return jsonify({'error': 'File not found after download'}), 500

    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        if 'Sign in' in err or 'bot' in err.lower():
            return jsonify({'error': 'YouTube is blocking this request. Try adding a cookies.txt file to bypass bot detection.'}), 403
        return jsonify({'error': err}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
