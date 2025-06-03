#!/usr/bin/env python3
from __future__ import annotations
import requests, json, pytz, io, base64, os, time, html
from datetime import datetime,timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
import os, base64, json, requests, pytz
from datetime import datetime
from dateutil.parser import parse
from typing import List, Optional, Tuple
from io import BytesIO
import numpy as np
from pathlib import Path
import moviepy.editor
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip, AudioFileClip
from tempfile import NamedTemporaryFile
import re
import urllib.parse 
import random

URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "3188890-hd_1920_1080_25fps.mp4"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "bielefeldbynight.mp4"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "20250520_1822_Vibrant City Billboard_simple_compose_01jvq81fa7eywa1d4r9363dzd0.mp4"
video_name = os.getenv("VIDEO_FILE", "clip1.mp4")      
GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / video_name
TUESDAY_RUN_VIDEO = Path(__file__).resolve().parent / "media" / "TUESDAY_RUN.mp4"
MUSIC_FILE = Path(__file__).resolve().parent / "media" / "INDEPENDENCE. (mp3cut.net).mp3"
#MUSIC_FILE = Path(__file__).resolve().parent / "media" / "ali-safari.mp3"
W, H,  PAD = 1080, 1080, 50
HBAR = 140
CARD_H = 110
RADIUS = 25
RED_TOP, RED_BOT = (200,20,20), (80,0,0)
CARD_BG = (250,250,250)
TXT_COL = (0,0,0)
TITLE_COL = (255,255,255)
MAX_PER_IMG = 6
MIN_H = 1080
FONT_SIZE = 60
TITLE_FONT_SIZE = 80
MAX_PER_SLIDE = 6
SLIDE_DURATION = 7  # Sekunden pro Overlay
PADDING = 50
TXT_COLOR = "white"
FONT_PATHS = ["DejaVuSans-Bold.ttf","DejaVuSans.ttf","arial.ttf"]
FPS = 24
SCROLL_FACTOR = 0.7
HIGHLIGHT_SCALE = 0
repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
IG_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_USER = os.getenv("IG_USER_ID")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
INSTAGRAM_WIDTH = 1080
INSTAGRAM_HEIGHT = 1920
TITLE_TEXT       = "Heute in Bielefeld" 
TITLE_FONT_SIZE  = 100                  
TITLE_DURATION   = 2                    
TITLE_FADE       = 0.5                 


CATEGORY_MAP = {
    "Ausgehen": ["Party","Kneipe","Bar","Ausgehen","Konzert","Festival","forum","nrzp","sams","bunker","movie","platzhirsch","irish_pub", "f2f","stereobielefeld","cafe","cutie","Lokschuppen"],
    "Sport": ["Laufen","Fitness","Sport","Yoga","Workout","arminia"],
    "Kreativität": ["Kurs","Workshop","Lesung","Kreativ","Mal","Musik","Krakeln","alarmtheater"]
}

def font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):  
        try: return ImageFont.truetype(name, pt)
        except OSError: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", pt)
    except OSError: return ImageFont.load_default()

RE_IG = re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?")

HANDLE_CACHE: dict[str, str] = {}          # erspart wiederholte Anfragen
DDG_HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_handle(name: str) -> str | None:
    """
    Liefert den Instagram-Handle (ohne @) oder None.
    Erst DuckDuckGo-HTML, dann Instagram-Autocomplete als Fallback.
    Ergebnis wird gecacht.
    """
    name = name.strip()
    if not name:
        return None
    if name in HANDLE_CACHE:
        return HANDLE_CACHE[name]

    # ------------------------------------------------------------
    # 1) DuckDuckGo – erstes Ergebnis, das nach instagram.com/... aussieht
    # ------------------------------------------------------------
    try:
        q     = f"{name} instagram"
        html0 = requests.get("https://duckduckgo.com/html/",
                             params={"q": q},
                             headers=DDG_HEADERS, timeout=10).text
        html0 = html.unescape(html0)
        m     = RE_IG.search(html0)
        if m:
            HANDLE_CACHE[name] = m.group(1).rstrip("/")
            time.sleep(1)                         # kleines Delay für Rate-Limit
            return HANDLE_CACHE[name]
    except requests.RequestException:
        pass

    # ------------------------------------------------------------
    # 2) Instagram-Autocomplete (KEIN Login nötig, aber Rate-Limit streng)
    #    https://www.instagram.com/web/search/topsearch/?context=user&query=<name>
    # ------------------------------------------------------------
    try:
        q = urllib.parse.quote(name)
        url = f"https://www.instagram.com/web/search/topsearch/?context=user&query={q}&rank_token={random.randint(1,1_000_000)}"
        js = requests.get(url, headers=DDG_HEADERS, timeout=10).json()
        users = js.get("users", [])
        if users:
            HANDLE_CACHE[name] = users[0]["user"]["username"]
            time.sleep(1)
            return HANDLE_CACHE[name]
    except (requests.RequestException, json.JSONDecodeError, KeyError):
        pass

    # ------------------------------------------------------------
    # Nichts gefunden
    # ------------------------------------------------------------
    HANDLE_CACHE[name] = None
    return None


