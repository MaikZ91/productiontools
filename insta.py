#!/usr/bin/env python3
"""
insta.py  –  Events-Bild erzeugen, im Repo ablegen und auf Instagram posten
---------------------------------------------------------------------------
• Bild → images/YYYY/MM/dd/HHmm_events.jpg
• Schriftgröße der Events dynamisch, max. 50 pt
• Nur zwei Secrets nötig: IG_ACCESS_TOKEN, IG_USER_ID
"""
import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────────────── Konstanten ─────────────────────
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")
CAPTION = ("🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 "
           "Kostenlos & offen für alle. #tribe #bielefeld #workout")

WIDTH, PAD, HBAR = 1080, 50, 140
CARD_H, RADIUS   = 110, 25
MAX_FONT, MIN_FONT = 50, 22          # Schrift-Größenbereich
RED_TOP, RED_BOT = (200,20,20), (80,0,0)
CARD_BG, TXT_COL = (250,250,250), (0,0,0)
TITLECOL         = (255,255,255)

# ───────────── Hilfsfunktionen ─────────────
def font(sz: int):
    try: return ImageFont.truetype("arial.ttf", sz)
    except: return ImageFont.load_default()

def gradient(draw, h):
    for y in range(h):
        t = y/(h-1)
        col = tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(WIDTH,y)], fill=col)

def fetch_events():
    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    events = requests.get(EVENTS_URL, timeout=10).json()
    return [e for e in events if e["date"].endswith(dm)] or [{"event":"Keine Events gefunden"}]

def best_font_size(draw, text, max_w):
    size = MAX_FONT
    while size >= MIN_FONT:
        if draw.textbbox((0,0), text, font(font(size)))[2] <= max_w:
            return font(size)
        size -= 2
    return font(MIN_FONT)

def build_image(events):
    n   = len(events)
    H   = PAD + HBAR + PAD + n*CARD_H + max(n-1,0)*PAD + PAD
    img = Image.new("RGB", (WIDTH, H))
    d   = ImageDraw.Draw(img)
    gradient(d, H)

    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (WIDTH-2*PAD, HBAR), (255,255,255,40))
    img.paste(header, (PAD,PAD), header)
    d.text((PAD*1.5, PAD+35),
           f"🔥  Events in Bielefeld – {dm}",
           font=font(60), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events:
        card = Image.new("RGBA", (WIDTH-2*PAD, CARD_H), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size], RADIUS, fill=255)
        img.paste(card, (PAD,y), mask)

        txt  = ev["event"]
        fnt  = best_font_size(d, txt, WIDTH-4*PAD)
        th   = d.textbbox((0,0), txt, font=fnt)[3]
        d.text((PAD*2, y+(CARD_H-th)//2), txt, font=fnt, fill=TXT_COL)
        y   += CARD_H + PAD
    return img

# ───────────── GitHub-Upload ─────────────
def upload(img_bytes, repo, token, branch=None):
    tz  = pytz.timezone("Europe/Berlin")
    path= datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    body = {
        "message":"auto-upload events image",
        "content": base64.b64encode(img_bytes).decode()
    }
    if branch: body["branch"]=branch
    hdr = {"Authorization":f"token {token}",
           "Accept":"application/vnd.github+json"}
    res = requests.put(url, headers=hdr, json=body, timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {res}")
    return res["content"]["download_url"]

# ───────────── Instagram-Publish ─────────────
def insta_post(url, caption, uid, token, ver="v21.0"):
    base=f"https://graph.facebook.com/{ver}/{uid}"
    media=requests.post(f"{base}/media",data={
        "image_url":url,"caption":caption,"access_token":token
    },timeout=15).json()
    cid=media.get("id")
    if not cid: raise RuntimeError(f"Container-Fehler: {media}")
    pub=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":token
    },timeout=15).json()
    if "id" not in pub: raise RuntimeError(f"Publish-Fehler: {pub}")
    return pub["id"]

# ───────────── Main ─────────────
def main():
    gh_token=os.getenv("GITHUB_TOKEN")
    gh_repo =os.getenv("GITHUB_REPOSITORY")
    ig_tok  =os.getenv("IG_ACCESS_TOKEN")
    ig_uid  =os.getenv("IG_USER_ID")
    if not all([gh_token,gh_repo,ig_tok,ig_uid]):
        raise SystemExit("ENV-Variablen fehlen")

    img=build_image(fetch_events())
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=95)
    raw=upload(buf.getvalue(), gh_repo, gh_token)
    print("✅ Bild gespeichert:", raw)
    pid=insta_post(raw,CAPTION,ig_uid,ig_tok)
    print("🎉 Instagram-Post ID:", pid)

if __name__=="__main__":
    main()
