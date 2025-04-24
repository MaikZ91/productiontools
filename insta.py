#!/usr/bin/env python3
"""
insta.py
--------
1.  Lädt tagesaktuelle Events und baut daraus ein Bild (dynamische Höhe).
2.  Speichert das JPEG im aktuellen GitHub-Repository
    (Pfad: images/YYYY/MM/dd/events_today.jpg).
3.  Veröffentlicht das Bild im Instagram-Feed des hinterlegten
    Business-/Creator-Accounts.

Erforderliche ENV-Variablen (nur zwei Secrets nötig):
  IG_ACCESS_TOKEN   – Graph-API-Token (instagram_content_publish)
  IG_USER_ID        – numerische IG-Business-User-ID

GitHub-seitig:
  GITHUB_TOKEN      – wird pro Workflow automatisch erzeugt
  GITHUB_REPOSITORY – owner/repo (z. B. "MaikZ91/productiontools")
"""

import os, io, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────────────────────────────────────────────────────────
# Konstante Quellen / Layout-Parameter
# ───────────────────────────────────────────────────────────
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")
CAPTION = ("🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 "
           "Kostenlos & offen für alle. #tribe #bielefeld #workout")

WIDTH, PAD, HBAR, CARD_H, RADIUS = 1080, 50, 140, 110, 25
RED_TOP, RED_BOT   = (200, 20, 20), (80, 0, 0)
CARD_BG, TXT_COL   = (250, 250, 250), (0, 0, 0)
TITLECOL           = (255, 255, 255)

# ───────────────────────────────────────────────────────────
# Bild-Utilities
# ───────────────────────────────────────────────────────────
def font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def gradient(draw: ImageDraw.ImageDraw, height: int):
    for y in range(height):
        t = y / (height - 1)
        col = tuple(int(RED_TOP[i] * (1 - t) + RED_BOT[i] * t) for i in range(3))
        draw.line([(0, y), (WIDTH, y)], fill=col)

def fetch_events_today() -> list[dict]:
    tz = pytz.timezone("Europe/Berlin")
    today_dm = datetime.now(tz).strftime("%d.%m")
    events = requests.get(EVENTS_URL, timeout=10).json()
    todays = [e for e in events if e["date"].endswith(today_dm)]
    return todays or [{"event": "Keine Events gefunden"}]

def build_image(events: list[dict]) -> Image.Image:
    n = len(events)
    height = PAD + HBAR + PAD + n * CARD_H + max(n - 1, 0) * PAD + PAD

    img = Image.new("RGB", (WIDTH, height))
    d = ImageDraw.Draw(img)
    gradient(d, height)

    tz = pytz.timezone("Europe/Berlin")
    dm = datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (WIDTH - 2 * PAD, HBAR), (255, 255, 255, 40))
    img.paste(header, (PAD, PAD), header)
    d.text((PAD * 1.5, PAD + 35), f"🔥  Events in Bielefeld – {dm}",
           font=font(60), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events:
        card = Image.new("RGBA", (WIDTH - 2 * PAD, CARD_H), CARD_BG + (255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, *card.size], RADIUS, fill=255)
        img.paste(card, (PAD, y), mask)

        txt = ev["event"]
        bbox = d.textbbox((0, 0), txt, font=font(34))
        th = bbox[3] - bbox[1]
        d.text((PAD * 2, y + (CARD_H - th) // 2), txt,
               font=font(34), fill=TXT_COL)
        y += CARD_H + PAD

    return img

# ───────────────────────────────────────────────────────────
# GitHub-Upload (PUT /contents/)
# ───────────────────────────────────────────────────────────
def upload_to_repo(img_bytes: bytes, repo: str, token: str, branch: str | None = None) -> str:
    tz = pytz.timezone("Europe/Berlin")
    path = datetime.now(tz).strftime("images/%Y/%m/%d/events_today.jpg")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

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

# ───────────────────────────────────────────────────────────
# Instagram-Publish
# ───────────────────────────────────────────────────────────
def publish_on_instagram(image_url: str, caption: str, user_id: str, token: str,
                         api_version: str = "v21.0") -> str:
    base = f"https://graph.facebook.com/{api_version}/{user_id}"

    # 1. Medien-Container
    media = requests.post(f"{base}/media", data={
        "image_url": image_url,
        "caption": caption,
        "access_token": token
    }, timeout=15).json()
    creation_id = media.get("id")
    if not creation_id:
        raise RuntimeError(f"Container-Erstellung fehlgeschlagen: {media}")

    # 2. Publish
    publish = requests.post(f"{base}/media_publish", data={
        "creation_id": creation_id,
        "access_token": token
    }, timeout=15).json()
    if "id" not in publish:
        raise RuntimeError(f"Veröffentlichen fehlgeschlagen: {publish}")
    return publish["id"]

# ───────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────
def main():
    # GitHub (automatische Variablen)
    gh_token = os.getenv("GITHUB_TOKEN")          # wird vom Runner gesetzt
    gh_repo  = os.getenv("GITHUB_REPOSITORY")     # owner/repo

    # Instagram (Secrets)
    ig_token   = os.getenv("IG_ACCESS_TOKEN")
    ig_user_id = os.getenv("IG_USER_ID")

    if not all([gh_token, gh_repo, ig_token, ig_user_id]):
        raise SystemExit("Mindestens eine erforderliche ENV-Variable fehlt.")

    # 1) Bild erstellen
    img = build_image(fetch_events_today())
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)

    # 2) Bild ins Repo laden
    raw_url = upload_to_repo(buf.getvalue(), gh_repo, gh_token)
    print("✅ Bild gespeichert:", raw_url)

    # 3) Bei Instagram posten
    post_id = publish_on_instagram(raw_url, CAPTION, ig_user_id, ig_token)
    print("🎉 Instagram-Post erstellt, ID:", post_id)

if __name__ == "__main__":
    main()
