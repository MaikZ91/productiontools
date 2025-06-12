
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event-Scraper (nur HEUTE) – Datenstruktur wie im 'impro'-Beispiel.
Speichert Ergebnis in events_today.json
"""

import concurrent.futures as cf
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# -------------------------- Konfiguration -------------------------- #
CITIES = {
    "Berlin": "berlin",
    "Hamburg": "hamburg",
    "München": "munich",
    "Köln": "cologne",
    "Frankfurt": "frankfurt",
    "Stuttgart": "stuttgart",
    "Düsseldorf": "duesseldorf",
    "Leipzig": "leipzig",
    "Hannover": "hanover",
    "Nürnberg": "nuremberg",
    "Bremen": "bremen",
    "Dresden": "dresden",
    "Essen": "essen",
    "Dortmund": "dortmund",
}

MONTH_MAP = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
MONTH_MAP.update({
    "Jan.": 1, "Feb.": 2, "Mär": 3, "Mrz": 3, "März": 3,
    "Apr.": 4, "Mai": 5, "Jun.": 6, "Juni": 6,
    "Jul.": 7, "Juli": 7, "Aug.": 8, "Sep.": 9, "Sept": 9,
    "Okt": 10, "Okt.": 10, "Nov.": 11, "Dez": 12, "Dez.": 12, "Dezember": 12
})
for k, v in list(MONTH_MAP.items()):
    MONTH_MAP[k.lower()] = v
    MONTH_MAP[k.capitalize()] = v

HEADERS = {"User-Agent": "Mozilla/5.0 (EventScraper/3.0)"}
TODAY = datetime.now(timezone.utc).date()
MAX_LINKS = 60
MAX_WORKERS = 10

# ----------------------- Hilfsfunktionen --------------------------- #
def parse_iso(txt: str) -> Optional[str]:
    m = re.search(r'(\d{1,2})\.\s*([A-Za-zÄÖÜäöü\.]+)\s*(\d{4})?', txt)
    if not m:
        return None
    day, mon_str, year = m.group(1), m.group(2).strip("."), m.group(3)
    mon = MONTH_MAP.get(mon_str)
    if not mon:
        return None
    year = int(year) if year else TODAY.year
    try:
        return datetime(year, mon, int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def iso_to_date(iso: str):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return None


def json_ld(soup: BeautifulSoup):
    tag = soup.find("script", type="application/ld+json")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except Exception:
            return {}
    return {}


def get_links(slug: str) -> List[str]:
    roots = [f"https://rausgegangen.de/en/{slug}/eventsbydate/",
             f"https://rausgegangen.de/en/{slug}/"]
    html = ""
    for root in roots:
        try:
            html = requests.get(root, headers=HEADERS, timeout=10).text
            break
        except requests.RequestException:
            continue
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/" in href:
            if href.startswith("/en/"):
                href = "https://rausgegangen.de" + href
            elif href.startswith("/"):
                href = "https://rausgegangen.de/en" + href
            elif not href.startswith("http"):
                href = "https://rausgegangen.de" + href
            links.append(href)
    return list(dict.fromkeys(links))[:MAX_LINKS]


# ----------------------- Detail-Scraper ---------------------------- #
def scrape_detail(url_city: tuple) -> Optional[Dict]:
    url, city = url_city
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except requests.RequestException:
        return None
    soup = BeautifulSoup(res.text, "html.parser")

    title_tag = soup.find(["h1", "h2"])
    title = title_tag.get_text(strip=True) if title_tag else "Unbenanntes Event"

    ld = json_ld(soup)
    start_iso = ld.get("startDate")
    date_iso = start_iso[:10] if start_iso else None
    time_str = start_iso[11:16] if start_iso else ""

    if not date_iso:
        txt = soup.get_text(" ", strip=True)
        date_iso = parse_iso(txt)
        m_t = re.search(r'\b(\d{1,2}:\d{2})\b', txt)
        time_str = m_t.group(1) if m_t else ""

    if not date_iso or iso_to_date(date_iso) != TODAY:
        return None

    location = ""
    loc_tag = soup.find("a", href=re.compile(r'/locations/'))
    if loc_tag:
        location = loc_tag.get_text(strip=True)

    # Kategorie: erstes Tag unterhalb der Überschrift (wenn vorhanden)
    cat = ""
    cat_tag = soup.find("span", class_=re.compile("tag"))
    if cat_tag:
        cat = cat_tag.get_text(strip=True)

    description = ""
    full = soup.get_text("\n")
    if "In the organizer's words:" in full:
        description = full.split("In the organizer's words:", 1)[1].split("\n", 1)[0].strip()

    img = ""
    m_img = re.search(r'https?://[^"\']+\.jpg', res.text)
    if m_img:
        img = m_img.group(0)

    date_fmt = datetime.strptime(date_iso, "%Y-%m-%d").strftime("%a, %d.%m.%Y")
    event_name = f"{title} (@{location})" if location else title

    return {
        "date":        date_fmt,
        "time":        time_str,
        "event":       event_name,
        "category":    cat,
        "description": description,
        "link":        url,
        "image_url":   img
    }

# ----------------------- Haupt­funktion ---------------------------- #
def main() -> None:
    print(f"► Scrape-Run für {TODAY} – max. {MAX_LINKS} Links/Stadt, {MAX_WORKERS} Threads\n")
    events: List[Dict] = []
    per_city = defaultdict(int)

    # 1) Link-Sammlung
    city_links = {c: get_links(s) for c, s in CITIES.items()}
    total = sum(len(lst) for lst in city_links.values())
    done = 0

    # 2) Parallel-Download
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(scrape_detail, (u, c))
                for c, lst in city_links.items() for u in lst]
        for fut in cf.as_completed(futs):
            done += 1
            ev = fut.result()
            if ev:
                events.append(ev)
                per_city[ev["event"].split("(@")[0].strip()]  # nur Statistik
            if done % 10 == 0 or done == total:
                pct = done / total * 100
                print(f"\r⌛ {done}/{total} Seiten … {pct:4.1f} %", end="", flush=True)

    # 3) Stadt-Zusammenfassung
    print("\n\nTreffer heute:")
    for city in CITIES:
        cnt = sum(1 for e in events if city in e["event"])
        print(f"  {city:11s}: {cnt}")

    Path("events_today.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n→ {len(events)} Events gespeichert in events_today.json")


if __name__ == "__main__":
    main()
