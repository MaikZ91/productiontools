#!/usr/bin/env python3
"""
insta_plain.py  –  Eine Slide, maximal große Schrift
----------------------------------------------------
Bild:  900 × 1350 (Portrait)
Font:  auto = (freier Platz pro Event) → niemals kleiner als 40 pt
Abschneiden:  ‚…‘ wenn Breite überschritten
"""
import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ───────── Parametrisierung ─────────
W, H       = 900, 1350
PAD, HEAD  = 40, 160
FONT_MIN   = 40
BG_GRAD    = (230,40,40), (80,0,0)
TXT_COL    = (245,245,245)
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

def fnt(pt):                        # immer Bold, wenn vorhanden
    for nm in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(nm, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d):
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(BG_GRAD[0][i]*(1-t)+BG_GRAD[1][i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def ellipsize(d,txt,font,max_w):
    """kürzt mit … bis es passt"""
    if d.textbbox((0,0),txt,font=font)[2]<=max_w: return txt
    while txt and d.textbbox((0,0),txt+"…",font=font)[2]>max_w:
        txt=txt[:-1]
    return txt+"…"

def load_today():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    ev=requests.get(EVENTS_URL,timeout=10).json()
    return [e["event"] for e in ev if e["date"].endswith(dm)] or ["Keine Events hinterlegt"]

def build_img(evts):
    n=len(evts)
    avail=H-PAD-HEAD-PAD                     # Höhe abzügl. Header
    line_h=avail//n
    size=max(FONT_MIN,int(line_h*0.8))
    font=fnt(size)

    img=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(img); gradient(d)

    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD, PAD+40),
           f"🔥  Events {datetime.now(tz).strftime('%d.%m')}",
           font=fnt(int(HEAD*0.45)), fill=TXT_COL)

    y=PAD+HEAD
    max_w=W-2*PAD
    for txt in evts:
        line=ellipsize(d,txt,font,max_w)
        d.text((PAD,y+(line_h-size)//2),line,font=font,fill=TXT_COL)
        y+=line_h
    return img

# ───── GitHub + Insta (wie gehabt, gestrafft) ─────
def gh_upload(b,repo,token):
    p=datetime.now(pytz.timezone("Europe/Berlin")).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r=requests.put(f"https://api.github.com/repos/{repo}/contents/{p}",
        headers={"Authorization":f"token {token}",
                 "Accept":"application/vnd.github+json"},
        json={"message":"upload","content":base64.b64encode(b).decode()},timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta(raw,cap,uid,tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={"image_url":raw,"caption":cap,
                "access_token":tok},timeout=15).json().get("id")
    pid=requests.post(f"{base}/media_publish",data={"creation_id":cid,
                "access_token":tok},timeout=15).json().get("id")
    if not pid: raise RuntimeError("publish fail"); return pid

def main():
    gh_tok=os.getenv("GITHUB_TOKEN"); gh_rep=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_rep,ig_tok,ig_uid]): raise SystemExit("ENV fehlt")

    evts=load_today()
    pic=build_img(evts)
    buf=io.BytesIO(); pic.save(buf,"JPEG",quality=95)

    raw=gh_upload(buf.getvalue(),gh_rep,gh_tok)
    cap="🔗 Alle Links in der Bio!\n\n"+"\n".join(f"• {e}" for e in evts[:10])
    pid=insta(raw,cap,ig_uid,ig_tok)
    print("✅ Upload:",raw,"\n🎉 Post ID:",pid)

if __name__=="__main__":
    main()
