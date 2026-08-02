import os
import re
import sys
import time
import base64
import requests
import subprocess
import cloudscraper
from threading import Lock
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SP_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads/SPOTIFY")
SVN_DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads/SAAVN")

DESKTOP_KEY = b"38346591"
PYTHON = sys.executable

SAAVN_API = "https://jiosavan-api2.vercel.app/api/search/songs"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-G981B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Mobile Safari/537.36"
    ),
    "Referer": "https://www.jiosaavn.com/",
    "Accept": "*/*",
    "Range": "bytes=0-",
}

def safe_name(s):
    return re.sub(r'[\\/:*?"<>|]+', "", s).strip()

# ============================================ #
#                SPOTIFY HELPER                #
# ============================================ #
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

# ============================================== #
#               JIO SAAVN HELPER                 #
# ============================================== #
def extract_song_id(url):
    clean_url = url.split("?", 1)[0].split("#", 1)[0]
    return clean_url.rstrip("/").split("/")[-1]

def decrypt_url(encrypted_url):
    encrypted_url += "=" * (-len(encrypted_url) % 4)
    encrypted_bytes = base64.b64decode(encrypted_url)

    cipher = DES.new(
        DESKTOP_KEY,
        DES.MODE_ECB
    )

    decrypted = unpad(
        cipher.decrypt(encrypted_bytes),
        DES.block_size
    )
    return decrypted.decode("utf-8")

def get_song_data(song_id):
    api = (
        "https://www.jiosaavn.com/api.php"
        f"?__call=webapi.get"
        f"&token={song_id}"
        f"&type=song"
        f"&includeMetaTags=0"
        f"&ctx=web6dot0"
        f"&api_version=4"
        f"&_format=json"
    )

    response = requests.get(api, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()

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

