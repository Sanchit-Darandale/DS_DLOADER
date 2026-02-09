import os
import re
import sys
import time
import requests
import subprocess
import cloudscraper
from threading import Lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

YT_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads/YT")
SP_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads/SPOTIFY")
SVN_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads/SAAVN")

COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")

PYTHON = sys.executable

YOUTUBE_REGEX = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/")

SAAVN_API = "https://jiosavan-api2.vercel.app/api/search/songs"

class SpotMateAPI:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "mobile": True}
        )
        self.base_url = "https://spotmate.online"
        self.lock = Lock()

    def init_session(self):
        r = self.scraper.get(f"{self.base_url}/en1", timeout=30)
        csrf = re.search(r'csrf-token"\s+content="([^"]+)"', r.text)
        return r.cookies.get_dict(), csrf.group(1) if csrf else None

    def process(self, spotify_url):
        cookies, csrf = self.init_session()
        if not csrf:
            return None

        headers = {"x-csrf-token": csrf}

        self.scraper.post(
            f"{self.base_url}/getTrackData",
            json={"spotify_url": spotify_url},
            headers=headers,
            cookies=cookies,
        )

        time.sleep(2)

        r = self.scraper.post(
            f"{self.base_url}/convert",
            json={"urls": spotify_url},
            headers=headers,
            cookies=cookies,
        )

        data = r.json()
        return data.get("download_url") or data.get("url")

def saavn_search(query):
    r = requests.get(
        SAAVN_API,
        params={"query": query, "limit": 10},
        timeout=10
    )
    data = r.json()
    results = []

    for song in data.get("data", {}).get("results", []):
        dls = song.get("downloadUrl", [])
        url = next((d["url"] for d in dls if d.get("quality") == "320kbps"), None)
        if not url:
            continue

        artists = song.get("artists", {}).get("primary", [])
        artist = ", ".join(a["name"] for a in artists) if artists else "Unknown"

        results.append({
            "title": song.get("name"),
            "artist": artist,
            "url": url
        })

    return results

def is_valid_youtube(url: str) -> bool:
    return bool(YOUTUBE_REGEX.match(url))

def run_yt_dlp(cmd):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "", s).strip()

