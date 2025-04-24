#!/usr/bin/env python3
"""
insta_cards_uploader.py
-----------------------
• Erstellt das gewohnte Card-Bild
• Lädt es nach images/YYYY/MM/dd/HHMM_events.jpg ins Repo
• Postet den Feed-Beitrag bei Instagram
"""

# ───────── 1. Dein ursprünglicher Bild-Generator ─────────
import requests, json, pytz, io, base64, os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

URL       = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
W, PAD    = 1080, 50
HBAR      = 140
CARD_H    = 110
RADIUS    = 25
RED_TOP, RED_BOT = (200,20,20), (80,0,0)
CARD_BG   = (250,250,250)
TXT_COL   = (0,0,0)
TITLECOL  = (255,255,255)
weekday  = datetime.now(pytz.timezone("Europe/Berlin")).weekday() 

def font(pt:int):
    """Robuster Font-Loader: Arial → DejaVu → Bitmap"""
    for name in ("arialbd.ttf","arial.ttf"):
        try:
            return ImageFont.truetype(name, pt)
        except OSError:
            pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", pt)
    except OSError:
        return ImageFont.load_default()

def red_grad(d,h):
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def build_image(events):
    n=len(events) or 1
    H=PAD+HBAR+PAD + n*CARD_H + max(n-1,0)*PAD + PAD

    base=Image.new("RGB",(W,H))
    draw=ImageDraw.Draw(base); red_grad(draw,H)

    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    header=Image.new("RGBA",(W-2*PAD,HBAR),(255,255,255,40))
    base.paste(header,(PAD,PAD),header)
    draw.text((PAD*1.5,PAD+35),
              f"🔥  Events in Bielefeld – {dm}",
              font=font(60), fill=TITLECOL)

    y=PAD+HBAR+PAD
    for ev in events or [{"event":"Keine Events gefunden"}]:
        card=Image.new("RGBA",(W-2*PAD,CARD_H),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(0.5))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],
                                               RADIUS,fill=255)
        base.paste(card,(PAD,y),mask)

        txt=ev["event"]
        d=ImageDraw.Draw(base)
        bbox=d.textbbox((0,0),txt,font=font(34))
        th=bbox[3]-bbox[1]
        d.text((PAD*2, y+(CARD_H-th)//2), txt,
               font=font(34), fill=TXT_COL)
        y += CARD_H + PAD
    return base

# ───────── 2. GitHub-Upload ─────────
def gh_upload(img_bytes, repo, token):
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    body={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    res=requests.put(url,headers=hdr,json=body,timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub upload failed: {res}")
    return res["content"]["download_url"]

# ───────── 3. Instagram-Publish ─────────
def insta_post(img_url, caption, uid, token):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media", data={
        "image_url":img_url,
        "caption":caption,
        "access_token":token}, timeout=15).json()["id"]
    pid=requests.post(f"{base}/media_publish", data={
        "creation_id":cid,
        "access_token":token}, timeout=15).json()["id"]
    return pid

# ───────── 4. Haupt-Flow ─────────
def main():
    # Events laden
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events=[e for e in json.loads(raw) if e["date"].endswith(dm)]

    # Bild rendern
    img=build_image(events)
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=95)

    # ENV
    gh_tok=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_repo,ig_tok,ig_uid]):
        raise SystemExit("Fehlende ENV-Variablen!")

    # Upload + Post
    raw_url=gh_upload(buf.getvalue(), gh_repo, gh_tok)
    caption="Weitere Events und Infos findest du in unserer App (Alle Angaben ohne Gewähr auf Richtigkeit)➡ Link in Bio 🔗\n\n" + "\n".join(f"• {e['event']}" for e in events)
    post_id=insta_post(raw_url, caption, ig_uid, ig_tok)

    if weekday == 2:                         
        caption = "Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗"
        insta_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png"
, caption, ig_uid, ig_tok)

    if weekday == 3:                         
        caption = "TUESDAY RUN 💪\n Anmeldung in Community, Link in der Bio🔗"
        insta_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png"
, caption, ig_uid, ig_tok)
    

    print("✅ Bild:", raw_url)
    print("🎉 IG-Post ID:", post_id)

if __name__=="__main__":
    main()
