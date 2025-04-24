#!/usr/bin/env python3
"""
insta_autofit.py – alle Tages-Events auf einer Slide, maximale Schrift
"""
import os, io, base64, requests, pytz, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ───────── Layout ─────────
W, H        = 1080, 1350
PAD, HEAD_H = 40, 170
STRIPE_W    = 40
GAP         = 28
PT_MAX, PT_MIN = 130, 46
BG_TOP, BG_BOT = (235,40,40), (80,0,0)
TXT_COL     = (250,250,250)

EVENTS_URL  = ("https://raw.githubusercontent.com/"
               "MaikZ91/productiontools/master/events.json")

def load_font(pt:int):
    for nm in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(nm, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d):
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(BG_TOP[i]*(1-t)+BG_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def today_events():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    data=requests.get(EVENTS_URL,timeout=10).json()
    return [e["event"] for e in data if e["date"].endswith(dm)] or ["Keine Events hinterlegt"]

# ---------- Auto-Fit ----------
def fits(draw, lines, font, max_w):
    return all(draw.textbbox((0,0),ln,font=font)[2] <= max_w for ln in lines)

def wrap_lines(draw, text, font, max_w):
    """bricht per Wort, max 3 Zeilen"""
    words, line, out = text.split(), "", []
    for w in words:
        test = (line+" "+w).strip()
        if draw.textbbox((0,0),test,font=font)[2] <= max_w:
            line = test
        else:
            out.append(line); line = w
    out.append(line)
    return out[:3]

def pick_font(events, draw, max_w, max_h):
    for pt in range(PT_MAX, PT_MIN-1, -2):
        f = load_font(pt)
        total=0; ok=True
        for txt in events:
            lines = wrap_lines(draw, txt, f, max_w)
            if not fits(draw, lines, f, max_w): ok=False; break
            total += len(lines)*pt + GAP
        if ok and total-GAP <= max_h:
            return f
    return load_font(PT_MIN)

# ---------- Bild ----------
def build_image(events):
    img=Image.new("RGB",(W,H))
    d=ImageDraw.Draw(img); gradient(d)

    # Header
    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD, PAD+40),
           f"🔥 Events {datetime.now(tz).strftime('%d.%m')}",
           font=load_font(100), fill=TXT_COL)

    free_h = H - (PAD + HEAD_H + PAD)
    free_w = W - (PAD*2 + STRIPE_W + 20)
    font   = pick_font(events, d, free_w, free_h)

    y = PAD + HEAD_H
    for txt in events:
        # linker Streifen
        d.rectangle([PAD,y, PAD+STRIPE_W, y+font.size*1.3], fill=(255,255,255,40))
        lines = wrap_lines(d, txt, font, free_w)
        for ln in lines:
            d.text((PAD+STRIPE_W+20,y), ln, font=font, fill=TXT_COL)
            y += font.size
        y += GAP
    return img

# ---------- GitHub + Instagram ----------
def gh_upload(b, repo, token):
    p=datetime.now().strftime("images/%Y/%m/%d/%H%M_events.jpg")
    r=requests.put(f"https://api.github.com/repos/{repo}/contents/{p}",
        headers={"Authorization":f"token {token}",
                 "Accept":"application/vnd.github+json"},
        json={"message":"upload","content":base64.b64encode(b).decode()},
        timeout=15).json()
    if "content" not in r: raise RuntimeError(r)
    return r["content"]["download_url"]

def insta_post(raw, cap, uid, tok):
    base=f"https://graph.facebook.com/v21.0/{uid}"
    cid=requests.post(f"{base}/media",data={
        "image_url":raw,"caption":cap,"access_token":tok},
        timeout=15).json().get("id")
    pid=requests.post(f"{base}/media_publish",data={
        "creation_id":cid,"access_token":tok},
        timeout=15).json().get("id")
    if not pid: raise RuntimeError("publish fail"); return pid

def caption(evts):
    return "Alle Links in der Bio 🔗\n\n" + "\n".join(f"• {e}" for e in evts)

def main():
    gh_tk=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tk=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tk,gh_repo,ig_tk,ig_uid]): raise SystemExit("ENV fehlt")

    evs=today_events()
    pic=build_image(evs)
    buf=io.BytesIO(); pic.save(buf,"JPEG",quality=95)

    raw=gh_upload(buf.getvalue(),gh_repo,gh_tk)
    insta_post(raw, caption(evs), ig_uid, ig_tk)
    print("✅ Bild hochgeladen:", raw)

if __name__=="__main__":
    main()
