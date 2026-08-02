import os
import re
import time
import json
import yt_dlp
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
cache = {}
COUNT_FILE = "count.txt"

def get_search_count():
    if not os.path.exists(COUNT_FILE):
        with open(COUNT_FILE, "w") as f:
            f.write("0")
    with open(COUNT_FILE, "r") as f:
        count = int(f.read())
    count += 1
    with open(COUNT_FILE, "w") as f:
        f.write(str(count))
    return count

def fast_spotify_scrape(url):
    if url in cache:
        return cache[url]
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = soup.find("meta", property="og:title")
        title = title_tag["content"] if title_tag else None
        artist_tag = soup.find("meta", property="og:description")
        artist = "Unknown"
        if artist_tag:
            desc = artist_tag["content"]
            parts = desc.split("·")
            if len(parts) >= 2:
                artist = parts[1].strip()
        image_tag = soup.find("meta", property="og:image")
        cover = image_tag["content"] if image_tag else None
        if title:
            title = re.sub(r"\s*\([^)]*\)", "", title).strip()
        result = {"title": title, "artist": artist, "cover": cover}
        cache[url] = result
        return result
    except:
        return {"title": None, "artist": None, "cover": None}

def get_all_formats(query):
    ydl_opts = {
        "format": "all",
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info.get("entries"):
                return None
            video_info = info["entries"][0]
            
            all_formats = []
            audio_formats = []
            best_audio = None
            
            for fmt in video_info.get("formats", []):
                if not fmt.get("url"): continue
                format_data = {"url": fmt.get("url"), "ext": fmt.get("ext"), "abr": fmt.get("abr"), "format_id": fmt.get("format_id")}
                all_formats.append(format_data)
                if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                    audio_formats.append(format_data)
                    if not best_audio or (fmt.get("abr", 0) or 0) > (best_audio.get("abr", 0) or 0):
                        best_audio = format_data
            
            return {
                "youtube_title": video_info.get("title"),
                "direct_audio_url": best_audio["url"] if best_audio else None,
                "total_formats": len(all_formats)
            }
    except:
        return None

@app.route("/download", methods=["GET"])
def download_super():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    current_count = get_search_count()
    overall_start = time.time()
    
    spotify = fast_spotify_scrape(url)
    if not spotify["title"]:
        return jsonify({"error": "Track not found"}), 404

    youtube_result = get_all_formats(f"{spotify['title']} {spotify['artist']}")
    
    response = {
        "success": True,
        "developer": "Sanchit",
        "channel": "https://t.me/THE_DS_OFFICIAL",
        "search_count": current_count,
        "spotify": spotify,
        "youtube": youtube_result,
        "time": f"{time.time() - overall_start:.2f}s"
    }
    
    return Response(json.dumps(response, indent=2), mimetype="application/json")

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "Active",
        "developer": "Sanchir",
        "endpoint": "/download?url=<spotify_url>"
    })

if __name__ == "__main__":
    app.run(debug=True)