#!/usr/bin/env python3
"""
insta.py  –  Events-Bild erzeugen, im Repo speichern, auf Instagram posten
===========================================================================

• Karten­höhe 170 px, Grundschrift 64 pt (fällt nur bis 36 pt, wenn nötig)
• Langer Titel? -> Halbautomatischer Umbruch auf max. zwei Zeilen
• Dateiname: images/YYYY/MM/dd/HHmm_events.jpg (eindeutig pro Lauf)

Benötigte ENV-Variablen:
  IG_ACCESS_TOKEN   –  Instagram Graph API Token (Secret)
  IG_USER_ID        –  IG Business-User-ID (Secret)
  GITHUB_TOKEN      –  vom Runner oder per PAT via Workflow
  GITHUB_REPOSITORY –  owner/repo (Runner)
"""

import os, io, base64, requests, pytz, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ────────────────── Layout-Konstanten ──────────────────
EVENTS_URL = ("https://raw.githubusercontent.com/"
              "MaikZ91/productiontools/master/events.json")

CAPTION = ("🔥 TRIBE WORKOUT – jeden Donnerstag! 💪 "
           "Kostenlos & offen für alle. #tribe #bielefeld #workout")

WIDTH, PAD, HBAR  = 1080, 50, 140            # Bildbreite, Außen­abstand, Headerhöhe
CARD_H, RADIUS    = 170, 25                  # Karten­höhe & Rundung
MAX_FONT, MIN_FONT= 64, 36                   # Schriftgrößen­range
RED_TOP, RED_BOT  = (200,20,20), (80,0,0)    # Hintergrund­gradient
CARD_BG, TXT_COL  = (250,250,250), (0,0,0)
TITLECOL          = (255,255,255)

# ────────────────── Basisfunktionen ──────────────────
def font(pt: int) -> ImageFont.FreeTypeFont:
    try:  return ImageFont.truetype("arial.ttf", pt)
    except: return ImageFont.load_default()

def gradient(draw: ImageDraw.ImageDraw, h: int):
    for y in range(h):
        t = y / (h-1)
        col = tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        draw.line([(0,y),(WIDTH,y)], fill=col)

def fetch_today_events() -> list[dict]:
    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    data = requests.get(EVENTS_URL, timeout=10).json()
    return [e for e in data if e["date"].endswith(dm)] or [{"event":"Keine Events gefunden"}]

# ────────── Text → Font-Größe + Zeilenumbruch ──────────
def fit_text(draw: ImageDraw.ImageDraw, text: str, max_w: int):
    """
    Versucht Schrift in MAX_FONT..MIN_FONT.
    Gibt (font, lines) zurück, wobei lines max. 2 Zeilen sind.
    """
    for size in range(MAX_FONT, MIN_FONT-1, -2):
        fnt = font(size)
        # erst ohne Umbruch testen
        if draw.textbbox((0,0), text, font=fnt)[2] <= max_w:
            return fnt, [text]

        # sonst versuchen, in 2 Zeilen zu umbrechen
        wrap = textwrap.wrap(text, width=42)  # grober Richtwert
        if len(wrap) <= 2 and all(draw.textbbox((0,0), ln, font=fnt)[2] <= max_w for ln in wrap):
            return fnt, wrap[:2]
    # Fallback kleinste Größe
    fnt = font(MIN_FONT)
    return fnt, textwrap.wrap(text, width=48)[:2]

# ────────────────── Bild bauen ──────────────────
def build_image(events: list[dict]) -> Image.Image:
    n   = len(events)
    H   = PAD + HBAR + PAD + n*CARD_H + max(n-1,0)*PAD + PAD
    img = Image.new("RGB", (WIDTH, H))
    d   = ImageDraw.Draw(img)
    gradient(d, H)

    tz  = pytz.timezone("Europe/Berlin")
    dm  = datetime.now(tz).strftime("%d.%m")
    header = Image.new("RGBA", (WIDTH-2*PAD, HBAR), (255,255,255,40))
    img.paste(header, (PAD,PAD), header)
    d.text((PAD*1.5, PAD+35),
           f"🔥  Events in Bielefeld – {dm}",
           font=font(70), fill=TITLECOL)

    y = PAD + HBAR + PAD
    for ev in events:
        card = Image.new("RGBA", (WIDTH-2*PAD, CARD_H), CARD_BG+(255,))
        card = card.filter(ImageFilter.GaussianBlur(0.5))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size], RADIUS, fill=255)
        img.paste(card, (PAD,y), mask)

        txt = ev["event"]
        fnt, lines = fit_text(d, txt, WIDTH-4*PAD)
        total_h = sum(d.textbbox((0,0), ln, font=fnt)[3] for ln in lines)
        offset_y = y + (CARD_H - total_h)//2

        for ln in lines:
            d.text((PAD*2, offset_y), ln, font=fnt, fill=TXT_COL)
            offset_y += d.textbbox((0,0), ln, font=fnt)[3]

        y += CARD_H + PAD
    return img

# ────────────────── GitHub Upload ──────────────────
def upload_to_repo(img_bytes: bytes, repo: str, token: str, branch=None) -> str:
    tz   = pytz.timezone("Europe/Berlin")
    path = datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_events.jpg")
    url  = f"https://api.github.com/repos/{repo}/contents/{path}"
    data = {
        "message": "auto-upload events image",
        "content": base64.b64encode(img_bytes).decode()
    }
    if branch: data["branch"] = branch
    hdr = {"Authorization": f"token {token}",
           "Accept": "application/vnd.github+json"}
    res = requests.put(url, headers=hdr, json=data, timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {res}")
    return res["content"]["download_url"]

# ────────────────── Instagram ──────────────────
def insta_post(raw_url, caption, uid, token, ver="v21.0"):
    base=f"https://graph.facebook.com/{ver}/{uid}"
    media = requests.post(f"{base}/media", data={
        "image_url":raw_url, "caption":caption, "access_token":token
    }, timeout=15).json()
    cid=media.get("id")
    if not cid: raise RuntimeError(f"Container-Fehler: {media}")
    pub = requests.post(f"{base}/media_publish", data={
        "creation_id":cid, "access_token":token
    }, timeout=15).json()
    if "id" not in pub: raise RuntimeError(f"Publish-Fehler: {pub}")
    return pub["id"]

# ────────────────── Main ──────────────────
def main():
    gh_tok = os.getenv("GITHUB_TOKEN")
    gh_rep = os.getenv("GITHUB_REPOSITORY")
    ig_tok = os.getenv("IG_ACCESS_TOKEN")
    ig_uid = os.getenv("IG_USER_ID")
    if not all([gh_tok, gh_rep, ig_tok, ig_uid]):
        raise SystemExit("ENV-Variablen fehlen!")

    img = build_image(fetch_today_events())
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)

    raw = upload_to_repo(buf.getvalue(), gh_rep, gh_tok)
    print("✅ Bild gespeichert:", raw)

    pid = insta_post(raw, CAPTION, ig_uid, ig_tok)
    print("🎉 Instagram-Post ID:", pid)

if __name__ == "__main__":
    main()
