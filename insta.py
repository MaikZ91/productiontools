#!/usr/bin/env python3
"""
insta_cards_uploader.py
-----------------------
• Erstellt das gewohnte Card-Bild(ern)
• Lädt es/sie nach images/YYYY/MM/dd/HHMM_events.jpg ins Repo
• Postet den Feed-Beitrag bei Instagram (Einzelbild oder Carousel)
"""

import requests, json, pytz, io, base64, os, time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

URL       = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
W, PAD    = 1080, 50
HBAR      = 140
CARD_H    = 110
RADIUS    = 25
RED_TOP, RED_BOT = (200,20,20), (80,0,0)
CARD_BG   = (250,250,250)
TXT_COL   = (0,0,0)
TITLECOL  = (255,255,255)
MAX_PER_IMG = 6

def font(pt:int):
    """Robuster Font-Loader: Arial → DejaVu → Bitmap"""
    for name in ("arialbd.ttf","arial.ttf"):
        try:
            return ImageFont.truetype(name, pt)
        except OSError:
            pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", pt)
    except OSError:
        return ImageFont.load_default()

def red_grad(d,h):
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def build_image(events):
    n=len(events) or 1
    H=PAD+HBAR+PAD + n*CARD_H + max(n-1,0)*PAD + PAD

    base=Image.new("RGB",(W,H))
    draw=ImageDraw.Draw(base); red_grad(draw,H)

    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    header=Image.new("RGBA",(W-2*PAD,HBAR),(255,255,255,40))
    base.paste(header,(PAD,PAD),header)
    draw.text((PAD*1.5,PAD+35),
              f"🔥  Events in Bielefeld – {dm}",
              font=font(60), fill=TITLECOL)

    y=PAD+HBAR+PAD
    for ev in events or [{"event":"Keine Events gefunden"}]:
        card=Image.new("RGBA",(W-2*PAD,CARD_H),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(0.5))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],
                                               RADIUS,fill=255)
        base.paste(card,(PAD,y),mask)

        txt=ev.get("event","")
        d=ImageDraw.Draw(base)
        bbox=d.textbbox((0,0),txt,font=font(34))
        th=bbox[3]-bbox[1]
        d.text((PAD*2, y+(CARD_H-th)//2), txt,
               font=font(34), fill=TXT_COL)
        y += CARD_H + PAD
    return base

# --- GitHub Upload ---
def gh_upload(img_bytes, repo, token):
    tz=pytz.timezone("Europe/Berlin")
    path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_%f_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    hdr={"Authorization":f"token {token}",
         "Accept":"application/vnd.github+json"}
    body={"message":"auto-upload events image",
          "content":base64.b64encode(img_bytes).decode()}
    res=requests.put(url,headers=hdr,json=body,timeout=15).json()
    if "content" not in res:
        raise RuntimeError(f"GitHub upload failed: {res}")
    return res["content"]["download_url"]

# --- Instagram Single Upload ---
def insta_single_post(image_url: str, caption: str, uid: str, token: str) -> str | None:
    base = f"https://graph.facebook.com/v21.0/{uid}"
    # 1: create media container
    r1 = requests.post(
        f"{base}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
        timeout=20
    )
    j1 = r1.json()
    cid = j1.get("id")
    if not cid:
        print(f"Error creating media: {j1}")
        return None
    time.sleep(15)
    # 2: publish
    r2 = requests.post(
        f"{base}/media_publish",
        data={"creation_id": cid, "access_token": token},
        timeout=20
    )
    return r2.json().get("id")

# --- Instagram Carousel Upload ---
def insta_carousel_post(image_urls: list[str], caption: str, uid: str, token: str) -> str | None:
    base = f"https://graph.facebook.com/v21.0/{uid}"
    # upload each image to get container IDs
    children = []
    for url in image_urls:
        r = requests.post(
            f"{base}/media",
            data={"image_url": url, "access_token": token},
            timeout=20
        )
        j = r.json()
        cid = j.get("id")
        if cid:
            children.append(cid)
        else:
            print(f"Error uploading carousel child: {j}")
    if not children:
        return None
    # create carousel container
    r1 = requests.post(
        f"{base}/media",
        data={
            "children": ",".join(children),
            "media_type": "CAROUSEL",
            "caption": caption,
            "access_token": token
        },
        timeout=20
    )
    j1 = r1.json()
    carousel_cid = j1.get("id")
    if not carousel_cid:
        print(f"Error creating carousel container: {j1}")
        return None
    time.sleep(15)
    # publish carousel
    r2 = requests.post(
        f"{base}/media_publish",
        data={"creation_id": carousel_cid, "access_token": token},
        timeout=20
    )
    return r2.json().get("id")

# --- Main Flow ---
def main():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events = [
    e for e in json.loads(raw)
    if e.get("date","?").endswith(dm)
       and "hochschulsport" not in e.get("event","").lower()
]
    # split events into chunks
    chunks = [events[i:i+MAX_PER_IMG] for i in range(0, len(events), MAX_PER_IMG)]

    # generate & upload images
    gh_tok=os.getenv("GITHUB_TOKEN"); gh_repo=os.getenv("GITHUB_REPOSITORY")
    ig_tok=os.getenv("IG_ACCESS_TOKEN"); ig_uid=os.getenv("IG_USER_ID")
    if not all([gh_tok,gh_repo,ig_tok,ig_uid]):
        raise SystemExit("Fehlende ENV-Variablen!")

    image_urls = []
    for chunk in chunks:
        img = build_image(chunk)
        buf = io.BytesIO(); img.save(buf,"JPEG",quality=95)
        url = gh_upload(buf.getvalue(), gh_repo, gh_tok)
        image_urls.append(url)

    # caption für alle Posts gleich
    base_caption = (
        "Weitere Events und Infos findest du in unserer App"
        " (Alle Angaben ohne Gewähr auf Richtigkeit) ➡ Link in Bio 🔗\n\n" +
        "\n".join(f"• {e.get('event','')}" for e in events)
    )

    # Post: Einzelbild oder Carousel
    if len(image_urls) == 1:
        pid = insta_single_post(image_urls[0], base_caption, ig_uid, ig_tok)
        print("🎉 IG-Post ID:", pid)
    else:
        pid = insta_carousel_post(image_urls, base_caption, ig_uid, ig_tok)
        print("🎉 IG-Carousel ID:", pid)

    # zusätzliche Montags/Mittwochs-Specials
    weekday = datetime.now(tz).weekday()
    if weekday == 0:
        insta_single_post(
            "https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png",
            "TUESDAY RUN 💪\n Anmeldung in Community, Link in der Bio🔗",
            ig_uid, ig_tok
        )
    if weekday == 2:
        insta_single_post(
            "https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png",
            "Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",
            ig_uid, ig_tok
        )
     if weekday == 6:
        insta_single_post(
            "https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png",
            "Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:
            • Premium Event Postings – Deine Events im Rampenlicht
            • Workshops & Talks – Teile dein Wissen mit engagierten Menschen
            • Lokale Werbung – Sichtbarkeit für deine Marke in Bielefeld
            Lass uns gemeinsam etwas bewegen.
            Jetzt Partner werden – schreib uns!
            #bielefeld #communitypower #netzwerk #eventsbielefeld #localbusiness #kooperation #sichtbarkeit",
            ig_uid, ig_tok
        )


    


    print("✅ Bilder hochgeladen:", image_urls)

if __name__=="__main__":
    main()
