#!/usr/bin/env python3
"""
insta_cards_autofit.py
Erzeugt eine Instagram-Grafik im Card-Layout:
• Rot-Gradient-Hintergrund, Glas-Header, 5 weiße Cards
• Schriftgröße passt sich automatisch an (≥ 60 pt)
"""

import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────── Layout ─────────
W, H           = 1080, 1350
PAD, HEAD_H    = 50, 180
CARD_R, BLUR   = 35, 0.6
BG_TOP, BG_BOT = (230,30,30), (90,0,0)
CARD_BG, TXT_COL = (250,250,250), (15,15,15)
FONT_MIN       = 60                # nie kleiner

EVENTS_URL     = ("https://raw.githubusercontent.com/"
                  "MaikZ91/productiontools/master/events.json")

def font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d):
    for y in range(H):
        t=y/(H-1)
        d.line([(0,y),(W,y)],
               fill=tuple(int(BG_TOP[i]*(1-t)+BG_BOT[i]*t) for i in range(3)))

def fetch_events(n=5):
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    ev=[e["event"] for e in data if e["date"].endswith(dm)]
    return ev[:n], max(0, len(ev)-n)

def build_image(events):
    lines=len(events)
    card_h = round((H - PAD - HEAD_H - PAD - (lines-1)*PAD) / lines)
    fsize  = max(FONT_MIN, int(card_h*0.55))
    fnt    = font(fsize)

    img=Image.new("RGB",(W,H))
    d  = ImageDraw.Draw(img); gradient(d)

    # Header (Glas)
    header = Image.new("RGBA",(W-2*PAD,HEAD_H),(255,255,255,50))
    img.paste(header,(PAD,PAD),header)
    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD*1.5, PAD+60),
           f"🔥 Aktuelle Events – {datetime.now(tz).strftime('%d.%m')}",
           font=font(90), fill=(255,255,255))

    y = PAD + HEAD_H + PAD
    for txt in events:
        # Card
        card=Image.new("RGBA",(W-2*PAD,card_h),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(BLUR))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],CARD_R,fill=255)
        img.paste(card,(PAD,y),mask)

        # Text
        bbox=d.textbbox((0,0),txt,font=fnt)
        d.text((PAD*2,y+(card_h-bbox[3])//2),txt,font=fnt,fill=TXT_COL)
        y+=card_h+PAD
    return img

# ───────── GitHub + Instagram ─────────
def gh_upload(buf, repo, token):
    path=datetime.now().strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r=requests.put(f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization":f"token {token}",
                 "Accept":"application/vnd.github+json"},
        json={"message":"auto upload","content":base64.b64encode(buf).decode()},
        timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(url, cap, uid, tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":url,"caption":cap,"access_token":tok}).json()["id"]
    pid=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":tok}).json()["id"]
    return pid

def make_caption(evs, extra):
    cap="Alle Details findest du in der Bio 🔗\n\n"
    cap+="\n".join(f"• {e}" for e in evs)
    if extra: cap+=f"\n… und {extra} weitere!"
    return cap

def main():
    gh_tk=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tk=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tk,gh_repo,ig_tk,ig_uid]): raise SystemExit("env fehlt")

    evts, rest=fetch_events()
    pic=build_image(evts)
    buf=io.BytesIO(); pic.save(buf,"JPEG",quality=96)

    raw=gh_upload(buf.getvalue(), gh_repo, gh_tk)
    insta_post(raw, make_caption(evts,rest), ig_uid, ig_tk)
    print("✅ gepostet:", raw)

if __name__=="__main__":
    main()
