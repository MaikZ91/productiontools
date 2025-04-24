#!/usr/bin/env python3
"""
insta.py  –  Alle heutigen Events auf EINER Slide (1080×1350) posten
--------------------------------------------------------------------
• Schriftgröße adaptiv: bis 120 pt, niemals kleiner als 44 pt
• Kartenhöhe = Schrift × 1.3  (optisch stimmig)
• Nur zwei Secrets nötig: IG_ACCESS_TOKEN, IG_USER_ID
"""

import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────── Konstanten ─────────────
WIDTH, HEIGHT = 1080, 1350          # Portrait-Format
PAD, HBAR     = 40, 160             # Außenabstand, Header-Höhe
FONT_MAX, FONT_MIN = 120, 44
TXT_COL       = (17,17,17)          # fast Schwarz
CARD_BG       = (250,250,250)
GRAD_TOP, GRAD_BOT = (230,30,30), (80,0,0)
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

CAPTION_HEAD = "🔥 Aktuelle Events in Bielefeld"

# ───────────── Helpers ─────────────
def load_font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except: pass
    return ImageFont.load_default()

def gradient(draw,h):
    for y in range(h):
        t=y/(h-1)
        col=tuple(int(GRAD_TOP[i]*(1-t)+GRAD_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(WIDTH,y)],fill=col)

def today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    return [e for e in data if e["date"].endswith(dm)] or [{"event":"Keine Events gefunden"}]

# ───────────── Bild bauen ─────────────
def build_image(events):
    n=len(events)
    # Dynamische Schriftgröße: 60 % des pro Event verfügbaren Vertikalraums
    avail_h = HEIGHT - PAD - HBAR - PAD          # Platz unter dem Header
    per_ev  = avail_h / n
    font_size = int(min(FONT_MAX, max(FONT_MIN, per_ev * 0.6)))
    font_ev   = load_font(font_size)
    card_h    = int(font_size * 1.3)

    img = Image.new("RGB",(WIDTH,HEIGHT))
    d   = ImageDraw.Draw(img)
    gradient(d, HEIGHT)

    # Header
    header = Image.new("RGBA",(WIDTH-2*PAD,HBAR),(255,255,255,40))
    img.paste(header,(PAD,PAD),header)
    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD*1.2,PAD+40),
           f"{CAPTION_HEAD} – {datetime.now(tz).strftime('%d.%m')}",
           font=load_font(88), fill=(255,255,255))

    # Events
    y_start = PAD + HBAR + PAD
    for ev in events:
        # Card-Hintergrund
        card = Image.new("RGBA",(WIDTH-2*PAD,card_h),CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.4))
        ms   = Image.new("L",card.size,0)
        ImageDraw.Draw(ms).rounded_rectangle([0,0,*card.size],25,fill=255)
        img.paste(card,(PAD,y_start),ms)

        text = ev["event"]
        tw   = d.textbbox((0,0),text,font=font_ev)[2]
        d.text((PAD*2, y_start + (card_h - font_size)//2),
               text,font=font_ev, fill=TXT_COL)

        y_start += card_h + PAD
    return img, font_size

# ───────────── Caption ─────────────
def build_caption(events):
    lines=[CAPTION_HEAD,"","Mehr Infos ➡ Link in Bio"]
    for ev in events:
        lines.append(f"• {ev['event']}")
    return "\n".join(lines)

# ───────────── GitHub + Instagram ─────────────
def upload_to_repo(img_bytes,repo,token):
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    data={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    r=requests.put(url,headers=hdr,json=data,timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(raw,caption,uid,token):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":raw,"caption":caption,"access_token":token},timeout=15).json().get("id")
    if not cid: raise RuntimeError("container error")
    pub=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":token},timeout=15).json()
    if "id" not in pub: raise RuntimeError("publish error")
    return pub["id"]

# ───────────── Main ─────────────
def main():
    gh_tok=os.getenv("GITHUB_TOKEN")
    gh_rep=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN")
    ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_rep,ig_tok,ig_uid]):
        raise SystemExit("ENV fehlt!")

    events=today_events()
    img,_=build_image(events)
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=96)

    raw=upload_to_repo(buf.getvalue(),gh_rep,gh_tok)
    post_id=insta_post(raw,build_caption(events),ig_uid,ig_tok)
    print("✅ Bild URL:",raw)
    print("🎉 Insta-Post ID:",post_id)

if __name__=="__main__":
    main()
