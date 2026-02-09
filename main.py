import os
import requests
from helper import *
from flask import Flask, request, send_file, Response, abort, jsonify

app = Flask(__name__)
spot = SpotMateAPI()

@app.route("/spotify")
def spotify_download():
    url = request.args.get("url")
    if not url:
        abort(400, "No URL")

    before = set(os.listdir(SP_DOWNLOAD_DIR))

    dl_url = spot.process(url)
    if not dl_url:
        abort(500, "Failed")

    r = requests.get(dl_url, stream=True, timeout=30)
    if r.status_code != 200:
        abort(500, "Audio fetch failed")

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
        abort(500, "Output not found")

    return send_file(
        os.path.join(SP_DOWNLOAD_DIR, new_files[0]),
        as_attachment=True
    )


@app.route("/youtube", methods=["POST"])
def youtube_download():
    url = request.form.get("url", "").strip()
    mode = request.form.get("mode")
    quality = request.form.get("quality", "1080")

    if not is_valid_youtube(url):
        abort(400, "Invalid YouTube URL")

    if not os.path.exists(COOKIE_FILE):
        abort(500, "cookies.txt missing")

    before = set(os.listdir(YT_DOWNLOAD_DIR))
    output_template = os.path.join(YT_DOWNLOAD_DIR, "%(title).200s.%(ext)s")

    if mode == "audio":
        cmd = [
            PYTHON, "-m", "yt_dlp",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=android",
            "--cookies", COOKIE_FILE,
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",
            "--no-playlist",
            "-o", output_template,
            url
        ]
    else:
        fmt = f"bv*[height<={quality}]+ba/best"
        cmd = [
            PYTHON, "-m", "yt_dlp",
            "--js-runtimes", "node",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=android",
            "--cookies", COOKIE_FILE,
            "-f", fmt,
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", output_template,
            url
        ]

    run_yt_dlp(cmd)

    after = set(os.listdir(YT_DOWNLOAD_DIR))
    new_files = list(after - before)
    if not new_files:
        abort(500, "Output not found")

    return send_file(
        os.path.join(YT_DOWNLOAD_DIR, new_files[0]),
        as_attachment=True
    )

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


@app.route("/")
def index():
    with open(os.path.join(BASE_DIR, "index.html"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)
