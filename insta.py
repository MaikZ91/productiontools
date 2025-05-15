#!/usr/bin/env python3
from __future__ import annotations
import requests, json, pytz, io, base64, os, time
from datetime import datetime,timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, base64, json, requests, pytz
from datetime import datetime
from dateutil.parser import parse
from typing import List, Optional
from io import BytesIO
import numpy as np
from pathlib import Path
import moviepy.editor
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip


URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
GITHUB_VIDEO_URL = (
    "https://raw.githubusercontent.com/MaikZ91/productiontools/master/"
    "media/3188890-hd_1920_1080_25fps.mp4"
)
W, PAD = 1080, 50
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
SLIDE_DURATION = 5  # Sekunden pro Overlay
FPS = 24

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
    if path is None:
        path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_%f_events.jpg")
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
    
def build_overlay(events: List[dict], title: str) -> Image.Image:
    """Erzeuge ein transparentes PNG mit Titel und Text der Events."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Titel zeichnen
    ft_title = font(TITLE_FONT_SIZE)
    bbox = draw.textbbox((0, 0), title, font=ft_title)
    w_title = bbox[2] - bbox[0]
    h_title = bbox[3] - bbox[1]
    x_title = (W - w_title) // 2
    draw.text((x_title, PAD), title, font=ft_title, fill=TXT_COL)

    # Events darunter
    y_offset = PAD + h_title + PAD
    ft = font(FONT_SIZE)
    ascent, descent = ft.getmetrics()
    line_h = ascent + descent
    y = y_offset
    for ev in events or [{"event": "Keine Events gefunden"}]:
        text = ev.get("event", "")
        draw.text((PAD, y), text, font=ft, fill=TXT_COL)
        y += line_h + PAD
    return img

def daily_video_save(output_path: Optional[str] = None) -> str:
    """Erzeuge das Video mit Titel und speichere es lokal. Gibt den Pfad zurück."""
    tz = pytz.timezone("Europe/Berlin")
    dm = datetime.now(tz)
    date_label = dm.strftime("%d.%m.%Y")
    title = f"Events heute – {date_label}"

    all_events = json.loads(requests.get(URL, timeout=10).text)
    events = [e for e in all_events if e.get("date", "").endswith(dm.strftime("%d.%m"))]
    chunks = [events[i:i+MAX_PER_SLIDE] for i in range(0, len(events), MAX_PER_SLIDE)] or [[]]

    base_clip = VideoFileClip(GITHUB_VIDEO_URL)
    overlays = []
    start = 0.0
    for chunk in chunks:
        img = build_overlay(chunk, title)
        arr = np.array(img)
        oc = (ImageClip(arr)
              .set_start(start)
              .set_duration(SLIDE_DURATION)
              .set_fps(FPS)
              .set_position("center")
        )
        overlays.append(oc)
        start += SLIDE_DURATION

    final = CompositeVideoClip([base_clip] + overlays)

    if output_path is None:
        output_path = "events_video.mp4"
    final.write_videofile(output_path, codec="libx264", fps=FPS, audio=False, verbose=False, logger=None)

    print(f"✅ Video gespeichert unter: {output_path}")
    return output_path




def main():
    global events
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events=[e for e in json.loads(raw) if e.get("date","?").endswith(dm) and "hochschulsport" not in e.get("event","").lower()]
    #events = [e for e in json.loads(raw) if e.get("date","?").endswith(dm)]

    

    gh_repo=os.getenv("GITHUB_REPOSITORY");gh_tok=os.getenv("GITHUB_TOKEN")
    save_daily_json(events,gh_repo,gh_tok)
    chunks=[events[i:i+MAX_PER_IMG] for i in range(0,len(events),MAX_PER_IMG)]
    image_urls=[]
    for chunk in chunks:
        img=build_image(chunk)
        buf=io.BytesIO();img.save(buf,"JPEG",quality=95)
        url=gh_upload(buf.getvalue(),gh_repo,gh_tok)
        image_urls.append(url)
    base_caption=("Weitere Events und Infos findest du in unserer App (Alle Angaben ohne Gewähr auf Richtigkeit) ➡ Link in Bio 🔗\n\n"+"\n".join(f"• {e.get('event','')}"for e in events))
    ig_tok=os.getenv("IG_ACCESS_TOKEN");ig_uid=os.getenv("IG_USER_ID")
    if len(image_urls)==1:print("🎉 IG-Post ID:",insta_single_post(image_urls[0],base_caption,ig_uid,ig_tok))
    else:print("🎉 IG-Carousel ID:",insta_carousel_post(image_urls,base_caption,ig_uid,ig_tok))
    weekday=datetime.now(tz).weekday()
    #if weekday==3:weekend_post() 
    if weekday==0:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png","TRIBE TUESDAY RUN 💪\nJeden Dienstag, 18 Uhr | Gellershagen Park (am Teich)\nGemeinsam laufen, motivieren & Spaß haben.\nAnmeldung in der WhatsApp Community (-> Wöchentliche Umfrage), Link in der Bio🔗","",ig_tok)
    if weekday==2:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png","Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",ig_uid,ig_tok)
    if weekday==6:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png","Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:",ig_uid,ig_tok)
    day=datetime.now(tz).day
    #if day in (1,15):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Craetive.jpg","TRIBE CREATIVE CIRCLE - Dein Talent, deine Bühne. Jeden letzten Fr im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    if day in (2,16):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Wandern.jpg","TRIBE WANDERSAMSTAG - Immer am letzten Samstag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    if day in (3,17):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Kennenlernen.jpg","TRIBE KENNENLERNABEND - Immer am letzten Sonntag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    daily_video_save()
    print("✅ Bilder hochgeladen:",image_urls)

if __name__=="__main__":main()