def red_grad(d,h):
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def build_image(events: List[dict], date_label: str | None = None) -> Image.Image:
    from PIL import ImageDraw, Image

    # Höhe fix auf 1080px
    H = MIN_H

    # Platz oberhalb und unterhalb für Header + Padding
    available = H - (PAD + HBAR + PAD + PAD)
    total_gap = (max(len(events),1) - 1) * PAD

    # Karte-Höhe so groß wie möglich, aber min. 40px
    ch = max((available - total_gap) // max(len(events),1), 40)

    # vertikale Zentrierung
    content_h = PAD + HBAR + PAD + len(events)*ch + total_gap + PAD
    y_off = (H - content_h) // 2

    base = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(base)

    # Hintergrund-Gradient
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(RED_TOP[i]*(1-t) + RED_BOT[i]*t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)

    # Datum verwenden, das dir übergeben wurde
    tz=pytz.timezone('Europe/Berlin')
    dm = date_label or datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (W-2*PAD, HBAR), (255,255,255,40))
    base.paste(header, (PAD, PAD+y_off), header)
    draw.text((PAD*1.5, PAD+35+y_off), f"Events in Bielefeld – {dm}", font=font(60), fill=TITLE_COL)

    # Event-Karten zeichnen
    y = PAD + HBAR + PAD + y_off
    for ev in events or [{"event":"Keine Events gefunden"}]:
        card = Image.new("RGBA", (W-2*PAD, ch), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size], RADIUS, fill=255)
        base.paste(card, (PAD, y), mask)

        txt = ev.get("event", "")
        bbox = draw.textbbox((0,0), txt, font=font(34))
        th = bbox[3] - bbox[1]
        draw.text((PAD*2, y + (ch - th)//2), txt, font=font(34), fill=TXT_COL)
        y += ch + PAD

    return base


def gh_upload(content_bytes: bytes, repo: str, token: str, path: str | None = None) -> str:
    tz=pytz.timezone("Europe/Berlin")
    now = datetime.now(tz)
    if path is None:
        # Heuristik: MP4 vs. Bild nach Magic‑Bytes
        if content_bytes.startswith(b"\x00\x00\x00\x18ftyp"):
            path = now.strftime("videos/%Y/%m/%d/%H%M_%S_events.mp4")
        else:
            path = now.strftime("images/%Y/%m/%d/%H%M_%S_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    headers={"Authorization":f"token {token}","Accept":"application/vnd.github+json"}
    body={"message":f"auto-upload {os.path.basename(path)}","content":base64.b64encode(content_bytes).decode()}
    res=requests.put(url,headers=headers,json=body,timeout=15).json()
    if "content" not in res: raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {res}")
    return res["content"]["download_url"]

def save_daily_json(events: list[dict], repo: str, token: str) -> str:
    categorized={cat:[] for cat in CATEGORY_MAP}
    uncategorized=[]
    for ev in events:
        desc=ev.get("event","")
        placed=False
        for cat,keywords in CATEGORY_MAP.items():
            if any(kw.lower() in desc.lower() for kw in keywords):
                categorized[cat].append(ev)
                placed=True
                break
        if not placed: uncategorized.append(ev)
    if uncategorized: categorized["Sonstige"]=uncategorized
    json_bytes=json.dumps(categorized,ensure_ascii=False,indent=2).encode("utf-8")
    tz = pytz.timezone("Europe/Berlin")
    now = datetime.now(tz)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = f"data/{now:%Y/%m/%d}/daily{timestamp}.json"

    return gh_upload(json_bytes,repo,token,path)

def insta_single_post(image_url:str,caption:str,uid:str,token:str)->str|None:
    base=f"https://graph.facebook.com/v21.0/{uid}"
    r1=requests.post(f"{base}/media",data={"image_url":image_url,"caption":caption,"access_token":token},timeout=20)
    j1=r1.json();cid=j1.get("id")
    if not cid:print(f"Error creating media: {j1}");return None
    time.sleep(15)
    r2=requests.post(f"{base}/media_publish",data={"creation_id":cid,"access_token":token},timeout=20)
    return r2.json().get("id")

def insta_carousel_post(image_urls:list[str],caption:str,uid:str,token:str)->str|None:
    base=f"https://graph.facebook.com/v21.0/{uid}"
    children=[]
    for url in image_urls:
        r=requests.post(f"{base}/media",data={"image_url":url,"access_token":token},timeout=20)
        j=r.json();cid=j.get("id");
        if cid:children.append(cid)
    if not children: return None
    r1=requests.post(f"{base}/media",data={"children":",".join(children),"media_type":"CAROUSEL","caption":caption,"access_token":token},timeout=20)
    j1=r1.json();carousel_cid=j1.get("id")
    if not carousel_cid: return None
    time.sleep(15)
    r2=requests.post(f"{base}/media_publish",data={"creation_id":carousel_cid,"access_token":token},timeout=20)
    return r2.json().get("id")


def weekend_post():
    tz = pytz.timezone("Europe/Berlin")
    today = datetime.now(tz)
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    days = [friday + timedelta(days=i) for i in range(3)]

    all_events = json.loads(requests.get(URL, timeout=10).text)

    def events_for(d: datetime):
        k = d.strftime("%d.%m")
        return [e for e in all_events if e.get("date", "").endswith(k)
                and "hochschulsport" not in e.get("event", "").lower()]

    slides = [events_for(d) for d in days]

    if "save_daily_json" in globals():
        save_daily_json(sum(slides, []), os.getenv("GITHUB_REPOSITORY"),
                        os.getenv("GITHUB_TOKEN"))

    repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    urls = []
    for d, ev in zip(days, slides):
        img = build_image(ev, d.strftime("%d.%m"))
        buf = BytesIO(); img.save(buf, "JPEG", quality=95)
        urls.append(gh_upload(buf.getvalue(), repo, token))

    caption = ["Weitere Events und Infos findest du in unserer App ➡ Link in Bio 🔗", ""]
    names = {4: "Fr", 5: "Sa", 6: "So"}
    for d, ev in zip(days, slides):
        caption.append(f"{names[d.weekday()]} {d.strftime('%d.%m')}:")
        caption += [f"• {e.get('event', '')}" for e in ev]
        caption.append("")
    caption = "\n".join(caption)

    uid, tok = os.getenv("IG_USER_ID"), os.getenv("IG_ACCESS_TOKEN")
    pid = (
    insta_single_post(urls[0], caption, uid, tok)
    if len(urls) == 1
    else insta_carousel_post(urls, caption, uid, tok)
    )
    print("🎉 Weekend-Post ID:", pid)
    
def daily_video() -> Tuple[str, Optional[str]]:
    """
    Erstellt ein kontinuierliches Scroll-Video der heutigen Events im Instagram-Format (9:16),
    lädt es ins GitHub-Repo hoch und postet es als Instagram-Reel.
    Liefert (GitHub-URL, Instagram-Reel-ID).
    """
    tz = pytz.timezone("Europe/Berlin")
    today_str = datetime.now(tz).strftime("%d.%m")
    #tomorrow = datetime.now(tz) + timedelta(days=1)
    #today_str = tomorrow.strftime("%d.%m") 

    # Ziel-Auflösung Instagram-Reel
    W, H = 1080, 1920

    # 1) Events abrufen
    try:
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        date_re = re.compile(rf"\b{today_str}\b")
        events   = [e for e in data if date_re.search(e.get("date", ""))]
        #events = [e.get("event", "") for e in data if date_re.search(e.get("date", ""))]
        
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der Events: {e}")
        events = []
    if not events:
        events = ["Keine Events gefunden"]

    parsed_events = []
    for ev in events:
        raw   = ev.get("event", "")
        event_time  = (ev.get("time") or "").strip()          # <-- Uhrzeit holen
        m = re.match(r"^(.*?)\s*\((.*?)\)$", raw)
        if m:
            title, location = m.groups()
        else:
            title, location = raw, ""

        ig_handle  = fetch_handle(title.strip()) or ""
        print(f"✏️  {title}  ->  @{ig_handle or '❌ kein Handle'}")
        parsed_events.append((title.strip(), location.strip(), event_time, ig_handle))


    # 2) Basis-Video laden und so skalieren, dass es vollständig füllt (kein Letterboxing)
    base_clip = VideoFileClip(str(GITHUB_VIDEO_FILE)).without_audio()
    orig_w, orig_h = base_clip.w, base_clip.h
    # Skalierungsfaktor so wählen, dass beide Dimensionen >= Ziel
    scale = max(W / orig_w, H / orig_h)
    base_clip = base_clip.resize(scale)
    # Auf Zielgröße zentriert zuschneiden
    base_clip = base_clip.crop(
        width=W, height=H,
        x_center=base_clip.w / 2,
        y_center=base_clip.h / 2
    )
    duration = base_clip.duration
    scroll_time = duration - TITLE_DURATION 

    for fp in FONT_PATHS:
        try:
            title_font = ImageFont.truetype(fp, TITLE_FONT_SIZE)
            break
        except OSError:
            title_font = ImageFont.load_default()
    
    dummy = Image.new("RGBA", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    bbox  = draw.textbbox((0, 0), TITLE_TEXT, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    title_img = Image.new("RGBA", (tw + 2 * PADDING, th + 2 * PADDING), (0, 0, 0, 0))
    draw      = ImageDraw.Draw(title_img)
    draw.text((PADDING, PADDING), TITLE_TEXT, font=title_font, fill=TXT_COLOR)
    
    title_clip = (ImageClip(np.array(title_img))
                  .set_duration(TITLE_DURATION)
                  .set_position(("center", "center"))
                  .crossfadeout(TITLE_FADE))          # sanft ausblenden


    # 3) Scroll-Overlay-Clips erzeugen
    clips = []
    total = len(parsed_events)
    
    for idx, (title, location, event_time, ig_handle) in enumerate(parsed_events):
        for fp in FONT_PATHS:
            try:
                font = ImageFont.truetype(fp, FONT_SIZE)
                break
            except OSError:
                font = ImageFont.load_default()
        prefix = ""
        if event_time:
                prefix += f"[{event_time}] "
        if ig_handle:
                prefix += f"@{ig_handle} "
        text_block = prefix + title + ("\n" + location if location else "")
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.multiline_textbbox((0, 0), text_block, font=font)
        w_text, h_text = bbox[2] - bbox[0], bbox[3] - bbox[1]
        img = Image.new("RGBA", (w_text + 2 * PADDING, h_text + 2 * PADDING), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.multiline_text((PADDING, PADDING), text_block, font=font, fill=TXT_COLOR)
        arr = np.array(img)
        clip = (ImageClip(arr).set_duration(scroll_time).set_start(TITLE_DURATION))
        line_h = h_text + 2 * PADDING
        distance = H + total * line_h
        speed = distance / scroll_time * SCROLL_FACTOR
        start_y = H + idx * line_h
        def pos_fn(t, sy=start_y, sp=speed):
            return (PADDING, sy - sp * t)
        def scale_fn(t, lh=line_h, sy=start_y, sp=speed):
            y = sy - sp * t
            center = y + h_text / 2 + PADDING
            d = abs(center - H / 2)
            if d <= lh:
                return 1 + HIGHLIGHT_SCALE * (1 - d / lh)
            return 1
        clips.append(clip.set_position(pos_fn).resize(scale_fn))

    # 4) Composite im Instagram-Format
    final = CompositeVideoClip([base_clip, title_clip, *clips], size=(W, H))
    # 5) Hintergrundmusik hinzufügen
    if os.path.isfile(MUSIC_FILE):
        try:
            audio = AudioFileClip(str(MUSIC_FILE)).subclip(0, duration)
            final = final.set_audio(audio)
        except Exception as e:
            print(f"Fehler beim Laden der Musik: {e}")

    # 6) Rendern in temporäre Datei
    with NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        tmp_path = tmp.name
    final.write_videofile(tmp_path, codec='libx264', fps=FPS, audio_codec='aac')
    with open(tmp_path, 'rb') as f:
        video_bytes = f.read()
    os.remove(tmp_path)

    # 7) Upload zu GitHub (mit SHA-Handling für Updates)
    path = datetime.now(tz).strftime("videos/%Y/%m/%d/%H%M_events.mp4")
    url_content = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    sha = None
    try:
        get_resp = requests.get(url_content, headers=headers)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
    except requests.RequestException as e:
        print(f"Fehler beim Prüfen vorhandener Datei: {e}")
    body = {"message": os.path.basename(path), "content": base64.b64encode(video_bytes).decode()}
    if sha:
        body["sha"] = sha
    try:
        put_resp = requests.put(url_content, headers=headers, json=body)
        put_resp.raise_for_status()
        github_url = put_resp.json()["content"]["download_url"]
    except requests.RequestException as e:
        print(f"Fehler beim Hochladen zu GitHub: {e}")
        raise

    # 8) Instagram-Reel posten
    music_credit = "🎵 Music by @ali_safari_erdenbuerger"
    video_credit = "🎥 Video by @ali_safari_erdenbuerger"
    
    # Caption zweizeilig aufbauen
    caption_lines = []
    for title, location, event_time, ig_handle in parsed_events:
        line = "• "
        if event_time:
            line += f"[{event_time}] "
        if ig_handle:
            line += f"@{ig_handle} "
        line += title
        if location:
            line += f"\n{location}"
        caption_lines.append(line)
    
    caption = (
        f"🎬 Events heute – {datetime.now(tz).strftime('%d.%m.%Y')} - Mehr Infos in unserer App\n"
        + "\n".join(caption_lines)
        + f"\n\n{music_credit}\n{video_credit}"
    )

    user_tags = [
    {"username": h, "x": 0.5, "y": 0.15 + i*0.05}
    for i, (_, _, _, h) in enumerate(parsed_events) if h
    ]

    ig_base = f"https://graph.facebook.com/v21.0"
    try:
        create_resp = requests.post(
            f"{ig_base}/{IG_USER}/media",
            data={
                "media_type": "REELS",
                "video_url": github_url,
                "caption": caption,
                "share_to_feed": "true",
                "user_tags": json.dumps(user_tags),
                "access_token": IG_TOKEN,
            }, timeout=60,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")
    except requests.RequestException as e:
        print(f"Fehler beim Erstellen des Reels: {e}")
        return github_url, None
    reel_id: Optional[str] = None
    if creation_id:
        poll_url = f"{ig_base}/{creation_id}"
        for _ in range(40):
            time.sleep(5)
            try:
                status_resp = requests.get(poll_url, params={"fields": "status_code", "access_token": IG_TOKEN})
                status_resp.raise_for_status()
            except requests.RequestException:
                break
            if status_resp.json().get("status_code") == "FINISHED":
                try:
                    publish_resp = requests.post(
                        f"{ig_base}/{IG_USER}/media_publish",
                        data={"creation_id": creation_id, "access_token": IG_TOKEN}, timeout=60
                    )
                    publish_resp.raise_for_status()
                    reel_id = publish_resp.json().get("id")
                except requests.RequestException:
                    pass
                break

    # 9) Instagram-Story posten
    try:
        story_resp = requests.post(
            f"{ig_base}/{IG_USER}/media",
            data={"media_type": "STORIES", "video_url": github_url, "caption": caption, "access_token": IG_TOKEN}, timeout=60
        )
        story_resp.raise_for_status()
        story_id = story_resp.json().get("id")
    except requests.RequestException:
        return github_url, reel_id
    if story_id:
        poll_story = f"{ig_base}/{story_id}"
        for _ in range(60):
            time.sleep(5)
            try:
                status = requests.get(poll_story, params={"fields": "status_code", "access_token": IG_TOKEN})
                status.raise_for_status()
            except requests.RequestException:
                break
            if status.json().get("status_code") == "FINISHED":
                try:
                    publish = requests.post(
                        f"{ig_base}/{IG_USER}/media_publish",
                        data={"creation_id": story_id, "access_token": IG_TOKEN}, timeout=60
                    )
                    publish.raise_for_status()
                except requests.RequestException:
                    pass
                break

    return github_url, reel_id

def post_video(video_path) -> Tuple[str, Optional[str]]:

    github_url = video_path
    ig_base = f"https://graph.facebook.com/v21.0"

    caption = "🏃‍♂️ Tuesday Run – enjoy!"
    reel_id: Optional[str] = None

    # 2) Reel-Container anlegen
    create = requests.post(
        f"{ig_base}/{IG_USER}/media",
        data={
            "media_type": "REELS",
            "video_url": github_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": IG_TOKEN,
        }, timeout=60
    )
    print("create:", create.status_code, create.text)
    if create.status_code != 200:
        return github_url, None

    container_id = create.json().get("id")
    if not container_id:
        return github_url, None

    # 3) Pollen bis Verarbeitung fertig
    poll_url = f"{ig_base}/{container_id}"
    wait = 15
    for _ in range(20):             # max ≈5 min
        time.sleep(wait)
        wait = min(wait * 1.3, 60)  # back-off
        status = requests.get(
            poll_url,
            params={
                "fields": "status_code,video_status",
                "access_token": IG_TOKEN,
            }, timeout=30
        ).json()
        print("poll:", status)

        if status.get("status_code") == "FINISHED":
            pub = requests.post(
                f"{ig_base}/{IG_USER}/media_publish",
                data={"creation_id": container_id, "access_token": IG_TOKEN},
                timeout=60
            )
            print("publish:", pub.status_code, pub.text)
            if pub.status_code == 200:
                reel_id = pub.json().get("id")
            break

        if status.get("status_code") == "ERROR":
            print("❌ Reel-Verarbeitung fehlgeschlagen")
            return github_url, None

    # 4) Story mit demselben Clip posten
    story = requests.post(
        f"{ig_base}/{IG_USER}/media",
        data={
            "media_type": "STORIES",
            "video_url": github_url,
            "caption": caption,
            "access_token": IG_TOKEN,
        }, timeout=60
    )
    print("story:", story.status_code, story.text)
    if story.status_code == 200:
        story_id = story.json().get("id")
        poll_story = f"{ig_base}/{story_id}"
        for _ in range(30):
            time.sleep(10)
            s = requests.get(
                poll_story,
                params={"fields": "status_code", "access_token": IG_TOKEN},
                timeout=30
            ).json()
            print("story poll:", s)
            if s.get("status_code") == "FINISHED":
                requests.post(
                    f"{ig_base}/{IG_USER}/media_publish",
                    data={"creation_id": story_id, "access_token": IG_TOKEN},
                    timeout=60
                )
                break

    return github_url, reel_id
def main():
    global events
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    date_re = re.compile(rf"\b{dm}\b")                       # dm = "27.05"
    #events=[e for e in json.loads(raw)if date_re.search(e.get("date",""))and "hochschulsport" not in e.get("event","").lower()]
    #events=[e for e in json.loads(raw) if e.get("date","?").endswith(dm) and "hochschulsport" not in e.get("event","").lower()]
    #events = [e for e in json.loads(raw) if e.get("date","?").endswith(dm)]

    weekday=datetime.now(tz).weekday()
    #if weekday==3:weekend_post() 
    if weekday==0:post_video(TUESDAY_RUN_VIDEO)
    #"TRIBE TUESDAY RUN 💪\nJeden Dienstag, 18 Uhr | Gellershagen Park (am Teich)\nGemeinsam laufen, motivieren & Spaß haben.\nAnmeldung in der WhatsApp Community (-> Wöchentliche Umfrage), Link in der Bio🔗","",ig_tok)
    #if weekday==2:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png","Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",ig_uid,ig_tok)
    #if weekday==6:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png","Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:",ig_uid,ig_tok)
    day=datetime.now(tz).day
    #if day in (1,15):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Craetive.jpg","TRIBE CREATIVE CIRCLE - Dein Talent, deine Bühne. Jeden letzten Fr im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #if day in (2,16):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Wandern.jpg","TRIBE WANDERSAMSTAG - Immer am letzten Samstag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #if day in (3,17):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Kennenlernen.jpg","TRIBE KENNENLERNABEND - Immer am letzten Sonntag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)

    if os.getenv("PURE_VIDEO") == "1":
        #video_path = Path(__file__).resolve().parent / "media" / os.environ["VIDEO_FILE"]
        #video_path = Path(__file__).resolve().parent / "media" / "clip2.mp4" 
        video_path = (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_REPO}/master/media/YouCut_20250603_194220189.mp4"
        )
        post_video(video_path)
    else:
        daily_video()
        
if __name__=="__main__":main()
