#!/usr/bin/env python3
"""
insta.py – Events-Bild für Instagram erstellen und posten
"""
import os, io, base64, requests, pytz, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────── Konstante Parameter ─────────────
WIDTH, PAD, HBAR = 1080, 40, 130          # breiterer Nutzenbereich
CARD_H, RADIUS   = 140, 25                # flachere Karten
TITLE_PT         = 78                     # Header-Schrift
TXT_COL          = (17,17,17)             # fast Schwarz
CARD_BG          = (250,250,250)
GRAD_TOP, GRAD_BOT= (225,30,30), (90,0,0)
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")
CAPTION = ("🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 "
           "Kostenlos & offen für alle. #tribe #bielefeld #workout")

def font(sz:int):
    try: return ImageFont.truetype("arial.ttf", sz)
    except: return ImageFont.load_default()

# ───────────── Daten laden ─────────────
def today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    return [e for e in data if e["date"].endswith(dm)] or [{"event":"Keine Events gefunden"}]

# ───────────── Hilfsfunktionen ─────────────
def gradient(draw,h):
    for y in range(h):
        t=y/(h-1)
        col=tuple(int(GRAD_TOP[i]*(1-t)+GRAD_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(WIDTH,y)],fill=col)

def wrap_text(draw,text,max_w,max_lines,base_size):
    """finde größte Schrift, max 2 Zeilen"""
    for pt in range(base_size,38,-2):
        f=font(pt)
        w=draw.textbbox((0,0),text,font=f)[2]
        if w<=max_w:
            return f,[text]
        # Umbruch
        wrap=textwrap.wrap(text,width=40)
        if len(wrap)<=max_lines and all(draw.textbbox((0,0),ln,font=f)[2]<=max_w for ln in wrap):
            return f,wrap
    f=font(38)
    return f,textwrap.wrap(text,width=45)[:max_lines]

# ───────────── Bild bauen ─────────────
def build_img(events):
    n=len(events)
    H=PAD+HBAR+PAD+n*CARD_H+max(0,n-1)*PAD+PAD
    img=Image.new("RGB",(WIDTH,H))
    d=ImageDraw.Draw(img)
    gradient(d,H)

    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    header=Image.new("RGBA",(WIDTH-2*PAD,HBAR),(255,255,255,40))
    img.paste(header,(PAD,PAD),header)
    d.text((PAD*1.2,PAD+28),f"🔥 Events in Bielefeld – {dm}",
           font=font(TITLE_PT),fill=(255,255,255))

    y=PAD+HBAR+PAD
    max_text_w=WIDTH-4*PAD
    base_pt=int(CARD_H*0.7)              # grob 70 % der Kartenhöhe
    for ev in events:
        card=Image.new("RGBA",(WIDTH-2*PAD,CARD_H),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(0.4))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],RADIUS,fill=255)
        img.paste(card,(PAD,y),mask)

        fnt,lines=wrap_text(d,ev["event"],max_text_w,2,base_pt)
        total_h=sum(d.textbbox((0,0),ln,font=fnt)[3] for ln in lines)
        cur_y=y+(CARD_H-total_h)//2
        for ln in lines:
            d.text((PAD*2,cur_y),ln,font=fnt,fill=TXT_COL)
            cur_y+=d.textbbox((0,0),ln,font=fnt)[3]

        y+=CARD_H+PAD
    return img

# ───────────── GitHub + Instagram ─────────────
def upload(img_b,re,tk):
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{re}/contents/{path}"
    body={"message":"auto-upload events image",
          "content":base64.b64encode(img_b).decode()}
    hd={"Authorization":f"token {tk}","Accept":"application/vnd.github+json"}
    r=requests.put(url,headers=hd,json=body,timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def post_insta(raw,cap,uid,tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":raw,"caption":cap,"access_token":tok},timeout=15).json().get("id")
    if not cid: raise RuntimeError("container error")
    res=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":tok},timeout=15).json()
    if "id" not in res: raise RuntimeError("publish error")
    return res["id"]

def main():
    gh_tok=os.getenv("GITHUB_TOKEN")
    gh_rep=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN")
    ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_rep,ig_tok,ig_uid]):
        raise SystemExit("ENV fehlt")

    pic=build_img(today_events())
    buf=io.BytesIO(); pic.save(buf,"JPEG",quality=96)

    raw=upload(buf.getvalue(),gh_rep,gh_tok)
    print("✅ Bild URL:",raw)
    pid=post_insta(raw,CAPTION,ig_uid,ig_tok)
    print("🎉 Insta-Post ID:",pid)

if __name__=="__main__":
    main()
