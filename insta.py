#!/usr/bin/env python3
import requests, json, pytz, io, base64, os, time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, base64, json, requests, pytz
from datetime import datetime
from dateutil.parser import parse

URL = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
W, PAD = 1080, 50
HBAR = 140
CARD_H = 110
RADIUS = 25
RED_TOP, RED_BOT = (200,20,20), (80,0,0)
CARD_BG = (250,250,250)
TXT_COL = (0,0,0)
TITLE_COL = (255,255,255)
MAX_PER_IMG = 6
MIN_H = 1080

CATEGORY_MAP = {
    "Ausgehen": ["Party","Kneipe","Bar","Ausgehen","Konzert","Festival","forum","nrzp","sams","bunker","movie","platzhirsch","irish_pub", "f2f","stereobielefeld","cafe","cutie","Lokschuppen"],
    "Sport": ["Laufen","Fitness","Sport","Yoga","Workout","arminia"],
    "Kreativität": ["Kurs","Workshop","Lesung","Kreativ","Mal","Musik","Krakeln","alarmtheater"]
}

def font(pt:int):
    for name in ("arialbd.ttf","arial.ttf"):  
        try: return ImageFont.truetype(name, pt)
        except OSError: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", pt)
    except OSError: return ImageFont.load_default()

def red_grad(d,h):
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(RED_TOP[i]*(1-t)+RED_BOT[i]*t) for i in range(3))
        d.line([(0,y),(W,y)],fill=c)

