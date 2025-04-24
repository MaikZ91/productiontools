#!/usr/bin/env python3
"""
insta.py
--------
1.  Lädt Events für den heutigen Tag.
2.  Baut daraus ein JPEG mit dynamischer Höhe.
3.  Speichert das Bild im Repo unter
      images/YYYY/MM/dd/HHmm_events.jpg
    (z. B. images/2025/04/24/0810_events.jpg)
4.  Postet die Raw-URL bei Instagram.

ENV-Variablen (nur zwei Secrets nötig):
  IG_ACCESS_TOKEN   – Graph-API-Token (instagram_content_publish)
  IG_USER_ID        – numerische IG-Business-User-ID
GitHub-seitig:
  GITHUB_TOKEN      – kommt automatisch vom Runner
  GITHUB_REPOSITORY – owner/repo
"""

import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────── Konfiguration ─────────────
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

CAPTION = ("🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 "
           "Kostenlos & offen für alle. #tribe #bielefeld #workout")

WIDTH, PAD, HBAR, CARD_H, RADIUS = 1080, 50, 140, 110, 25
RED_TOP, RED_BOT   = (200, 20, 20), (80, 0, 0)
CARD_BG, TXT_COL   = (250, 250, 250), (0, 0, 0)
TITLECOL           = (255, 255, 255)

# ───────────── Bild-Utilities ─────────────
def font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def gradient(draw: ImageDraw.ImageDraw, h: int):
    for y in range(h):
        t = y/(h-1)
        col = tuple(int(RED_TOP[i]*(1-t) + RED_BOT[i]*t) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=col)

def fetch_today_events() -> list[dict]:
    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    events = requests.get(EVENTS_URL, timeout=10).json()
    todays = [e for e in events if e["date"].endswith(dm)]
    return todays or [{"event": "Keine Events gefunden"}]

def build_image(events: list[dict]) -> Image.Image:
    n = len(events)
    H = PAD + HBAR + PAD + n*CARD_H + max(n-1,0)*PAD + PAD

    img = Image.new("RGB", (WIDTH, H))
    d   = ImageDraw.Draw(img)
    gradient(d, H)

    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (WIDTH-2*PAD, HBAR), (255,255,255,40))
    img.paste(header, (PAD, PAD), header)
    d.text((PAD*1.5, PAD+35), f"🔥  Events in Bielefeld – {dm}",
           font=font(60), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events:
        card = Image.new("RGBA", (WIDTH-2*PAD, CARD_H), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],
                                               RADIUS, fill=255)
        img.paste(card, (PAD, y), mask)

        txt  = ev["event"]
        bbox = d.textbbox((0,0), txt, font=font(34))
        th   = bbox[3]-bbox[1]
        d.text((PAD*2, y+(CARD_H-th)//2), txt,
               font=font(34), fill=TXT_COL)
        y += CARD_H + PAD
    return img

# ───────────── GitHub-Upload ─────────────
def upload_to_repo(img_bytes: bytes, repo: str, token: str,
                   branch: str | None = None) -> str:
    tz   = pytz.timezone("Europe/Berlin")
    now  = datetime.now(tz)
    # einzigartiger Dateiname: images/2025/04/24/0810_events.jpg
    path = now.strftime("images/%Y/%m/%d/%H%M_events.jpg")

    url  = f"https://api.github.com/repos/{repo}/contents/{path}"
    body = {
        "message": "auto-upload events image",
        "content": base64.b64encode(img_bytes).decode()
    }
    if branch:
        body["branch"] = branch

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    resp = requests.put(url, headers=headers, json=body, timeout=15).json()
    if "content" not in resp:
        raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {resp}")
    return resp["content"]["download_url"]

# ───────────── Instagram-Publish ─────────────
def publish_on_instagram(image_url: str, caption: str,
                         user_id: str, token: str,
                         version: str = "v21.0") -> str:
    base = f"https://graph.facebook.com/{version}/{user_id}"

    media = requests.post(f"{base}/media", data={
        "image_url": image_url,
        "caption":   caption,
        "access_token": token
    }, timeout=15).json()
    cid = media.get("id")
    if not cid:
        raise RuntimeError(f"Container-Fehler: {media}")

    publish = requests.post(f"{base}/media_publish", data={
        "creation_id": cid,
        "access_token": token
    }, timeout=15).json()
    if "id" not in publish:
        raise RuntimeError(f"Publish-Fehler: {publish}")
    return publish["id"]

# ───────────── Main ─────────────
def main():
    gh_token = os.getenv("GITHUB_TOKEN")          # vom Runner
    gh_repo  = os.getenv("GITHUB_REPOSITORY")     # owner/repo
    ig_token = os.getenv("IG_ACCESS_TOKEN")
    ig_user  = os.getenv("IG_USER_ID")

    if not all([gh_token, gh_repo, ig_token, ig_user]):
        raise SystemExit("ENV-Variablen fehlen.")

    img  = build_image(fetch_today_events())
    buf  = io.BytesIO(); img.save(buf, "JPEG", quality=95)

    raw_url = upload_to_repo(buf.getvalue(), gh_repo, gh_token)
    print("✅ Bild gespeichert:", raw_url)

    post_id = publish_on_instagram(raw_url, CAPTION, ig_user, ig_token)
    print("🎉 Instagram-Post: ", post_id)

if __name__ == "__main__":
    main()
