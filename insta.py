import requests, json
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ── SETTINGS ───────────────────────────────────────────────────
URL       = "https://raw.githubusercontent.com/MaikZ91/productiontools/master/events.json"
WIDTH     = 1080
PADDING   = 50
HEADER_H  = 140
CARD_H    = 110
RADIUS    = 25
TOP_RED   = (200, 20, 20)
BOT_RED   = ( 80,  0,  0)
WHITE     = (255,255,255)
BLACK     = (  0,  0,  0)

def load_font(sz):
    try:    return ImageFont.truetype("arial.ttf", sz)
    except: return ImageFont.load_default()

# ── 1. Events filtern ──────────────────────────────────────────
today = datetime.now().strftime("%d.%m")
events = [e for e in json.loads(requests.get(URL).text)
          if e["date"].endswith(today)]

# ── 2. Höhe dynamisch berechnen ───────────────────────────────
n       = max(1, len(events))
needed  = HEADER_H + PADDING + n*(CARD_H + PADDING) + PADDING
HEIGHT  = max(1080, needed)

# ── 3. Canvas + Gradient ──────────────────────────────────────
img  = Image.new("RGB", (WIDTH, HEIGHT))
draw = ImageDraw.Draw(img)
for y in range(HEIGHT):
    t = y/(HEIGHT-1)
    col = (
        int(TOP_RED[0]*(1-t) + BOT_RED[0]*t),
        int(TOP_RED[1]*(1-t) + BOT_RED[1]*t),
        int(TOP_RED[2]*(1-t) + BOT_RED[2]*t),
    )
    draw.line([(0,y),(WIDTH,y)], fill=col)

# ── 4. Header ─────────────────────────────────────────────────
draw.rectangle([0,0,WIDTH,HEADER_H], fill=(255,255,255,40))
draw.text(
    (PADDING, PADDING+35),
    f"🔥 Events in Bielefeld – {today}",
    font=load_font(60),
    fill=WHITE
)

# ── 5. Event-Cards ────────────────────────────────────────────
y = HEADER_H + PADDING
f_evt = load_font(34)
for ev in events or [{"event":"Keine Events gefunden"}]:
    draw.rounded_rectangle(
        [PADDING, y, WIDTH-PADDING, y+CARD_H],
        radius=RADIUS,
        fill=WHITE
    )
    # Text vertikal zentriert
    bbox = draw.textbbox((0,0), ev["event"], font=f_evt)
    th   = bbox[3] - bbox[1]
    draw.text(
        (PADDING*2, y + (CARD_H-th)//2),
        ev["event"], font=f_evt, fill=BLACK
    )
    y += CARD_H + PADDING

# ── 6. Crop auf max. 4:5 (0.8) Ratio → max Höhe = 1080/0.8 = 1350 px ─
max_h = int(WIDTH / 0.8)
if HEIGHT > max_h:
    img = img.crop((0, 0, WIDTH, max_h))
    HEIGHT = max_h

# ── 7. Speichern ──────────────────────────────────────────────
out = "events_dynamic_cropped.png"
img.save(out)
print(f"✅ Bild gespeichert: {out}  (Höhe: {HEIGHT}px)")
