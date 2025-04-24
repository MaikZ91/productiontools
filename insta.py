#!/usr/bin/env python3
"""
insta.py  –  Alle heutigen Events als 1-Slide posten
----------------------------------------------------
Bild: 1080 × dynamisch, Kartenhöhe 180 px, Grundschrift 90 pt
Caption: "Aktuelle Events in #Liebefeld" + Bullet-Liste
"""

import os, io, base64, requests, pytz, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────── Grund­parameter ─────────────
WIDTH, PAD, HBAR = 1080, 40, 140
CARD_H, RADIUS   = 180, 30
FONT_MAX, FONT_MIN = 90, 44
TXT_COL, CARD_BG = (15,15,15), (250,250,250)
GRAD_TOP, GRAD_BOT = (220,25,25), (85,0,0)

EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

# ───────────── Font-Loader ─────────────
def font(pt:int):
    try:  return ImageFont.truetype("arial.ttf", pt)
    except: return ImageFont.load_default()

# ───────────── Util ─────────────
def gradient(d,h):
    for y in range(h):
        t=y/(h-1)
        col=tuple(int(GRAD_TOP[i]*(1-t)+GRAD_BOT[i]*t) for i in range(3))
        d.line([(0,y),(WIDTH,y)],fill=col)

def today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    return [e for e in data if e["date"].endswith(dm)] or [{"event":"Keine Events gefunden"}]

def best_font(d,text,max_w):
    for pt in range(FONT_MAX, FONT_MIN-1, -2):
        if d.textbbox((0,0),text,font(font(pt)))[2]<=max_w:
            return font(pt)
    return font(FONT_MIN)

# ───────────── Bild-Generator ─────────────
def build_image(events):
    n=len(events)
    H=PAD+HBAR+PAD+n*CARD_H+max(n-1,0)*PAD+PAD
    img=Image.new("RGB",(WIDTH,H))
    d=ImageDraw.Draw(img)
    gradient(d,H)

    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    header=Image.new("RGBA",(WIDTH-2*PAD,HBAR),(255,255,255,40))
    img.paste(header,(PAD,PAD),header)
    d.text((PAD*1.2,PAD+32),f"🔥  Events in Liebefeld – {dm}",
           font=font(78),fill=(255,255,255))

    y=PAD+HBAR+PAD
    max_w=WIDTH-4*PAD
    for ev in events:
        card=Image.new("RGBA",(WIDTH-2*PAD,CARD_H),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(0.5))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],RADIUS,fill=255)
        img.paste(card,(PAD,y),mask)

        txt=ev["event"]
        fnt=best_font(d,txt,max_w)
        th=d.textbbox((0,0),txt,font=fnt)[3]
        d.text((PAD*2,y+(CARD_H-th)//2),txt,font=fnt,fill=TXT_COL)

        y+=CARD_H+PAD
    return img

# ───────────── Caption-Builder ─────────────
def build_caption(ev_list):
    lines=["Aktuelle Events in #Liebefeld"]
    for ev in ev_list:
        name = ev["event"]
        link = ev.get("link","🔗")
        at   = ev.get("at","📍")
        lines.append(f"• {name}  –  {link}  {at}")
    return "\n".join(lines)

# ───────────── GitHub + Instagram ─────────────
def upload(img_bytes,repo,token):
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    data={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    res=requests.put(url,headers=hdr,json=data,timeout=15).json()
    if "content" not in res: raise RuntimeError(res)
    return res["content"]["download_url"]

def post_insta(raw,caption,uid,token):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":raw,"caption":caption,"access_token":token},timeout=15).json().get("id")
    if not cid: raise RuntimeError("container fail")
    pub=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":token},timeout=15).json()
    if "id" not in pub: raise RuntimeError("publish fail")
    return pub["id"]

# ───────────── Main ─────────────
def main():
    gh_tok=os.getenv("GITHUB_TOKEN")
    gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN")
    ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_repo,ig_tok,ig_uid]):
        raise SystemExit("ENV fehlt")

    events=today_events()
    img=build_image(events)
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=96)

    raw=upload(buf.getvalue(),gh_repo,gh_tok)
    caption=build_caption(events)
    print("✅ Bild-URL:",raw)
    print("📝 Caption:\n",caption)

    post_id=post_insta(raw,caption,ig_uid,ig_tok)
    print("🎉 Insta-Post ID:",post_id)

if __name__=="__main__":
    main()
