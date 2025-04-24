#!/usr/bin/env python3
"""
insta_autofit.py  –  Eine Slide, beliebig viele Events, maximal große Schrift
"""
import os, io, base64, textwrap, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Layout & Farben
W,H           = 1080, 1350
PAD, HEAD_H   = 40, 170
STRIPE_W      = 40               # linker Farb­streifen
GAP           = 28               # Zwischen Zeilenblöcken
FONT_MAX, FONT_MIN = 130, 46
BG_GRAD_TOP, BG_GRAD_BOT = (235,40,40), (80,0,0)
TXT_COL       = (250,250,250)

EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

def load_font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except: pass
    return ImageFont.load_default()

def gradient(draw):
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(BG_GRAD_TOP[i]*(1-t)+BG_GRAD_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(W,y)], fill=c)

def today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    return [e["event"] for e in data if e["date"].endswith(dm)] or ["Keine Events hinterlegt"]

# ---------- Auto-Fit Solver ----------
def fit_font(events, draw, max_w, max_h):
    for pt in range(FONT_MAX, FONT_MIN-1, -2):
        f = load_font(pt)
        total = 0
        ok = True
        for txt in events:
            wrapped = textwrap.wrap(txt, width=999)  # wir umbrechen gleich konkret
            # Versuche 1-,2-,3-Zeilen-Wrap
            for lines in range(1,4):
                trial = textwrap.fill(txt, width=40//lines)  # grober Versuch
            # Jetzt echtes Wrap per Pixel
            words = txt.split()
            lines, line='', []
            for w in words:
                test = (line+' '+w).strip()
                if draw.textbbox((0,0),test,font=f)[2] <= max_w:
                    line = test
                else:
                    lines.append(line); line=w
            lines.append(line)
            if len(lines) > 3: ok=False; break
            total += len(lines)*pt + GAP
            if any(draw.textbbox((0,0),ln,font=f)[2] > max_w for ln in lines):
                ok=False; break
        if ok and total - GAP <= max_h:         # passt
            return f
    return load_font(FONT_MIN)

def build_image(events):
    img=Image.new("RGB",(W,H))
    d = ImageDraw.Draw(img); gradient(d)

    # Header
    tz=pytz.timezone("Europe/Berlin")
    head=f"🔥 Events {datetime.now(tz).strftime('%d.%m')}"
    d.text((PAD, PAD+40), head, font=load_font(100), fill=TXT_COL)

    # solve font size
    free_h = H - (PAD + HEAD_H + PAD)
    free_w = W - PAD*2 - STRIPE_W
    fnt = fit_font(events, d, free_w, free_h)

    # Draw events
    y = PAD + HEAD_H
    for txt in events:
        # Streifen
        d.rectangle([PAD, y, PAD+STRIPE_W, y+fnt.size*1.25], fill=(255,255,255,40))
        # Text wrap
        words, lines, line = txt.split(), [], ''
        for w in words:
            test=(line+' '+w).strip()
            if d.textbbox((0,0), test, font=fnt)[2] <= free_w:
                line=test
            else:
                lines.append(line); line=w
        lines.append(line)
        for ln in lines:
            d.text((PAD+STRIPE_W+20,y), ln, font=fnt, fill=TXT_COL)
            y += fnt.size
        y += GAP
    return img

# ---------- GitHub + Insta ----------
def gh_upload(buf, repo, token):
    tz=pytz.timezone("Europe/Berlin")
    p=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r=requests.put(f"https://api.github.com/repos/{repo}/contents/{p}",
        headers={"Authorization":f"token {token}","Accept":"application/vnd.github+json"},
        json={"message":"upload","content":base64.b64encode(buf).decode()},timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(img_url, cap, uid, tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media", data={
        "image_url":img_url,"caption":cap,"access_token":tok}, timeout=15).json().get("id")
    pid=requests.post(f"{base}/media_publish", data={
        "creation_id":cid,"access_token":tok}, timeout=15).json().get("id")
    if not pid: raise RuntimeError("publish error")
    return pid

def caption(evts):
    return "Alle Termine – Links in der Bio 🔗\n\n" + "\n".join(f"• {e}" for e in evts)

def main():
    gh_tk=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tk=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tk,gh_repo,ig_tk,ig_uid]): raise SystemExit("ENV fehlt")

    events=today_events()
    img=build_image(events)
    b=io.BytesIO(); img.save(b,"JPEG",quality=95)

    raw=gh_upload(b.getvalue(),gh_repo,gh_tk)
    insta_post(raw, caption(events), ig_uid, ig_tk)
    print("✅ Hochgeladen:", raw)

if __name__=="__main__":
    main()
