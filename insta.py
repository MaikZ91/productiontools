#!/usr/bin/env python3
"""
cards_feed.py – schicke Event-Cards wie ganz am Anfang, aber auto‐font
"""
import os, io, json, base64, requests, pytz
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ───────── Layout-Konstanten ─────────
W, PAD, HEAD_H = 1080, 50, 160          # Bildbreite, Außenabstand, Header
CARD_R, BLUR   = 25, 0.6                # Rundung, Weichzeichner
CARD_BG        = (250,250,250)
GRAD_TOP, GRAD_BOT = (200,20,20), (80,0,0)
TXT_COL, TITLECOL  = (0,0,0), (255,255,255)
MAX_CARDS      = 6                      # mehr → Caption

EVENTS_URL     = ("https://raw.githubusercontent.com/"
                  "MaikZ91/productiontools/master/events.json")

def font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):
        try: return ImageFont.truetype(name, pt)
        except: pass
    return ImageFont.load_default()

def gradient(d, h):
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(GRAD_TOP[i]*(1-t)+GRAD_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)], fill=c)

def load_events():
    tz=pytz.timezone("Europe/Berlin")
    today=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(EVENTS_URL,timeout=10).text
    ev=[e["event"] for e in json.loads(raw) if e["date"].endswith(today)]
    return ev[:MAX_CARDS], max(0,len(ev)-MAX_CARDS)

# ───────── Bild aufbauen ─────────
def build_image(events):
    n=len(events) or 1
    # Kartenhöhe so, dass sie gut ins Bild passen
    card_h=130 if n<=6 else 110
    H=PAD+HEAD_H+PAD + n*card_h + max(n-1,0)*PAD + PAD

    img=Image.new("RGB",(W,H)); d=ImageDraw.Draw(img); gradient(d,H)

    # Header
    tz=pytz.timezone("Europe/Berlin")
    d.text((PAD*1.5, PAD+45),
           f"🔥  Events in Bielefeld – {datetime.now(tz).strftime('%d.%m')}",
           font=font(72), fill=TITLECOL)

    # Schriftgröße = 70 % Kartendicke
    fsize=max(38,int(card_h*0.7)); fnt=font(fsize)

    y=PAD+HEAD_H+PAD
    for txt in events:
        card=Image.new("RGBA",(W-2*PAD,card_h),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(BLUR))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],
                                               CARD_R,fill=255)
        img.paste(card,(PAD,y),mask)

        bbox=d.textbbox((0,0),txt,font=fnt)
        d.text((PAD*2, y+(card_h-bbox[3])//2), txt, font=fnt, fill=TXT_COL)
        y+=card_h+PAD
    return img

# ───────── Hauptaufruf ‒ nur testen / lokal speichern ─────────
if __name__=="__main__":
    evts, rest = load_events()
    pic=build_image(evts or ["Keine Events gefunden"])
    pic.save("1012_events.jpg", format="JPEG", quality=95, dpi=(96,96))
    print("Bild gespeichert: 1012_events.jpg  –  überschüssige Events:", rest)
