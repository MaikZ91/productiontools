#!/usr/bin/env python3
from __future__ import annotations
import requests, json, pytz, io, base64, os, time
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


URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "3188890-hd_1920_1080_25fps.mp4"
MUSIC_FILE = Path(__file__).resolve().parent / "media" / "creative-technology-showreel-241274.mp3" 
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
    Erstellt ein kontinuierliches Scroll-Video der heutigen Events,
    lädt es ins GitHub-Repo hoch und postet es als Instagram-Reel.
    Liefert (GitHub-URL, Instagram-Reel-ID).
    """
    # Zeitzone und Datum
    tz = pytz.timezone("Europe/Berlin")
    today_str = datetime.now(tz).strftime("%d.%m")

    # 1) Events abrufen
    try:
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        events = [e.get("event", "") for e in data if e.get("date", "").endswith(today_str)]
    except requests.RequestException as e:
        print(f"Fehler beim Abrufen der Events: {e}")
        events = []

    if not events:
        events = ["Keine Events gefunden"]

    # 2) Basis-Video laden
    base_clip = VideoFileClip(str(GITHUB_VIDEO_FILE)).without_audio()
    duration = base_clip.duration

    # 3) Scroll-Overlay-Clips erzeugen
    clips = []
    total = len(events)
    for idx, text in enumerate(events):
        # Font laden (Fallback auf Default)
        for fp in FONT_PATHS:
            try:
                font = ImageFont.truetype(fp, FONT_SIZE)
                break
            except OSError:
                font = ImageFont.load_default()

        # Text rendern
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        img = Image.new("RGBA", (w + 2 * PADDING, h + 2 * PADDING), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((PADDING, PADDING), text, font=font, fill=TXT_COLOR)
        arr = np.array(img)
        clip = ImageClip(arr).set_duration(duration)

        # Position und Zoom animieren
        line_h = h + 2 * PADDING
        distance = H + total * line_h
        speed = distance / duration * SCROLL_FACTOR
        start_y = H + idx * line_h

        def pos_fn(t, sy=start_y, sp=speed):
            return (PADDING, sy - sp * t)

        def scale_fn(t, lh=line_h, sy=start_y, sp=speed):
            y = sy - sp * t
            center = y + h / 2 + PADDING
            d = abs(center - H / 2)
            if d <= lh:
                return 1 + HIGHLIGHT_SCALE * (1 - d / lh)
            return 1

        clips.append(clip.set_position(pos_fn).resize(scale_fn))

    # 4) Composite
    final = CompositeVideoClip([base_clip, *clips])

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
    caption = (
        f"🎬 Events heute – {datetime.now(tz).strftime('%d.%m.%Y')}\n"
        + "\n".join(f"• {e}" for e in events)
    )
    ig_base = f"https://graph.facebook.com/v21.0"

    # Reel erzeugen
    try:
        create_resp = requests.post(
            f"{ig_base}/{IG_USER}/media",
            data={
                "media_type": "REELS",
                "video_url": github_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": IG_TOKEN,
            },
            timeout=60,
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
                status_resp = requests.get(
                    poll_url,
                    params={"fields": "status_code", "access_token": IG_TOKEN},
                )
                status_resp.raise_for_status()
            except requests.RequestException as e:
                print(f"Fehler beim Polling des Reel-Status: {e}")
                break

            if status_resp.json().get("status_code") == "FINISHED":
                try:
                    publish_resp = requests.post(
                        f"{ig_base}/{IG_USER}/media_publish",
                        data={"creation_id": creation_id, "access_token": IG_TOKEN},
                        timeout=60,
                    )
                    publish_resp.raise_for_status()
                    reel_id = publish_resp.json().get("id")
                except requests.RequestException as e:
                    print(f"Fehler beim Veröffentlichen des Reels: {e}")
                break

    return github_url, reel_id 



def main():
    global events
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events=[e for e in json.loads(raw) if e.get("date","?").endswith(dm) and "hochschulsport" not in e.get("event","").lower()]
    #events = [e for e in json.loads(raw) if e.get("date","?").endswith(dm)]

    weekday=datetime.now(tz).weekday()
    if weekday==3:weekend_post() 
    if weekday==0:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png","TRIBE TUESDAY RUN 💪\nJeden Dienstag, 18 Uhr | Gellershagen Park (am Teich)\nGemeinsam laufen, motivieren & Spaß haben.\nAnmeldung in der WhatsApp Community (-> Wöchentliche Umfrage), Link in der Bio🔗","",ig_tok)
    if weekday==2:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png","Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",ig_uid,ig_tok)
    if weekday==6:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png","Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:",ig_uid,ig_tok)
    day=datetime.now(tz).day
    if day in (1,15):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Craetive.jpg","TRIBE CREATIVE CIRCLE - Dein Talent, deine Bühne. Jeden letzten Fr im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    if day in (2,16):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Wandern.jpg","TRIBE WANDERSAMSTAG - Immer am letzten Samstag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #if day in (3,17):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Kennenlernen.jpg","TRIBE KENNENLERNABEND - Immer am letzten Sonntag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #daily_video_save()
    daily_video()
    
    #print("✅ Bilder hochgeladen:",image_urls)

if __name__=="__main__":main()
