#!/usr/bin/env python3
# ------------------------------------------------------------
# 1) ───── Dein unveränderter Bild-Generator ─────────────────
# ------------------------------------------------------------
import requests, json, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import matplotlib.pyplot as plt

URL       = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
W         = 1080
PAD       = 50
HBAR      = 140
CARD_H    = 110
RADIUS    = 25
RED_TOP   = (200, 20, 20)
RED_BOT   = (80,   0,  0)
CARD_BG   = (250, 250, 250)
TXT_COL   = (0,   0,   0)
TITLECOL  = (255, 255, 255)

def font(sz):
    try:  return ImageFont.truetype("arial.ttf", sz)
    except: return ImageFont.load_default()

def red_grad(draw, height):
    for y in range(height):
        t=y/(height-1)
        col=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(W,y)], fill=col)

tz=pytz.timezone("Europe/Berlin")
dm=datetime.now(tz).strftime("%d.%m")
raw=requests.get(URL).text
events=[e for e in json.loads(raw) if e["date"].endswith(dm)]

n=len(events) or 1
H=PAD+HBAR+PAD + n*CARD_H + max(n-1,0)*PAD + PAD

base=Image.new("RGB",(W,H))
draw=ImageDraw.Draw(base); red_grad(draw,H)

header=Image.new("RGBA",(W-2*PAD,HBAR),(255,255,255,40))
base.paste(header,(PAD,PAD),header)
draw.text((PAD*1.5,PAD+35),
          f"🔥  Events in Bielefeld – {dm}",
          font=font(60), fill=TITLECOL)

y=PAD+HBAR+PAD
for ev in events or [{"event":"Keine Events gefunden"}]:
    card=Image.new("RGBA",(W-2*PAD,CARD_H),CARD_BG+(255,))
    card=card.filter(ImageFilter.GaussianBlur(0.5))
    msk=Image.new("L",card.size,0)
    ImageDraw.Draw(msk).rounded_rectangle([0,0,*card.size],RADIUS,fill=255)
    base.paste(card,(PAD,y),msk)

    d=ImageDraw.Draw(base)
    txt=ev["event"]
    bbox=d.textbbox((0,0),txt,font=font(34))
    th=bbox[3]-bbox[1]
    d.text((PAD*2, y+(CARD_H-th)//2), txt, font=font(34), fill=TXT_COL)
    y+=CARD_H+PAD

# ------------------------------------------------------------
# 2) ───── Upload zum Repo + Instagram-Post ──────────────────
# ------------------------------------------------------------
import os, io, base64

def gh_upload(img_bytes, repo, token):
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    body={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    res=requests.put(url, headers=hdr, json=body, timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub upload failed: {res}")
    return res["content"]["download_url"]

def insta_post(img_url, caption, uid, token):
    base_url=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base_url}/media", data={
        "image_url":img_url,
        "caption":caption,
        "access_token":token}).json()["id"]
    pid=requests.post(f"{base_url}/media_publish", data={
        "creation_id":cid,
        "access_token":token}).json()["id"]
    return pid

# -------- Bild in Bytes wandeln --------
buf=io.BytesIO(); base.save(buf,"JPEG",quality=95)

# -------- ENV-Variablen holen --------
GH_TOKEN = os.getenv("GITHUB_TOKEN")
GH_REPO  = os.getenv("GITHUB_REPOSITORY")
IG_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IG_UID   = os.getenv("IG_USER_ID")
if not all([GH_TOKEN, GH_REPO, IG_TOKEN, IG_UID]):
    raise SystemExit("Fehlende ENV-Variablen!")

# -------- Upload + Post --------
raw_url = gh_upload(buf.getvalue(), GH_REPO, GH_TOKEN)

caption = "Mehr Events in der Bio 🔗\n\n" + "\n".join(f"• {e['event']}" for e in events)
post_id = insta_post(raw_url, caption, IG_UID, IG_TOKEN)

print("✅ Bild-URL:", raw_url)
print("🎉 Instagram-Post ID:", post_id)
