#!/usr/bin/env python3
# save_events_image_to_repo.py
import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -------- Konfiguration --------
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

WIDTH, PAD, HBAR, CARD_H, RADIUS = 1080, 50, 140, 110, 25
RED_TOP, RED_BOT   = (200, 20, 20), (80, 0, 0)
CARD_BG, TXT_COL   = (250, 250, 250), (0, 0, 0)
TITLECOL           = (255, 255, 255)

def font(sz):
    try: return ImageFont.truetype("arial.ttf", sz)
    except: return ImageFont.load_default()

def red_gradient(draw, h):
    for y in range(h):
        t   = y/(h-1)
        col = tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=col)

def fetch_today_events():
    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    data = requests.get(EVENTS_URL, timeout=10).json()
    evs = [e for e in data if e["date"].endswith(dm)]
    return evs or [{"event": "Keine Events gefunden"}]

def make_image(events):
    n  = len(events)
    H  = PAD + HBAR + PAD + n*CARD_H + max(n-1, 0)*PAD + PAD

    base = Image.new("RGB", (WIDTH, H))
    d    = ImageDraw.Draw(base)
    red_gradient(d, H)

    tz = pytz.timezone("Europe/Berlin")
    dm = datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (WIDTH-2*PAD, HBAR), (255,255,255,40))
    base.paste(header, (PAD, PAD), header)
    d.text((PAD*1.5, PAD+35),
           f"🔥  Events in Bielefeld – {dm}",
           font=font(60), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events:
        card = Image.new("RGBA", (WIDTH-2*PAD, CARD_H), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],
                                               RADIUS, fill=255)
        base.paste(card, (PAD, y), mask)

        txt  = ev["event"]
        bbox = d.textbbox((0,0), txt, font=font(34))
        th   = bbox[3]-bbox[1]
        d.text((PAD*2, y+(CARD_H-th)//2), txt,
               font=font(34), fill=TXT_COL)
        y += CARD_H + PAD
    return base

def upload_to_github(img_bytes, repo, token, branch="main"):
    tz      = pytz.timezone("Europe/Berlin")
    today   = datetime.now(tz).strftime("%Y/%m/%d")
    path    = f"images/{today}/events_today.jpg"

    url     = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github+json"
    }
    body    = {
        "message": "auto-upload events image",
        "content": base64.b64encode(img_bytes).decode(),
        "branch":  branch
    }
    resp = requests.put(url, headers=headers, json=body, timeout=15).json()
    if "content" not in resp:
        raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {resp}")
    return resp["content"]["download_url"]

def main():
    gh_token      = os.getenv("GH_TOKEN")
    gh_owner_repo = os.getenv("GH_OWNER_REPO")
    if not gh_token or not gh_owner_repo:
        raise SystemExit("GH_TOKEN und/oder GH_OWNER_REPO fehlen")

    events = fetch_today_events()
    img    = make_image(events)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    raw_url = upload_to_github(buf.getvalue(), gh_owner_repo, gh_token)

    print("✅ Bild gespeichert unter:", raw_url)

if __name__ == "__main__":
    main()
