import os
import io
import html
import json
import requests
from helper import *
from flask import Flask, request, send_file, Response, abort, jsonify

app = Flask(__name__)
spot = SpotMateAPI()

def spotify_retry_response(error):
    reload_url = request.full_path
    escaped_error = html.escape(str(error))
    escaped_reload_url = html.escape(reload_url, quote=True)
    reload_url_json = json.dumps(reload_url)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Retrying Spotify Download</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <div class="bg-3d" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="container retry-card">
            <h1>API Rotation Failed... Wait</h1>
            <p>Retrying the same request...</p>
            <div class="retry-status">
                <span class="spinner"></span>
                <span>Processing</span>
            </div>
            <p class="retry-error">{escaped_error}</p>
            <a href="{escaped_reload_url}">Retry now</a>
        </div>
        <script>
            const retryKey = "spotifyRetry:" + window.location.href;
            const retryCount = Number(sessionStorage.getItem(retryKey) || "0");

            if (retryCount < 3) {{
                sessionStorage.setItem(retryKey, String(retryCount + 1));
                setTimeout(() => {{
                    window.location.replace({reload_url_json});
                }}, 2500);
            }} else {{
                document.querySelector(".retry-status").textContent =
                    "Stopped after 3 retry attempts. Click Retry now to try again.";
                sessionStorage.removeItem(retryKey);
            }}
        </script>
    </body>
    </html>
    """, 503

@app.route("/spotify")
def spotify_download():
    url = request.args.get("url")
    if not url:
        abort(400, "No URL")

    try:
        before = set(os.listdir(SP_DOWNLOAD_DIR))

        dl_url = spot.process(url)
        if not dl_url:
            raise RuntimeError("Failed")

        r = requests.get(dl_url, stream=True, timeout=30)
        if r.status_code != 200:
            raise RuntimeError("Audio fetch failed")

        name = safe_name(os.path.basename(dl_url.split("?")[0]))
        if not name.endswith(".mp3"):
            name += ".mp3"

        out = os.path.join(SP_DOWNLOAD_DIR, name)

        with open(out, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        after = set(os.listdir(SP_DOWNLOAD_DIR))
        new_files = list(after - before)
        if not new_files:
            raise RuntimeError("Output not found")

        return send_file(
            os.path.join(SP_DOWNLOAD_DIR, new_files[0]),
            as_attachment=True
        )
    except Exception as e:
        return spotify_retry_response(e)

@app.route("/saavn/search")
def saavn_search_api():
    q = request.args.get("q", "").strip()
    if not q:
        abort(400)

    songs = saavn_search(q)
    if not songs:
        return jsonify([])

    return jsonify(songs)

@app.route("/saavn/download")
def saavn_download():
    url = request.args.get("url")
    title = request.args.get("title")
    artist = request.args.get("artist")

    if not url or not title:
        abort(400)

    filename = safe_name(f"{title} - {artist}.mp3")
    path = os.path.join(SVN_DOWNLOAD_DIR, filename)

    r = requests.get(url, stream=True, timeout=30)
    if r.status_code != 200:
        abort(500)

    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    return send_file(path, as_attachment=True)


@app.route("/saavn/url-download", methods=["GET", "POST"])
def saavn_url_download():
    try:
        song_url = request.values.get("url", "").strip()
        if not song_url:
            abort(400, "No Song URL")

        song_id = extract_song_id(song_url)
        data = get_song_data(song_id)
        song = data["songs"][0]

        title = song["title"]
        encrypted_url = song["more_info"]["encrypted_media_url"]
        media_url = decrypt_url(encrypted_url)
        filename = safe_name(title) + ".m4a"

        response = requests.get(
            media_url,
            headers=HEADERS,
            stream=True,
            timeout=30
        )
        response.raise_for_status()

        audio_data = io.BytesIO()
        for chunk in response.iter_content(8192):
            if chunk:
                audio_data.write(chunk)

        audio_data.seek(0)
        return send_file(
            audio_data,
            as_attachment=True,
            download_name=filename,
            mimetype="audio/m4a"
        )
    except Exception as e:
        return f"""
        <h1>Error</h1>
        <pre>{str(e)}</pre>
        """, 500


@app.route("/")
def index():
    with open(os.path.join(BASE_DIR, "index.html"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)
