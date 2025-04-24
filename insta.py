#!/usr/bin/env python3
"""
insta_auto.py
──────────────
• Täglich: Event-Cards rendern, ins Repo hochladen, Feed + Story posten
• Dienstag: fixes Tuesday-Run-Bild (mit Datums-Overlay)   → Feed + Story
• Mittwoch: fixes Powerworkout-Bild (mit Datums-Overlay)  → Feed + Story
"""

import os, io, json, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------- Konstanten ----------
EVENTS_JSON = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
RAW_TUESDAY = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png"
RAW_WEDNES  = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png"

W, PAD, HBAR, CARD_H, RADIUS = 1080, 50, 140, 110, 25
RED_TOP, RED_BOT = (200, 20, 20), (80, 0, 0)
CARD_BG, TXT_COL, TITLECOL = (250, 250, 250), (0, 0, 0), (255, 255, 255)

tz      = pytz.timezone("Europe/Berlin")
today   = datetime.now(tz)
weekday = today.weekday()           # 0=Mo … 6=So
dm      = today.strftime("%d.%m")

GH_TOKEN = os.getenv("GITHUB_TOKEN")
GH_REPO  = os.getenv("GITHUB_REPOSITORY")
IG_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_UID   = os.getenv("IG_USER_ID")
if not all([GH_TOKEN, GH_REPO, IG_TOKEN, IG_UID]):
    raise SystemExit("Fehlende ENV-Variablen!")

# ---------- Fonts ----------
def font(pt):
    for name in ("arialbd.ttf", "arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except OSError: pass
    return ImageFont.truetype("DejaVuSans-Bold.ttf", pt)

# ---------- GitHub upload ----------
def gh_upload(img_bytes, subname):
    path = today.strftime(f"images/%Y/%m/%d/%H%M_{subname}.jpg")
    url  = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    payload = {"message": "auto-upload", "content": base64.b64encode(img_bytes).decode()}
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    res = requests.put(url, headers=headers, json=payload, timeout=15).json()
    if "content" not in res: raise RuntimeError(res)
    return res["content"]["download_url"]

# ---------- Insta Feed + Story ----------
def post_feed_and_story(img_url, caption):
    base = f"https://graph.facebook.com/v21.0/{IG_UID}"
    cid_feed = requests.post(f"{base}/media", data={
        "image_url": img_url, "caption": caption, "access_token": IG_TOKEN}).json()["id"]
    requests.post(f"{base}/media_publish", data={
        "creation_id": cid_feed, "access_token": IG_TOKEN})
    cid_story = requests.post(f"{base}/media", data={
        "image_url": img_url, "is_story": "true", "access_token": IG_TOKEN}).json()["id"]
    requests.post(f"{base}/media_publish", data={
        "creation_id": cid_story, "access_token": IG_TOKEN})

# ---------- Helper: Gradient ----------
def gradient(d, h):
    for y in range(h):
        t = y/(h-1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3)))

# ---------- Event-Bild ----------
def build_event_image(events):
    n = len(events) or 1
    H = PAD + HBAR + PAD + n*CARD_H + max(n-1, 0)*PAD + PAD
    img = Image.new("RGB", (W, H))
    d   = ImageDraw.Draw(img); gradient(d, H)

    header = Image.new("RGBA", (W-2*PAD, HBAR), (255, 255, 255, 40))
    img.paste(header, (PAD, PAD), header)
    d.text((PAD*1.5, PAD+35), f"🔥  Events in Bielefeld – {dm}",
           font=font(60), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events or [{"event":"Keine Events gefunden"}]:
        card = Image.new("RGBA", (W-2*PAD, CARD_H), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        msk  = Image.new("L", card.size, 0)
        ImageDraw.Draw(msk).rounded_rectangle([0,0,*card.size], RADIUS, fill=255)
        img.paste(card, (PAD, y), msk)
        ImageDraw.Draw(img).text((PAD*2, y+30), ev["event"],
                                 font=font(34), fill=TXT_COL)
        y += CARD_H + PAD
    return img

# ---------- Tages-Events ----------
events_raw = requests.get(EVENTS_JSON, timeout=15).text
events     = [e for e in json.loads(events_raw) if e["date"].endswith(dm)]
img_ev     = build_event_image(events)
buf_ev     = io.BytesIO(); img_ev.save(buf_ev, "JPEG", quality=95)
url_ev     = gh_upload(buf_ev.getvalue(), "events")
cap_ev = "Weitere Events – Link in Bio 🔗\n\n" + "\n".join(f"• {e['event']}" for e in events)
post_feed_and_story(url_ev, cap_ev)

# ---------- Dienstags- & Mittwochs-Bilder mit Overlay ----------
def post_raw_with_overlay(raw_url, subname, caption):
    img_bytes = requests.get(raw_url, timeout=15).content
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    ImageDraw.Draw(img).text((40, 40), dm, font=font(90), fill="white")
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
    url = gh_upload(buf.getvalue(), subname)
    post_feed_and_story(url, caption)

if weekday == 0:  # Dienstag
    post_raw_with_overlay(RAW_TUESDAY, "monday", "TUESDAY RUN 💪\nAnmeldung in Community – Link in Bio 🔗")
if weekday == 2:  # Mittwoch
    post_raw_with_overlay(RAW_WEDNES, "wednesday", "Tribe Powerworkout 💪\nAnmeldung in Community – Link in Bio 🔗")

print("✅ Tages-Workflow abgeschlossen")
