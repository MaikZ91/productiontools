#!/usr/bin/env python3
"""
insta_top5.py  –  maximal 5 Events in einem Feed-Bild
"""
import os, io, base64, requests, pytz, math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ───────── Layout‐Konstanten ─────────
W, H        = 1080, 1350
PAD, HEAD_H = 40, 180
BG_TOP, BG_BOT = (225,35,35), (80,0,0)
TXT_COL     = (245,245,245)
FONT_MIN    = 80                          # fällt nie kleiner
EVENTS_URL  = ("https://raw.githubusercontent.com/"
               "MaikZ91/productiontools/master/events.json")

def font(pt:int):
    for n in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(n, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d):
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(BG_TOP[i]*(1-t)+BG_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def todays_events(max_items=5):
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    ev=[e["event"] for e in data if e["date"].endswith(dm)]
    return ev[:max_items], max(0,len(ev)-max_items)

def build_image(evts):
    n=len(evts)
    avail=H-PAD-HEAD_H-PAD
    line_h=avail//n
    pt=max(FONT_MIN,int(line_h*0.85))
    fnt=font(pt)

    img=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(img); gradient(d)

    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD, PAD+50),
           f"🔥 Events {datetime.now(tz).strftime('%d.%m')}",
           font=font(100), fill=TXT_COL)

    y_start = PAD + HEAD_H
    for txt in evts:
        y = y_start + (line_h-pt)//2
        d.text((PAD*2, y), txt, font=fnt, fill=TXT_COL)
        y_start += line_h
    return img

# ───────── GitHub + Insta ─────────
def gh_upload(b,repo,token):
    path=datetime.now().strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r=requests.put(f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization":f"token {token}",
                 "Accept":"application/vnd.github+json"},
        json={"message":"upload image","content":base64.b64encode(b).decode()},
        timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(url,cap,uid,tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":url,"caption":cap,"access_token":tok},timeout=15).json().get("id")
    pid=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":tok},timeout=15).json().get("id")
    if not pid: raise RuntimeError("publish fail")
    return pid

def caption(evts,extra):
    head="🔗 Alle Infos in der Bio"
    body="\n".join(f"• {e}" for e in evts)
    if extra: body+=f"\n… und {extra} weitere Termine!"
    return head+"\n\n"+body

def main():
    gh_tok=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_repo,ig_tok,ig_uid]): raise SystemExit("ENV fehlt")

    events, rest=todays_events()
    img=build_image(events)
    buf=io.BytesIO(); img.save(buf,"JPEG",quality=96)

    raw=gh_upload(buf.getvalue(),gh_repo,gh_tok)
    insta_post(raw,caption(events,rest),ig_uid,ig_tok)
    print("🎉 Gepostet:", raw)

if __name__=="__main__":
    main()
