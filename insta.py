#!/usr/bin/env python3
"""
insta_top5.py – zeige nur die fünf ersten Events,
                Schrift automatisch so groß wie möglich.
"""
import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Bild-Layout
W, H         = 1080, 1350        # Porträt
PAD, HEAD_H  = 50, 180
BG_TOP, BG_BOT = (225,30,30), (80,0,0)
TXT_COL      = (250,250,250)
STRIPE_W     = 50
EVENTS_URL   = ("https://raw.githubusercontent.com/"
                "MaikZ91/productiontools/master/events.json")

def load_font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d):
    for y in range(H):
        t = y/(H-1)
        c = tuple(int(BG_TOP[i]*(1-t)+BG_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)], fill=c)

def fetch_top5():
    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    data = requests.get(EVENTS_URL, timeout=10).json()
    events = [e["event"] for e in data if e["date"].endswith(dm)]
    return events[:5], max(0, len(events)-5)

def build_image(events):
    n = len(events) or 1
    free_h = H - (PAD + HEAD_H + PAD)
    line_h = free_h // n
    pt     = int(line_h * 0.85)
    if pt < 70: pt = 70             # Untergrenze
    fnt    = load_font(pt)

    img = Image.new("RGB", (W, H))
    d   = ImageDraw.Draw(img)
    gradient(d)

    # Header
    tz  = pytz.timezone("Europe/Berlin")
    d.text((PAD, PAD+50),
           f"🔥 Events {datetime.now(tz).strftime('%d.%m')}",
           font=load_font(105), fill=TXT_COL)

    y = PAD + HEAD_H
    for txt in events:
        # Farbstreifen
        d.rectangle([PAD, y, PAD+STRIPE_W, y+pt*1.25],
                    fill=(255,255,255,40))
        d.text((PAD+STRIPE_W+25, y + (line_h-pt)//2),
               txt, font=fnt, fill=TXT_COL)
        y += line_h
    return img

# ───────── GitHub & Instagram (unverändert) ─────────
import base64, requests
def gh_upload(buf, repo, token):
    path = datetime.now().strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r = requests.put(f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github+json"},
        json={"message":"upload events image",
              "content": base64.b64encode(buf).decode()},
        timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(url, cap, uid, tok):
    base = f"https://graph.facebook.com/v21.0/{uid}"
    cid = requests.post(f"{base}/media", data={
            "image_url": url, "caption": cap,
            "access_token": tok}).json().get("id")
    pid = requests.post(f"{base}/media_publish", data={
            "creation_id": cid, "access_token": tok}).json().get("id")
    if not pid: raise RuntimeError("publish error")
    return pid

def make_caption(events, extra):
    txt = "Alle weiteren Details findest du in der Bio 🔗\n\n"
    txt += "\n".join(f"• {e}" for e in events)
    if extra:
        txt += f"\n… und {extra} weitere Termine!"
    return txt

def main():
    gh_tok = os.getenv("GITHUB_TOKEN")
    gh_repo= os.getenv("GITHUB_REPOSITORY")
    ig_tok = os.getenv("IG_ACCESS_TOKEN")
    ig_uid = os.getenv("IG_USER_ID")
    if not all([gh_tok, gh_repo, ig_tok, ig_uid]):
        raise SystemExit("Environment-Variablen fehlen!")

    events, extra = fetch_top5()
    img   = build_image(events)
    buf   = io.BytesIO(); img.save(buf, "JPEG", quality=95)

    raw   = gh_upload(buf.getvalue(), gh_repo, gh_tok)
    insta_post(raw, make_caption(events, extra), ig_uid, ig_tok)
    print("✅ Gepostet:", raw)

if __name__ == "__main__":
    main()
