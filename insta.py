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
import re


URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "3188890-hd_1920_1080_25fps.mp4"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "bielefeldbynight.mp4"
#GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "20250520_1822_Vibrant City Billboard_simple_compose_01jvq81fa7eywa1d4r9363dzd0.mp4"
GITHUB_VIDEO_FILE = Path(__file__).resolve().parent / "media" / "YouCut_20250522_184722743.mp4"
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
    
def _is_today(date_field: str, tz) -> bool:
    """
    True, wenn date_field auf das heutige Datum fällt.
    Akzeptiert u. a.:
      • 'Sun, 25.05.2025'  / 'So, 25.05.'
      • '25.05'            / '25.05.2025'
      • ISO '2025-05-25'   / '2025-05-25T11:00[:SS][Z]'
    """
    if not date_field:
        return False

    today = datetime.now(tz).date()

    # ISO-8601 direkt probieren
    try:
        return datetime.fromisoformat(date_field.rstrip("Z")).astimezone(tz).date() == today
    except ValueError:
        pass

    # Wochentag-Präfix abschneiden
    cleaned = date_field.split(",", 1)[-1].strip()

    # DD.MM[.YYYY]
    for fmt in ("%d.%m.%Y", "%d.%m"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if fmt == "%d.%m":                        # ohne Jahr → aktuelles anfügen
                dt = dt.replace(year=today.year)
            return dt.date() == today
        except ValueError:
            continue
    return False


def daily_video() -> Tuple[str, Optional[str]]:
    """
    Erstellt ein Scroll-Video der heutigen Events (9:16),
    lädt es ins GitHub-Repo hoch und postet es als Reel + Story.
    Liefert (GitHub-Download-URL, Reel-ID).
    """
    tz = pytz.timezone("Europe/Berlin")
    W, H = 1080, 1920                                  # Reels-Auflösung

    # ─────────────────────────────
    # 1) Events abrufen + filtern
    # ─────────────────────────────
    try:
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()                             # list[dict]
        today_events: List[dict] = [
            e for e in data if _is_today(e.get("date", ""), tz)
        ]
    except requests.RequestException as e:
        print("Fehler beim Abrufen der Events:", e)
        today_events = []

    if not today_events:
        today_events = [{"event": "Keine Events gefunden", "time": "", "location": ""}]

    # ─────────────────────────────
    # 2) Strings parsen → (title, location, time)
    # ─────────────────────────────
    parsed_events: List[Tuple[str, str, str]] = []
    for ev in today_events:
        raw = ev.get("event", "")
        m = re.match(r"^(.*?)\s*\((.*?)\)$", raw)      # „Titel (Ort)”
        if m:
            title, loc_in_brackets = m.groups()
            location = loc_in_brackets or ev.get("location", "")
        else:
            title, location = raw, ev.get("location", "")
        time_str = (ev.get("time") or "").strip()
        parsed_events.append((title.strip(), location.strip(), time_str))

    # ─────────────────────────────
    # 3) Basis-Video laden & beschneiden
    # ─────────────────────────────
    base_clip = VideoFileClip(str(GITHUB_VIDEO_FILE)).without_audio()
    scale = max(W / base_clip.w, H / base_clip.h)
    base_clip = base_clip.resize(scale).crop(
        width=W, height=H, x_center=base_clip.w / 2, y_center=base_clip.h / 2
    )

    duration    = base_clip.duration
    scroll_time = duration - TITLE_DURATION

    # ─────────────────────────────
    # 4) Titel-Overlay
    # ─────────────────────────────
    for fp in FONT_PATHS:
        try:
            t_font = ImageFont.truetype(fp, TITLE_FONT_SIZE); break
        except OSError: t_font = ImageFont.load_default()

    dummy = Image.new("RGBA", (1, 1))
    tw, th = ImageDraw.Draw(dummy).textbbox((0, 0), TITLE_TEXT, font=t_font)[2:]
    title_img = Image.new("RGBA", (tw + 2*PADDING, th + 2*PADDING), (0, 0, 0, 0))
    ImageDraw.Draw(title_img).text((PADDING, PADDING), TITLE_TEXT, font=t_font, fill=TXT_COLOR)
    title_clip = ImageClip(np.array(title_img)).set_duration(TITLE_DURATION)\
                 .set_position(("center", "center")).crossfadeout(TITLE_FADE)

    # ─────────────────────────────
    # 5) Scroll-Overlays
    # ─────────────────────────────
    clips = []
    total = len(parsed_events)

    for idx, (title, location, time_str) in enumerate(parsed_events):
        for fp in FONT_PATHS:
            try:
                font = ImageFont.truetype(fp, FONT_SIZE); break
            except OSError: font = ImageFont.load_default()

        first_line = title + (f" – {time_str}" if time_str else "")
        text_block = "\n".join(filter(None, [first_line, location]))

        bbox = ImageDraw.Draw(dummy).multiline_textbbox((0, 0), text_block, font=font)
        w_txt, h_txt = bbox[2]-bbox[0], bbox[3]-bbox[1]

        img = Image.new("RGBA", (w_txt + 2*PADDING, h_txt + 2*PADDING), (0, 0, 0, 0))
        ImageDraw.Draw(img).multiline_text((PADDING, PADDING), text_block, font=font, fill=TXT_COLOR)

        clip = ImageClip(np.array(img)).set_duration(scroll_time).set_start(TITLE_DURATION)

        line_h   = h_txt + 2*PADDING
        distance = H + total * line_h
        speed    = distance / scroll_time * SCROLL_FACTOR
        start_y  = H + idx * line_h

        pos_fn   = lambda t,sy=start_y,sp=speed:(PADDING, sy - sp*t)
        def scale_fn(t,lh=line_h,sy=start_y,sp=speed):
            y = sy - sp*t
            center = y + h_txt/2 + PADDING
            d = abs(center - H/2)
            return 1 + HIGHLIGHT_SCALE*(1 - d/lh) if d <= lh else 1

        clips.append(clip.set_position(pos_fn).resize(scale_fn))

    final = CompositeVideoClip([base_clip, title_clip, *clips], size=(W, H))

    # ─────────────────────────────
    # 6) Musik
    # ─────────────────────────────
    if os.path.isfile(MUSIC_FILE):
        try:
            final = final.set_audio(AudioFileClip(str(MUSIC_FILE)).subclip(0, duration))
        except Exception as e:
            print("Fehler beim Laden der Musik:", e)

    # ─────────────────────────────
    # 7) Rendern in tmp-Datei
    # ─────────────────────────────
    with NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    final.write_videofile(tmp_path, codec="libx264", fps=FPS, audio_codec="aac")
    with open(tmp_path, "rb") as f: video_bytes = f.read()
    os.remove(tmp_path)

    # ─────────────────────────────
    # 8) GitHub-Upload (SHA-Handling)
    # ─────────────────────────────
    path = datetime.now(tz).strftime("videos/%Y/%m/%d/%H%M_events.mp4")
    api  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    sha = None
    try:
        ex = requests.get(api, headers=headers)
        if ex.status_code == 200:
            sha = ex.json().get("sha")
    except requests.RequestException:
        pass

    body = {"message": os.path.basename(path),
            "content": base64.b64encode(video_bytes).decode()}
    if sha: body["sha"] = sha

    github_url = requests.put(api, headers=headers, json=body)\
                         .json()["content"]["download_url"]

    # ─────────────────────────────
    # 9) Caption bauen
    # ─────────────────────────────
    music_credit = "🎵 Music by @mz.9_nyc"
    video_credit = "🎥 Video by @sora.ai_"

    caption_lines = []
    for title, location, time_str in parsed_events:
        line = f"• {title}"
        if time_str: line += f" – {time_str}"
        if location: line += f"\n{location}"
        caption_lines.append(line)

    caption = (
        f"🎬 Events heute – {datetime.now(tz).strftime('%d.%m.%Y')}\n"
        + "\n".join(caption_lines)
        + f"\n\n{music_credit}\n{video_credit}"
    )

    # ─────────────────────────────
    # 10) Reel & Story posten (unverändert)
    # ─────────────────────────────
    ig_base = "https://graph.facebook.com/v21.0"

    def _post(kind: str, extra: dict) -> Optional[str]:
        create = requests.post(
            f"{ig_base}/{IG_USER}/media",
            data={**extra, "access_token": IG_TOKEN, "video_url": github_url},
            timeout=60,
        )
        if create.status_code != 200:
            print("Create-Fehler:", create.text)
            return None
        creation_id = create.json().get("id")
        poll = f"{ig_base}/{creation_id}"
        for _ in range(60):
            time.sleep(5)
            status = requests.get(poll, params={"fields": "status_code", "access_token": IG_TOKEN})
            if status.json().get("status_code") == "FINISHED":
                pub = requests.post(
                    f"{ig_base}/{IG_USER}/media_publish",
                    data={"creation_id": creation_id, "access_token": IG_TOKEN},
                    timeout=60,
                )
                return pub.json().get("id") if pub.status_code == 200 else None
        return None

    reel_id = _post("REELS", {"media_type": "REELS", "caption": caption, "share_to_feed": "true"})
    _       = _post("STORIES", {"media_type": "STORIES", "caption": caption})

    return github_url, reel_id

def main():
    global events
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events=[e for e in json.loads(raw) if e.get("date","?").endswith(dm) and "hochschulsport" not in e.get("event","").lower()]
    #events = [e for e in json.loads(raw) if e.get("date","?").endswith(dm)]

    weekday=datetime.now(tz).weekday()
    #if weekday==3:weekend_post() 
    #if weekday==0:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png","TRIBE TUESDAY RUN 💪\nJeden Dienstag, 18 Uhr | Gellershagen Park (am Teich)\nGemeinsam laufen, motivieren & Spaß haben.\nAnmeldung in der WhatsApp Community (-> Wöchentliche Umfrage), Link in der Bio🔗","",ig_tok)
    #if weekday==2:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png","Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",ig_uid,ig_tok)
    #if weekday==6:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png","Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:",ig_uid,ig_tok)
    day=datetime.now(tz).day
    #if day in (1,15):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Craetive.jpg","TRIBE CREATIVE CIRCLE - Dein Talent, deine Bühne. Jeden letzten Fr im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #if day in (2,16):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Wandern.jpg","TRIBE WANDERSAMSTAG - Immer am letzten Samstag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #if day in (3,17):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Kennenlernen.jpg","TRIBE KENNENLERNABEND - Immer am letzten Sonntag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    #daily_video_save()
    daily_video()
    
    #print("✅ Bilder hochgeladen:",image_urls)

if __name__=="__main__":main()
