#!/usr/bin/env python3
"""
insta_cards_post.py
-------------------
• Holt Tages-Events aus events.json
• Rendert sie im „klassischen“ Card-Layout
• Lädt das JPEG ins eigene GitHub-Repo hoch
• Postet das Bild anschließend im Instagram-Feed
"""

import os, io, json, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────── Layout-Konstanten ─────────
W            = 1080                  # Bildbreite
PAD          = 50                    # allgemeines Padding
HEAD_H       = 140                   # Header-Höhe
CARD_H       = 110                   # Kartenhöhe
CARD_R       = 25                    # Rundung
BLUR         = 0.5                   # leichter Blur
GRAD_TOP, GRAD_BOT = (200,20,20), (80,0,0)
CARD_BG      = (250,250,250)
TXT_COL      = (0,0,0)
TITLECOL     = (255,255,255)
EVENTS_URL   = ("https://raw.githubusercontent.com/"
                "MaikZ91/productiontools/master/events.json")

# ───────── Hilfsfunktionen ─────────
def font(pt:int):
    for f in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(f, pt)
        except: pass
    return ImageFont.load_default()

def gradient(draw, h:int):
    for y in range(h):
        t=y/(h-1)
        col=tuple(int(GRAD_TOP[i]*(1-t)+GRAD_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(W,y)], fill=col)

def fetch_today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(EVENTS_URL,timeout=10).text
    data=json.loads(raw)
    return [e["event"] for e in data if e["date"].endswith(dm)]

# ───────── Bild erzeugen ─────────
def build_image(events:list[str]):
    n = max(len(events), 1)                      # mind. 1 Karte
    H = PAD + HEAD_H + PAD + n*CARD_H + max(n-1,0)*PAD + PAD
    base = Image.new("RGB",(W,H))
    d    = ImageDraw.Draw(base); gradient(d,H)

    # Header (Glas)
    header = Image.new("RGBA",(W-2*PAD,HEAD_H),(255,255,255,40))
    base.paste(header,(PAD,PAD),header)
    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD*1.5, PAD+35),
           f"🔥  Events in Bielefeld – {datetime.now(tz).strftime('%d.%m')}",
           font=font(60), fill=TITLECOL)

    # Karten loop
    y = PAD + HEAD_H + PAD
    for txt in (events or ["Keine Events gefunden"]):
        card = Image.new("RGBA",(W-2*PAD,CARD_H),CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(BLUR))
        mask = Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],CARD_R,fill=255)
        base.paste(card,(PAD,y),mask)

        d.text((PAD*2, y+(CARD_H-34)//2), txt,
               font=font(34), fill=TXT_COL)

        y += CARD_H + PAD
    return base

# ───────── GitHub-Upload ─────────
def upload_to_repo(img_bytes:bytes, repo:str, token:str) -> str:
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    body={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    res=requests.put(url,headers=hdr,json=body,timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {res}")
    return res["content"]["download_url"]

# ───────── Instagram-Publish ─────────
def post_on_instagram(img_url:str, caption:str,
                      uid:str, token:str) -> str:
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":img_url,
        "caption":caption,
        "access_token":token},timeout=15).json().get("id")
    if not cid: raise RuntimeError("Fehler beim Media-Container")
    pub=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,
        "access_token":token},timeout=15).json()
    if "id" not in pub: raise RuntimeError("Publish-Fehler")
    return pub["id"]

def make_caption(events, extra:int):
    cap = "Weitere Infos in der Bio 🔗\n\n"
    cap += "\n".join(f"• {e}" for e in events[:10])
    if extra:
        cap += f"\n… und {extra} weitere Termine!"
    return cap

# ───────── Main ─────────
def main():
    gh_tok = os.getenv("GITHUB_TOKEN")
    gh_repo= os.getenv("GITHUB_REPOSITORY")
    ig_tok = os.getenv("IG_ACCESS_TOKEN")
    ig_uid = os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_repo,ig_tok,ig_uid]):
        raise SystemExit("Fehlende ENV-Variablen!")

    events = fetch_today_events()
    extra  = max(0, len(events) - 10)
    img    = build_image(events[:10])           # nicht überfüllen
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=95)

    raw_url = upload_to_repo(buf.getvalue(), gh_repo, gh_tok)
    post_id = post_on_instagram(raw_url,
                                make_caption(events, extra),
                                ig_uid, ig_tok)

    print("✅ Bild:", raw_url)
    print("🎉 IG-Post ID:", post_id)

if __name__ == "__main__":
    main()