def build_image(events: list[dict]) -> Image.Image:
    n = max(len(events),1)
    content_H = PAD+HBAR+PAD + n*CARD_H + max(n-1,0)*PAD + PAD
    H = max(content_H, MIN_H)
    y_offset = (H-content_H)//2
    base = Image.new("RGB",(W,H))
    draw = ImageDraw.Draw(base)
    red_grad(draw,H)
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    header=Image.new("RGBA",(W-2*PAD,HBAR),(255,255,255,40))
    base.paste(header,(PAD,PAD+y_offset),header)
    draw.text((PAD*1.5,PAD+35+y_offset),f"🔥  Events in Bielefeld – {dm}",font=font(60),fill=TITLE_COL)
    y=PAD+HBAR+PAD+y_offset
    for ev in events or [{"event":"Keine Events gefunden"}]:
        card=Image.new("RGBA",(W-2*PAD,CARD_H),CARD_BG+(255,))
        card=card.filter(ImageFilter.GaussianBlur(0.5))
        mask=Image.new("L",card.size,0)
        ImageDraw.Draw(mask).rounded_rectangle([0,0,*card.size],RADIUS,fill=255)
        base.paste(card,(PAD,y),mask)
        txt=ev.get("event","")
        d=ImageDraw.Draw(base)
        bbox=d.textbbox((0,0),txt,font=font(34))
        th=bbox[3]-bbox[1]
        d.text((PAD*2,y+(CARD_H-th)//2),txt,font=font(34),fill=TXT_COL)
        y+=CARD_H+PAD
    return base


def gh_upload(content_bytes: bytes, repo: str, token: str, path: str | None = None) -> str:
    tz=pytz.timezone("Europe/Berlin")
    if path is None:
        path=datetime.now(tz).strftime("images/%Y/%m/%d/%H%M_%f_events.jpg")
    url=f"https://api.github.com/repos/{repo}/contents/{path}"
    headers={"Authorization":f"token {token}","Accept":"application/vnd.github+json"}
    body={"message":f"auto-upload {os.path.basename(path)}","content":base64.b64encode(content_bytes).decode()}
    res=requests.put(url,headers=headers,json=body,timeout=15).json()
    if "content" not in res: raise RuntimeError(f"GitHub-Upload fehlgeschlagen: {res}")
    return res["content"]["download_url"]

def save_daily_json(events: list[dict], repo: str, token: str) -> str:
    categorized={cat:[] for cat in CATEGORY_MAP}
    uncategorized=[]
    for ev in events:
        desc=ev.get("event","")
        placed=False
        for cat,keywords in CATEGORY_MAP.items():
            if any(kw.lower() in desc.lower() for kw in keywords):
                categorized[cat].append(ev)
                placed=True
                break
        if not placed: uncategorized.append(ev)
    if uncategorized: categorized["Sonstige"]=uncategorized
    json_bytes=json.dumps(categorized,ensure_ascii=False,indent=2).encode("utf-8")
    tz = pytz.timezone("Europe/Berlin")
    now = datetime.now(tz)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = f"data/{now:%Y/%m/%d}/daily{timestamp}.json"

    return gh_upload(json_bytes,repo,token,path)

def insta_single_post(image_url:str,caption:str,uid:str,token:str)->str|None:
    base=f"https://graph.facebook.com/v21.0/{uid}"
    r1=requests.post(f"{base}/media",data={"image_url":image_url,"caption":caption,"access_token":token},timeout=20)
    j1=r1.json();cid=j1.get("id")
    if not cid:print(f"Error creating media: {j1}");return None
    time.sleep(15)
    r2=requests.post(f"{base}/media_publish",data={"creation_id":cid,"access_token":token},timeout=20)
    return r2.json().get("id")

def insta_carousel_post(image_urls:list[str],caption:str,uid:str,token:str)->str|None:
    base=f"https://graph.facebook.com/v21.0/{uid}"
    children=[]
    for url in image_urls:
        r=requests.post(f"{base}/media",data={"image_url":url,"access_token":token},timeout=20)
        j=r.json();cid=j.get("id");
        if cid:children.append(cid)
    if not children: return None
    r1=requests.post(f"{base}/media",data={"children":",".join(children),"media_type":"CAROUSEL","caption":caption,"access_token":token},timeout=20)
    j1=r1.json();carousel_cid=j1.get("id")
    if not carousel_cid: return None
    time.sleep(15)
    r2=requests.post(f"{base}/media_publish",data={"creation_id":carousel_cid,"access_token":token},timeout=20)
    return r2.json().get("id")

def main():
    tz=pytz.timezone("Europe/Berlin")
    dm=datetime.now(tz).strftime("%d.%m")
    raw=requests.get(URL,timeout=10).text
    events=[e for e in json.loads(raw) if e.get("date","?").endswith(dm) and "hochschulsport" not in e.get("event","").lower()]
    #events = [e for e in json.loads(raw) if e.get("date","?").endswith(dm)]
    

    gh_repo=os.getenv("GITHUB_REPOSITORY");gh_tok=os.getenv("GITHUB_TOKEN")
    save_daily_json(events,gh_repo,gh_tok)
    chunks=[events[i:i+MAX_PER_IMG] for i in range(0,len(events),MAX_PER_IMG)]
    image_urls=[]
    for chunk in chunks:
        img=build_image(chunk)
        buf=io.BytesIO();img.save(buf,"JPEG",quality=95)
        url=gh_upload(buf.getvalue(),gh_repo,gh_tok)
        image_urls.append(url)
    base_caption=("Weitere Events und Infos findest du in unserer App (Alle Angaben ohne Gewähr auf Richtigkeit) ➡ Link in Bio 🔗\n\n"+"\n".join(f"• {e.get('event','')}"for e in events))
    ig_tok=os.getenv("IG_ACCESS_TOKEN");ig_uid=os.getenv("IG_USER_ID")
    if len(image_urls)==1:print("🎉 IG-Post ID:",insta_single_post(image_urls[0],base_caption,ig_uid,ig_tok))
    else:print("🎉 IG-Carousel ID:",insta_carousel_post(image_urls,base_caption,ig_uid,ig_tok))
    weekday=datetime.now(tz).weekday()
    if weekday==0:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/ChatGPT%20Image%20Apr%2024%2C%202025%2C%2012_58_30%20PM.png","TRIBE TUESDAY RUN 💪\nJeden Dienstag, 18 Uhr | Gellershagen Park (am Teich)\nGemeinsam laufen, motivieren & Spaß haben.\nAnmeldung in der WhatsApp Community (-> Wöchentliche Umfrage), Link in der Bio🔗","",ig_tok)
    if weekday==2:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt.png","Tribe Powerworkout 💪\n Anmeldung in Community, Link in der Bio 🔗",ig_uid,ig_tok)
    if weekday==6:insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/Unbenannt3.png","Werde Partner – Deine Marke in der Bielefelder Community! Erreiche eine aktive Zielgruppe direkt vor Ort und präsentiere dich authentisch:",ig_uid,ig_tok)
    day=datetime.now(tz).day
    if day in (1,15):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Craetive.jpg","TRIBE CREATIVE CIRCLE - Dein Talent, deine Bühne. Jeden letzten Fr im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    if day in (2,16):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Wandern.jpg","TRIBE WANDERSAMSTAG - Immer am letzten Samstag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    if day in (3,17):insta_single_post("https://raw.githubusercontent.com/MaikZ91/productiontools/master/media/Kennenlernen.jpg","TRIBE KENNENLERNABEND - Immer am letzten Sonntag im Monat. Anmeldung in der Whats App Community",ig_uid,ig_tok)
    print("✅ Bilder hochgeladen:",image_urls)

if __name__=="__main__":main()
