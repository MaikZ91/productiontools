import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
from datetime import datetime as dt, timedelta
from urllib.parse import urljoin,urlsplit, urlunsplit, parse_qsl, urlencode
import calendar
import traceback
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Zieljahr definieren (z. B. 2025)
TARGET_YEAR = 2025

# URLs der Quellen (angepasst für das gesamte Jahr)
bielefeld_guide = 'https://www.bielefeld-guide.de/events/weekend-guide/'
bielefeld_jetzt = f'https://www.bielefeld.jetzt/termine/suche?dateFrom={TARGET_YEAR}-01-01&dateTo={TARGET_YEAR}-12-31&rubrik%5B0%5D=k24&rubrik%5B1%5D=k246&rubrik%5B2%5D=k215&ort=0&stadtbezirk=0&freitext='
forum = 'https://forum-bielefeld.com/category/veranstaltungen/'
nrzp = 'https://nrzp.de/programm/'
bunker = 'https://bunker-ulmenwall.org/category/programm/'
sams = 'https://www.club-sams.de/'
movie = 'https://www.movie-bielefeld.de/'
platzhirsch = 'https://www.facebook.com/search/top?q=platzhirsch'
irish_pub = 'https://www.irishpub-bielefeld.de/'
f2f = 'https://face-to-face-dating.de/bielefeld'
stereobielefeld = 'https://stereo-bielefeld.de/programm/'
cafe = "https://cafeeuropa.de/"
arminia = "https://www.arminia.de/profis/saison/arminia-spiele"
cutie = "https://www.instagram.com/cutiebielefeld/?hl=de"

hsp="https://hsp.sport.uni-bielefeld.de/angebote/aktueller_zeitraum/"
theater= "https://theaterlabor.eu/veranstaltungskalender/"
vhs= "https://www.vhs-bielefeld.de"
impro = "https://www.yesticket.org/events/de/impro-bielefeld/?lastView=list"
germany = "https://rausgegangen.de/en/hamburg/eventsbydate/"

RAUSGEGANGEN_CITIES = {
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
    "Münster": "muenster",
    "Lübeck": "luebeck",
    "Detmold": "detmold" 
}

def scrape_events(base_url):
    events = []
    try:
        response = requests.get(base_url)
        soup = BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Fehler beim Abrufen von {base_url}: {e}")
        return events

    if base_url == bielefeld_guide:
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text()
            full_link = urljoin(base_url, href)
            date_match = re.search(r'\[(.*?)\]', text)
            if date_match:
                date = date_match.group(1)
                try:
                    event = text.split('] ')[1].strip()
                except IndexError:
                    event = text.strip()
                if '+' in date:
                    dates = split_dates(date)
                    for single_date in dates:
                        events.append({
                            'date': single_date,
                            'event': event,
                            'link': full_link
                        })
                elif '–' in date:
                    dates = split_dates2(date)
                    for single_date in dates:
                        events.append({
                            'date': single_date,
                            'event': event,
                            'link': full_link
                        })
                else:
                    events.append({
                        'date': date,
                        'event': event,
                        'link': full_link
                    })
    
    _date_re  = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
    _time_re  = re.compile(r'(\d{1,2}:\d{2})')  
    if base_url == bielefeld_jetzt:
        event_containers = soup.find_all("div", class_="veranstaltung")
        for event_container in event_containers:
            try:
                event_link = event_container.find("a", class_="box-item")["href"]
                event_name = event_container.find("h3").get_text(strip=True)

                p_tags = event_container.find_all("p")
                if len(p_tags) >= 3:
                    event_category = p_tags[0].get_text(strip=True)  # Neu: Kategorie
                    raw_event_date = p_tags[1].get_text(" ", strip=True)
                    event_location = p_tags[2].get_text(strip=True)

                    # ---------- Datum ----------------------------------------
                    m_date = _date_re.search(raw_event_date)
                    if m_date:
                        formatted_event_date = dt.strptime(m_date.group(1), "%d.%m.%Y").strftime("%a, %d.%m.%Y")    
                    else:
                        formatted_event_date = raw_event_date  # Fallback

                    # ---------- Start-Uhrzeit --------------------------------
                    m_time = _time_re.search(raw_event_date)
                    start_time = m_time.group(1) if m_time else None

                    formatted_event_name = f"{event_name} (@{event_location})"

                    # ---------- Beschreibung nachladen ------------------------
                    description = ""
                    try:
                        detail_resp = requests.get(urljoin(base_url, event_link), timeout=10)
                        detail_resp.raise_for_status()
                        detail_html  = detail_resp.text       
                        detail_soup  = BeautifulSoup(detail_html, "html.parser")

                        image_url = None                                 
                        thumb = event_container.find("img")
                        if thumb and thumb.get("src"):
                            image_url = urljoin(base_url, thumb["src"])
                        if not image_url and detail_html:
                                detail_soup = BeautifulSoup(detail_html, "html.parser")
                                og = detail_soup.find("meta", property="og:image")
                                if og and og.get("content"):
                                    image_url = urljoin(base_url, og["content"])

            
                        for selector in (
                            "div.text", "div.teaser", "div.v-copy", "div.cms-text", "article .text"
                        ):
                            node = detail_soup.select_one(selector)
                            if node and node.get_text(strip=True):
                                description = re.sub(r"\s+", " ", node.get_text(" ")).strip()
                                break
                        if not description:
                            first_p = detail_soup.find("p")
                            if first_p:
                                description = re.sub(r"\s+", " ", first_p.get_text(" ")).strip()
                    except Exception as ex:
                        print(f"Fehler beim Laden der Detailseite: {ex}")
                        description = ""

                    # ---------- Ausschlussfilter -----------------------------
                    if not any(sub in event_location for sub in [
                        "Nr. z. P", "Bunker Ulmenwall", "Forum",
                        "Johanneskirche Quelle (ev.)", "Zionskirche Bethel (ev.)",
                        "Altstädter Nicolaikirche (ev.)", "Peterskirche Kirchdornberg (ev.)",
                        "Johanniskirche (ev.)", "Peter-und-Pauls-Kirche Heepen (ev.)",
                        "Neustädter Marienkirche (ev.)", "Kirche Brake (ev.)",
                        "Haus der Kirche", "Capella Hospitalis",
                        "Thomaskirche Schildesche (ev.)", "Eckardtsheim",
                        "Ev.-Luth. Bartholomäus-Kirchengemeinde Bielefeld-Brackwede",
                        "Bartholomäuskirche Brackwede (ev.-luth.)",
                        "St. Jodokus-Kirche (kath.)", "Theaterwerkstatt Bethel",
                        "Pappelkrug", "Marienkirche Jöllenbeck (ev.)",
                        "Haus Wellensiek", "Neue Schmiede", "Movement-Theater",
                        "Musik- und Kunstschule", "Bielefeld-Schildesche",
                        "Kreuzkirche Sennestadt (ev.)",
                        "Museum Peter August Böckstiegel", "Bielefeld-Gadderbaum",
                        "Süsterkirche (ev.-ref.)", "Ev. Kirche Ummeln"
                    ]):
                        events.append({
                            'date': formatted_event_date,
                            'time': start_time,
                            'event': formatted_event_name,
                            'category': event_category,  # Neu
                            'description': description,
                            "image_url":   image_url, 
                            'link': urljoin(base_url, event_link)
                        })
            except Exception as e:
                print(f"Fehler bei bielefeld.jetzt: {e}")
                continue

    if base_url == sams:
        columns = soup.find_all('div', class_='col')
        for col in columns:
            link_tag = col.find('a')
            event_link = urljoin(base_url, link_tag['href'])
    
            head_tag = col.find('span', class_='head')
            event_name = f"{head_tag.get_text(strip=True)} (@sams_bielefeld)"
    
            content_tag = col.find('div', class_='content')
            if content_tag:
                start_text = content_tag.get_text(strip=True)
                if 'Start:' in start_text:
                    start_date = start_text.split('Start: ')[1]
    
                    # Datums- und Zeit­objekt erzeugen
                    date_obj = datetime.datetime.strptime(start_date, '%d.%m.%Y %H:%M')
    
                    # Formatierungen
                    formatted_date = date_obj.strftime('%a, %d.%m')   # z. B. "Do, 05.06"
                    formatted_time = date_obj.strftime('%H:%M')       # z. B. "19:00"
                    img_tag = col.find('img')
                    image_url = urljoin(base_url, img_tag['src']) if img_tag and img_tag.get('src') else None
    
                    events.append({
                        'date': formatted_date,
                        'time': formatted_time,      # <-- neue Uhrzeit-Spalte
                        'event': event_name,
                        'category': 'Party',
                        'link': event_link,
                        'image_url': image_url
                    })
    if base_url == forum:
        articles = soup.find_all('article', class_='post')
        for article in articles:
            date_div = article.find('div', class_='forumevent_date')
            if date_div:
                day = date_div.find('span', class_='day').text.strip()
                month_name = date_div.find('span', class_='month').text.strip()
                try:
                    month_number = datetime.datetime.strptime(month_name, '%b').strftime('%m')
                except Exception:
                    month_number = '00'
                dayname = date_div.find('span', class_='dayname').text[:2]
                date = f"{dayname}, {day}.{month_number}"
                title_div = article.find('div', class_='entry-title')
                if title_div:
                    event = f"{title_div.get_text(strip=True)} (@forum_bielefeld)"
                    full_link = urljoin(base_url, title_div.find('a')['href'])
                    image_url = ""
                    # 1) Teaser-Bild im Listing
                    img_tag = (
                        article.select_one("img")              # <img> oder <picture><img>
                        or article.select_one("picture img")
                    )
                    if img_tag:
                        image_url = urljoin(
                            base_url,
                            img_tag.get("src")
                            or img_tag.get("data-src")
                            or img_tag.get("data-lazy-src")
                            or (img_tag.get("srcset") or "").split(" ")[0]
                            or "",
                        )
            
                    # 2) Fallback Detailseite
                    if not image_url:
                        try:
                            detail_html = requests.get(full_link, timeout=10).text
                            d_soup      = BeautifulSoup(detail_html, "html.parser")
            
                            # a) OpenGraph
                            og = d_soup.find("meta", property="og:image")
                            if og and og.get("content"):
                                image_url = urljoin(base_url, og["content"])
            
                            # b) Erstes <figure>- oder <img>-Tag
                            if not image_url:
                                d_img = d_soup.select_one("figure img") or d_soup.find("img")
                                if d_img and d_img.get("src"):
                                    image_url = urljoin(base_url, d_img["src"])
                        except Exception:
                            pass  
                    events.append({
                        'date': date,
                        'event': event,
                        'link': full_link,
                        'image_url': image_url
                    })

    if base_url == cafe:
        MONTHS = {
            "Januar": "01",  "Februar": "02", "März": "03", "April": "04",
            "Mai": "05",     "Juni": "06",    "Juli": "07", "August": "08",
            "September": "09","Oktober": "10","November": "11","Dezember": "12"
        }
    
        ticket_links = soup.find_all('a', string=lambda s: s and "Tickets kaufen" in s)
        for link in ticket_links:
            # --- Event-Titel ----------------------------------------------------
            title_elem = link.find_previous(
                lambda tag: tag.name in ['h2', 'h3', 'h4'] and "•" in tag.get_text()
            )
            if not title_elem:
                continue
            event_title = title_elem.get_text(strip=True)
    
            # --- Datum herausziehen --------------------------------------------
            prev_text = title_elem.find_previous(string=re.compile(r'\d{1,2}\.\s*[A-Za-zäöüÄÖÜ]+'))
            if not prev_text:
                continue
            date_text = prev_text.strip()
    
            m = re.search(r'(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)', date_text)
            if not m:
                continue
            day, month_name = m.groups()
            month_number = MONTHS.get(month_name, "00")
    
            # --- Uhrzeit suchen -------------------------------------------------
            # 1) Direkt in der Nähe eines <time>, <span> oder <p>-Tags …
            time_elem = title_elem.find_next(
                lambda tag: tag.name in ['time', 'span', 'p'] 
                and re.search(r'\d{1,2}:\d{2}', tag.get_text())
            )
    
            # 2) … oder im reinen Text der nächsten Geschwister
            if time_elem:
                time_match = re.search(r'(\d{1,2}:\d{2})', time_elem.get_text())
            else:
                time_str_candidate = title_elem.find_next(string=re.compile(r'\d{1,2}:\d{2}'))
                time_match = re.search(r'(\d{1,2}:\d{2})', time_str_candidate or '')
    
            event_time = time_match.group(1) if time_match else "00:00"   # Fallback
    
            # --- Datum (inkl. Verschiebung um −1 Tag) ---------------------------
            candidate_date = datetime.datetime(TARGET_YEAR, int(month_number), int(day))
            event_year = TARGET_YEAR if candidate_date.date() >= datetime.date(TARGET_YEAR, 1, 1) else TARGET_YEAR + 1
            event_date = datetime.datetime(event_year, int(month_number), int(day))
            adjusted_date = event_date - datetime.timedelta(days=1)
    
            weekday_map = {"Mon": "Mo", "Tue": "Di", "Wed": "Mi",
                           "Thu": "Do", "Fri": "Fr", "Sat": "Sa", "Sun": "So"}
            weekday_candidate = weekday_map.get(adjusted_date.strftime("%a"), adjusted_date.strftime("%a"))
            date_str = f"{weekday_candidate}, {adjusted_date.day:02d}.{adjusted_date.month:02d}"
    
            # --- Event-Dict -----------------------------------------------------
            full_link = urljoin(base_url, link.get('href'))
            img_tag = title_elem.find_previous("img")
            image_url = urljoin(base_url, img_tag["src"]) if img_tag else None
            events.append({
                "date":     date_str,
                "time":     event_time,            # <-- neue Uhrzeit-Spalte
                "event":    f"{event_title} (@cafe_europa_bi)",
                "category": "Party",
                "link":     full_link,
                'image_url': image_url
            })

    if base_url == nrzp:
            for row in soup.find_all('div', class_='eventcalender-row'):

                # -------- Datum ----------------------------------------------------
                raw_date = row.find('div', class_='eventcalender-date')
                if not raw_date:
                    continue

                m = re.match(r'(\w{2})\. (\d{2}) (\d{2})', raw_date.get_text(strip=True))
                if not m:
                    continue

                day_abbr, day, month = m.groups()
                event_date = f"{day_abbr}, {day}.{month}"          # z. B. "Fr, 13.06"

                # -------- Link, Titel, (erste) Uhrzeit  ----------------------------
                btn = row.find_next_sibling('a', class_='menu_btn')
                if not btn:
                    continue

                title_span = btn.find('span', class_='span_left')
                if not title_span:
                    continue

                event_name = f"{title_span.get_text(strip=True)} (@nr.z.p)"
                event_link = urljoin(base_url, btn.get('href', ''))

                # Uhrzeit kann im Button rechts stehen (span_right) oder im Listing
                time_str = ''
                time_holder = (btn.find('span', class_='span_right')  or
                            row.find('div',  class_='eventcalender-time'))
                if time_holder:
                    m_t = re.search(r'(\d{1,2})[:.](\d{2})', time_holder.get_text())
                    if m_t:
                        h, mi = m_t.groups()
                        time_str = f"{int(h):02d}:{mi}"

                # -------- Bild ------------------------------------------------------
                image_url = ''

                # 1) CSS-Hintergrund der <div class="eventcalender-img">
                bg_div = row.find('div', class_='eventcalender-img')
                if bg_div and 'background-image' in (style := bg_div.get('style', '')):
                    m_bg = re.search(r'url\([\'"]?([^\'")]+)', style)
                    if m_bg:
                        image_url = urljoin(base_url, m_bg.group(1))

                # 2) <img> im Listing / Button
                if not image_url:
                    img_tag = (row.find('img') or btn.find('img'))
                    if img_tag:
                        src = (img_tag.get('src') or img_tag.get('data-src') or
                            (img_tag.get('srcset') or '').split(' ')[0])
                        if src:
                            image_url = urljoin(base_url, src)

                # 3) Detailseite: og:image oder erstes Bild
                if (not image_url) or (not time_str):
                    try:
                        detail_html = requests.get(event_link, timeout=10).text
                        d_soup = BeautifulSoup(detail_html, 'html.parser')

                        # Uhrzeit hier nachholen, falls noch leer
                        if not time_str:
                            t_detail = re.search(
                                r'(\d{1,2})[:.](\d{2})\s*Uhr',
                                d_soup.get_text(' ', strip=True)
                            )
                            if t_detail:
                                h, mi = t_detail.groups()
                                time_str = f"{int(h):02d}:{mi}"

                        # Bild suchen
                        if not image_url:
                            og = d_soup.find('meta', property='og:image')
                            if og and og.get('content'):
                                image_url = urljoin(base_url, og['content'])
                            if not image_url:
                                d_img = d_soup.select_one('figure img') or d_soup.find('img')
                                if d_img and d_img.get('src'):
                                    image_url = urljoin(base_url, d_img['src'])
                    except Exception:
                        pass   # Detailseite nicht erreichbar → kein Crash

                events.append({
                    'date':  event_date,
                    'time':  time_str,          # <─ jetzt immer HH:MM (oder '')
                    'event': event_name,
                    'link':  event_link,
                    'image_url': image_url or ''
                })
        

    if base_url == bunker:
        months = {
            'Januar': 'January', 'Februar': 'February', 'März': 'March',
            'April': 'April',    'Mai': 'May',        'Juni': 'June',
            'Juli': 'July',      'August': 'August',  'September': 'September',
            'Oktober': 'October','November': 'November','Dezember': 'December'
        }

        articles = soup.find_all('article', class_='entry')
        for article in articles:
            date_div = article.find('div', class_='entry-summary')
            event_date_raw = date_div.get_text(strip=True)
            try:
                day_name, day, month_name, year = event_date_raw.split(' ')
            except ValueError:
                continue                                   # Formatfehler → nächster Artikel

            month_name   = months.get(month_name, month_name)
            day_padded   = day.rstrip('.').zfill(2)
            month_padded = datetime.datetime.strptime(month_name, '%B').strftime('%m')
            event_date   = f"{day_name}, {day_padded}.{month_padded}.{year}"

            event_name_tag = article.find('h2', class_='entry-title')
            event_name     = f"{event_name_tag.get_text(strip=True)} (@bunkerulmenwall)"
            event_link     = article.find('a', class_='post-thumbnail')['href']

            cat_links = article.select(
                '.cat-links a, footer a[rel~=\"category\"], a[href*=\"/category/\"]'
            )
            categories = ' | '.join(c.get_text(strip=True) for c in cat_links)

            start_time = ""
            try:
                detail_html = requests.get(event_link, timeout=10).text
                detail_soup = BeautifulSoup(detail_html, "html.parser")
            
                m = re.search(
                    r"Beginn\s*(?:um|:|-)?\s*(\d{1,2}[.:]\d{2})",
                    detail_soup.get_text(" ", strip=True),
                    flags=re.I,
                )
                if m:
                    start_time = m.group(1).replace(".", ":")
                    # einstellig → führende Null, damit immer HH:MM
                    if len(start_time) == 4:
                        start_time = "0" + start_time
            
                if not start_time:
                    ld = detail_soup.find("script", type="application/ld+json")
                    if ld and ld.string:
                        data = json.loads(ld.string)
                        if isinstance(data, dict) and "startDate" in data:
                            start_time = parse(data["startDate"]).strftime("%H:%M")
            except Exception:
                pass                                      # Detailseite nicht erreichbar

            detail_soup = None                          # für Bild-Fallback

            image_url = ""
            img_tag = (
                article.select_one("a.post-thumbnail img") or
                article.select_one('img[class*="wp-post-image"]') or
                article.find("img")
            )
            if img_tag:
                src = (
                    img_tag.get("src") or
                    img_tag.get("data-src") or
                    (img_tag.get("srcset") or "").split(" ")[0]
                )
                if src:
                    image_url = urljoin(base_url, src)
            if not image_url and detail_soup:
                og = detail_soup.find("meta", property="og:image")
                if og and og.get("content"):
                    image_url = urljoin(base_url, og["content"])
                if not image_url:
                    fig_img = detail_soup.select_one("figure img")
                    if fig_img and fig_img.get("src"):
                        image_url = urljoin(base_url, fig_img["src"])

            events.append({
                'date': event_date,
                'time': start_time,      # ← jetzt korrekt gefüllt oder ''
                'category': categories,  # ← jetzt gefüllt oder ''
                'event': event_name,
                'link': event_link,
                'image_url': image_url
            })    

    if base_url == stereobielefeld:
        for event in soup.find_all('div', class_='evo_event_schema'):
            script_tag = event.find('script', type='application/ld+json')
            if not (script_tag and script_tag.string):
                continue
    
            # clean up the JSON-LD blob
            cleaned = script_tag.string.replace('\n', '').replace('\r', '').replace('\t', '')
            event_name    = re.search(r'name":\s*"(.*?)"', cleaned).group(1)
            start_date_ld = re.search(r'startDate":\s*"(.*?)"', cleaned).group(1)
            url_match     = re.search(r'url":\s*"(.*?)"', cleaned)
            url_extracted = url_match.group(1) if url_match else base_url
    
            # split date vs. time+timezone
            date_part, time_part = start_date_ld.split('T')
            year, month, day  = date_part.split('-')
            month = month.zfill(2)
            day   = day.zfill(2)
    
            # normalize the timezone offset
            tz = time_part[-6:]
            tz = tz.replace('+2:00', '+02:00').replace('-2:00', '-02:00')
            time_core = time_part[:-6]
            iso_str   = f"{year}-{month}-{day}T{time_core}{tz}".replace('+1:00', '+01:00')
    
            # parse via the module name so we don't shadow anything
            parsed_date    = datetime.datetime.fromisoformat(iso_str)
            formatted_date = parsed_date.strftime('%a, %d.%m')   # z. B. "Do, 05.06"
            formatted_time = parsed_date.strftime('%H:%M')        # z. B. "19:00"
            m_img = re.search(r'"image":\s*"([^"]+)"', cleaned)
            image_url = m_img.group(1) if m_img else None
            events.append({
                "date":      formatted_date,
                "time":      formatted_time,                      # <-- neue Uhrzeit-Spalte
                "event":     f"{event_name} (@stereobielefeld)",
                "category":  "Party",
                "link":      url_extracted,
                'image_url': image_url
            })

    if base_url == f2f:
        container = soup.find('div', class_='wpf2f-public-widget')
        if container:
            event_containers = container.find_all('a')
            for event in event_containers:
                date_text = event.find('span', class_='font-semibold text-md text-start')
                if date_text:
                    date = date_text.text.strip().split(' ab')[0].strip()
                    date = format_date2(date)
                    event_name = event['title'].split("in Bielefeld am ")[0].strip()
                    link = event['href']
                    events.append({"date": date, "event": event_name, 'link': link})
    if base_url == arminia:

        all_divs = soup.find_all("div")

        for i in range(len(all_divs) - 4):
            date_block  = all_divs[i]
            team1_block = all_divs[i + 1]
            team2_block = all_divs[i + 2]

            team1 = team1_block.get_text(strip=True)
            team2 = team2_block.get_text(strip=True)

            if team1 == "Arminia Bielefeld":
                datum_raw = date_block.get_text(separator="\n").strip()
                # e.g.: "Sa, 05.04.2025 19:00"
                datum     = datum_raw.split("\n")[-1].strip()

                if "2025" in datum:
                    # Gegner (away team)
                    gegner = team2

                    # Remove weekday prefix up to the comma
                    if "," in datum:
                        _, date_str = datum.split(",", 1)
                        date_str = date_str.strip()
                    else:
                        date_str = datum

                    # Parse via the datetime module so we don't touch the local dt name
                    datum_dt = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                    formatted = datum_dt.strftime("%a, %d.%m")
                    ld_json = date_block.find_previous("script", type="application/ld+json")
                    image_url = None
                    if ld_json and ld_json.string:
                        data = json.loads(ld_json.string)
                        image_url = data.get("image")
                    events.append({
                        "date":  formatted,
                        "event": f"Arminia vs. {gegner} (@arminiaofficial)",
                        "category": 'Sport',
                        "link":  base_url,
                        'image_url': image_url
                    })

    if base_url == hsp:
               
        BASE_URL = hsp
        INDEX_URL = urljoin(BASE_URL, "m.html")
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
    
        # 1) Index-Seite holen und Links für Mo–So extrahieren
        resp = session.get(INDEX_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
    
        wd_map = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}
        # Link-Map: z.B. {"Mo": "...", …}
        weekday_links = {
            a.get_text(strip=True)[:2]: urljoin(BASE_URL, a["href"])
            for a in soup.find_all("a", href=True)
            if "anmeldung.fcgi" in a["href"]
               and "mode=mobile" in a["href"]
               and a.get_text(strip=True)[:2] in wd_map
        }
        def extract_basename(name: str):
            for kw, rx in kw_regex.items():
                if rx.search(name):
                    return kw
            return None
    
        # Reverse-Map: aus Wochentag-Index zurück auf Abkürzung
        rev_wd = {v: k for k, v in wd_map.items()}
    
        # 2) Ab heute für 10 Tage
        today = dt.today()
        num_days = 10
    
        time_pattern = re.compile(r"\d{2}:\d{2}(?:-\d{2}:\d{2})?(?:\s?Uhr)?$")
        allowed_keywords = [
        "Laufen",         # running
        "Improtheater",   # improv theatre
        "Wandern",      # hiking
        "Fitnesstraining",   # power workout (typo preserved as requested)
        "Yoga",
        "Volleyball",
        "Tango Argentino",
        "Surf",
        "Salsa/Bachata"
        ]
        kw_regex = {k: re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE)for k in allowed_keywords}

        events = []
        seen = set()
    
        for i in range(num_days):
            date = today + timedelta(days=i)
            abbr = rev_wd[date.weekday()]        # z.B. "Sa" für Samstag
            page_url = weekday_links.get(abbr)   # Link für diesen Wochentag
            if not page_url:
                continue                         # überspringen, falls kein Link existiert
    
            r = session.get(page_url)
            if r.status_code != 200:
                continue
    
            day_soup = BeautifulSoup(r.content, "html.parser")
            date_str = date.strftime(f"{abbr}, %d.%m.%Y")
    
            for a in day_soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                tm = time_pattern.search(txt)
                if not tm:
                    continue
                timeslot = tm.group().replace(" Uhr", "")
                start_time = timeslot.split("-", 1)[0]

                raw_name = txt[: tm.start()].split(":", 1)[-1].strip()
                raw_name = re.sub(r"\b(?:Mo|Di|Mi|Do|Fr|Sa|So)$", "", raw_name).strip()
                basename = extract_basename(raw_name)
                if basename is None:
                    continue
    
                key = (date_str, timeslot, basename.lower())
                if key in seen:
                    continue
                seen.add(key)
    
                events.append(
                    {
                        "date": date_str,
                        "time": start_time,
                        "event": f"{basename}(@hochschulsport_bielefeld)",
                        "category": "Sport",
                        "link": urljoin(base_url, a["href"]),
                        'image_url': 'https://www.uni-bielefeld.de/__uuid/e4523e8b-a93a-4b4d-97ff-66c808ae7e0e/10-09-2008_Sport_Universitat_Bielefeld_(1044).jpg'
                    }
                )

    if base_url == theater:

        theater_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KreativScraper/1.0)"
        }

        MONTH_MAP = {
            "Januar":   1,  "Februar":  2,  "März":     3,
            "April":    4,  "Mai":      5,  "Juni":     6,
            "Juli":     7,  "August":   8,  "September":9,
            "Oktober": 10,  "November":11,  "Dezember":12
        }
        WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        resp = requests.get(base_url, headers=theater_headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for h4 in soup.select("h4"):
            a = h4.find("a", href=True)
            if not a:
                continue

            raw_date = ""
            for sib in h4.previous_siblings:
                txt = sib.strip() if isinstance(sib, str) else sib.get_text(strip=True)
                m = re.match(
                    rf"^({'|'.join(MONTH_MAP.keys())})\s+(\d{{1,2}}),\s+(\d{{4}})",
                    txt
                )
                if m:
                    month_name, day, year = m.groups()
                    month = MONTH_MAP[month_name]
                    day   = int(day)
                    year  = int(year)
                    # ← use dt, not datetime
                    event_dt = dt(year, month, day)
                    wd       = WEEKDAY_ABBR[event_dt.weekday()]
                    raw_date = f"{wd}, {event_dt.day:02d}.{event_dt.month:02d}"
                    break

            title = a.get_text(strip=True)
            link  = a["href"]
            if link.startswith("/"):
                link = "https://theaterlabor.eu" + link

            events.append({
                "event": f"{title}(@theaterlaborbielefeld)",
                "date":  raw_date,
                "category": 'Kultur',
                "link":  link
            })

    if base_url == impro:          # z. B.  
    # Jede Listenzeile ist bereits der Link auf die Detailseite
        event_containers = soup.select("a[href^='/event/']")
    
        for link_tag in event_containers:
            try:
                event_link = link_tag["href"]
                raw_text   = " ".join(link_tag.get_text(" ", strip=True).split())
    
                # Beispiel-String:
                # "Jun 06 2025 LAST SCENE STANDING - Du entscheidest 19:45 Falkendom, Bielefeld"
                m = re.match(
                r"^([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})\s+(.+?)\s+(\d{2}:\d{2})(?:\s*Uhr)?\s+(.+)$",
                raw_text
                    )
                
                if not m:             # Unerwartetes Format – weiter zum nächsten Eintrag
                    continue
    
                mon_str, day, year, event_name, start_time, event_location = m.groups()
    
                # ---------- Datum --------------------------------------------
                try:
                    parsed_date = dt.strptime(f"{day} {mon_str} {year}", "%d %b %Y")
                    formatted_event_date = parsed_date.strftime("%a, %d.%m.%Y")
                except ValueError:
                    formatted_event_date = f"{day}.{mon_str}.{year}"   # Fallback
    
                # ---------- Kategorie (Überschrift oberhalb der Links) ---------
                heading = link_tag.find_previous(lambda t: t.name in ("h2", "h3"))
                event_category = heading.get_text(strip=True) if heading else ""
    
                formatted_event_name = f"{event_name} (@{event_location})"
   
                description = ""
                try:
                    detail_resp = requests.get(urljoin(base_url, event_link), timeout=10)
                    detail_resp.raise_for_status()
                    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
    
                    for selector in (
                        "div.event-description", "div.text", "div.teaser",
                        "div.v-copy", "article .text"
                    ):
                        node = detail_soup.select_one(selector)
                        if node and node.get_text(strip=True):
                            description = re.sub(r"\s+", " ", node.get_text(" ")).strip()
                            break
    
                    if not description:
                        first_p = detail_soup.find("p")
                        if first_p:
                            description = re.sub(r"\s+", " ", first_p.get_text(" ")).strip()
                except Exception as ex:
                    print(f"Fehler beim Laden der Detailseite: {ex}")
    
                og = detail_soup.find("meta", property="og:image")
                image_url = urljoin(base_url, og["content"]) if og else None

                events.append({
                    "date":        formatted_event_date,
                    "time":        start_time,
                    "event":       formatted_event_name,
                    "category":    event_category,
                    "description": description,
                    "link":        urljoin(base_url, event_link),
                    'image_url': image_url
                })
    
            except Exception as ex:
                print(f"Fehler beim Verarbeiten eines Events: {ex}")


    if base_url == vhs:
        WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        # Only used in this branch
        vhs_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KreativScraper/1.0)"
        }

        base = base_url
        url  = base + "/programm"
        resp = requests.get(url, headers=vhs_headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen_links = set()

        for a in soup.select("a[href*='/programm/kurs/']"):
            raw_link = a["href"].split("#")[0]  # ohne Anker
            link = raw_link if raw_link.startswith("http") else base + raw_link
            if link in seen_links:
                continue
            seen_links.add(link)

            raw_text = a.get_text(" ", strip=True)
            if not raw_text:
                continue

            m_title = re.match(r"^(.*?)\s*Wann:", raw_text)
            title = m_title.group(1).strip() if m_title else raw_text

            date_str = ""
            try:
                r2 = requests.get(link + "#inhalt", headers=vhs_headers, timeout=10)
                r2.raise_for_status()
                doc = BeautifulSoup(r2.text, "html.parser")
                hdr = doc.find(lambda tag: tag.name in ["h2","h3"] and "Termine" in tag.get_text())
                if hdr:
                    tbl = hdr.find_next("table")
                    if tbl:
                        first_td = tbl.find("td")
                        if first_td:
                            raw = first_td.get_text(strip=True)  # z.B. "13.01.2025"
                            m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", raw)
                            if m:
                                d, mth, yr = map(int, m.groups())
                                if yr < 100:
                                    yr += 2000
                                event_dt = dt(yr, mth, d)
                                date_str = f"{WEEKDAY_ABBR[event_dt.weekday()]}, {event_dt.day:02d}.{event_dt.month:02d}"
            except Exception:
                pass

            if not date_str:
                
                m_date = re.search(
                    r"Wann:.*?(Mo|Di|Mi|Do|Fr|Sa|So)\.?\s*,\s*(\d{1,2})\.(\d{1,2})\.(\d{2})",
                    raw_text
                )
                if m_date:
                    wd_abbr, d, mth, yy = m_date.groups()
                    day, month, year = int(d), int(mth), 2000 + int(yy)
                    # again, use `dt` for the class
                    event_dt = dt(year, month, day)
                    date_str = f"{wd_abbr}, {event_dt.day:02d}.{event_dt.month:02d}"

            events.append({
                "event": f"{title}(@volkshochschule.bielefeld)",
                "date":  date_str,
                "category": 'Bildung',
                "link":  link
            })
    
    if base_url.startswith("https://rausgegangen.de/en/"):

        city_slug = base_url.rstrip("/").split("/")[-2]          # z. B. "dortmund"
        city_name = next(
            (k for k, v in RAUSGEGANGEN_CITIES.items() if v == city_slug),
            city_slug.capitalize()
        )

        UA = "Mozilla/5.0 (compatible; TRIBE-Scraper/1.0)"
        events = []                                              # Ergebnisliste

        try:
            html = requests.get(base_url, headers={"User-Agent": UA}, timeout=10).text
        except Exception as e:
            print(f"[Rausgegangen] Fehler beim Abruf ({city_name}): {e}")
            return []

        soup = BeautifulSoup(html, "html.parser")

        # -------- Links zu Einzel-Events sammeln --------
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/events/" in href:
                if href.startswith("/en/"):
                    href = "https://rausgegangen.de" + href
                elif href.startswith("/") and not href.startswith("http"):
                    href = "https://rausgegangen.de/en" + href
                links.append(href)

        links = list(dict.fromkeys(links))[:30]                  # max 30 Events

        # -------- Einzel-Events parsen --------
        for link in links:
            try:
                res = requests.get(link, headers={"User-Agent": UA}, timeout=10)
                res.raise_for_status()
                soup_ev = BeautifulSoup(res.text, "html.parser")

                ld_tag = soup_ev.find("script", type="application/ld+json")
                ld = json.loads(ld_tag.string) if ld_tag and ld_tag.string else {}

                # Titel
                title = ld.get("name") or \
                        (soup_ev.find(["h1", "h2"]).get_text(strip=True) if soup_ev.find(["h1", "h2"]) else "Unbenanntes Event")

                # Datum / Zeit
                start_iso = ld.get("startDate")
                if not start_iso:
                    continue
                date_iso = start_iso[:10]          # YYYY-MM-DD
                time_str = start_iso[11:16]        # HH:MM

                ev_date = datetime.datetime.strptime(date_iso, "%Y-%m-%d").date()
                if ev_date < TODAY:
                    continue

                # ------------- Location -------------
                location = ""
                if isinstance(ld.get("location"), dict):
                    location = (ld["location"].get("name") or "").strip()

                if not location:
                    loc_a = soup_ev.select_one("a[href*='/locations/']")
                    if loc_a:
                        location = loc_a.get_text(strip=True)

                # ------------- Kategorie -------------
                cat_tag = soup_ev.select_one("span.tag")
                category = cat_tag.get_text(strip=True) if cat_tag else ""

                # ------------- Beschreibung -------------
                description = BeautifulSoup(
                    ld.get("description", ""), "html.parser"
                ).get_text(" ").strip()

                # ------------- Bild -------------
                def clean_img_url(raw_url: Optional[str]) -> Optional[str]:
                    if not raw_url:
                        return None
                
                    parts = list(urlsplit(raw_url))         
                    safe_qs = [(k, v) for k, v in parse_qsl(parts[3]) if v.strip()]
                    parts[3] = urlencode(safe_qs, doseq=True)
                    cleaned = urlunsplit(parts)
                    return cleaned.split("?", 1)[0] if cleaned.endswith("?") else cleaned
                img_url = None
                og_tag = soup_ev.find("meta", property="og:image")
                if og_tag and og_tag.get("content"):
                    img_url = clean_img_url(og_tag["content"])
                if not img_url:
                    ld_img = ld.get("image")
                    if isinstance(ld_img, list):
                        ld_img = ld_img[0]
                    if isinstance(ld_img, dict):
                        ld_img = ld_img.get("url")
                    if isinstance(ld_img, str):
                        img_url = clean_img_url(ld_img)
                if not img_url:
                    m = re.search(r'https?://[^"\']+\.(?:jpg|jpeg|png|webp)', res.text, re.I)
                    img_url = clean_img_url(m.group(0)) if m else None

                # ------------- Event-Name -------------
                if location:
                    event_name = f"{title} (@{location})"
                else:
                    event_name = f"{title}"

                # ------------- Append -------------
                events.append({
                    "date":        ev_date.strftime("%a, %d.%m.%Y"),
                    "time":        time_str,
                    "event":       event_name,
                    "category":    category,
                    "description": description,
                    "link":        link,
                    "image_url":   img_url,
                    "city":        city_name
                })
            except Exception as e:
                print(f"Fehler bei Detail-Scrape {link}: {e}")

            
    if base_url in [movie, platzhirsch, irish_pub]:
        if base_url == movie:
            add_recurring_events(events, "Salsa Party (@movie_liveclub)", "THURSDAY", movie, 'weekly', None, '20:00', 'Party')
        elif base_url == platzhirsch:
            add_recurring_events(events, "Afterwork Party (@platzhirschbielefeld)", "THURSDAY", platzhirsch, 'weekly', None, '20:00', 'Party','https://www.bielefeld-app.de/media/processed/80EB0D40-D9E5-4CA5-91AD-21A7EBC961D6_1.jpeg')
            add_recurring_events(events, "Bingo (@platzhirschbielefeld)", "WEDNESDAY", platzhirsch, 'monthly_nth_weekday', 1, '20:00', 'Ausgehen','https://www.bielefeld-app.de/media/processed/80EB0D40-D9E5-4CA5-91AD-21A7EBC961D6_1.jpeg')
        elif base_url == irish_pub:
            add_recurring_events(events, "Pub Quiz (@irish_pub_bielefeld)", "MONDAY", irish_pub, 'weekly', None,'20:00', 'Ausgehen')
            add_recurring_events(events, "Art Night (@loom_bielefeld)", "WEDNESDAY",'https://www.loom-bielefeld.de/events/mini-artnight-e49416/', 'monthly_nth_weekday', 1, '17:00', 'Kreativität')
            add_recurring_events(events, "Karaoke (@irish_pub_bielefeld)", "WEDNESDAY", irish_pub, 'weekly', None,'21:00', 'Ausgehen')
            add_recurring_events(events, "*TRIBE TUESDAY RUN(@gellershagenpark_teich)*", "TUESDAY",
                                 'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None,'18:00','Sport')
            add_recurring_events(events, "*TRIBE POWERWORKOUT (@GELLERSHAGEN PARK TEICH)*", "MONDAY",'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==','weekly', None,'18:00','Sport')
            add_recurring_events(events, "*TRIBE BOULDERN (@Kletterhalle Senne)*", "WEDNESDAY",'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==','weekly', None,'18:00','Sport')
            add_recurring_events(events, "*TRIBE FUSSBALL (@Obersee Fussballplatz)*", "THURSDAY",'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==','weekly', None,'18:00','Sport')
            add_recurring_events(events, "*TRIBE KENNENLERNABEND*", "SUNDAY",
                                 'https://www.instagram.com/p/CnjcdapLOe7/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None,'19:00','Ausgehen')
            add_recurring_events(events, "*TRIBE WANDERSAMSTAG*", "SATURDAY", irish_pub, 'monthly_last', None, '14:00','Sport')
            add_recurring_events(events, "*TRIBE CREATIVE CIRCLES*", "FRIDAY",
                                 'https://www.instagram.com/reel/DBwDGB9IL3_/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'monthly_last', None,'19:00','Kreativität')
            add_recurring_events(events, "Lauftreff @oberseeparkrun (@Obersee)", "SATURDAY", "https://www.parkrun.com.de/", 'weekly', None, '09:00','Sport')
            add_recurring_events(events, "Lauftreff @uprunningclub (@Venue Coffee)", "SUNDAY", "https://www.instagram.com/uprunningclub/?hl=de", 'weekly', None,'09:00','Sport')
            add_recurring_events(events, "Lauftreff @apero_runners (@Luttercafe)", "THURSDAY", "https://www.instagram.com/apero_runners/?hl=de", 'weekly', None,'19:00','Sport',"https://scontent-dus1-1.cdninstagram.com/v/t51.2885-19/438862626_403374899131107_8121470992097519210_n.jpg?efg=eyJ2ZW5jb2RlX3RhZyI6InByb2ZpbGVfcGljLmRqYW5nby4xMDM3LmMyIn0&_nc_ht=scontent-dus1-1.cdninstagram.com&_nc_cat=103&_nc_oc=Q6cZ2QHUcQrauDzCYoMIDEPYrSYe85kBc7OrgBVsELXVLgFHqjVKxfWchabFl5yxG5JeRPI&_nc_ohc=xXJD1wXmVekQ7kNvwGrwK6s&_nc_gid=LdvieMPHIMzmntbW1-1odQ&edm=APoiHPcBAAAA&ccb=7-5&oh=00_AfjuW9iBlNTXK85tzmUvZC-i4pResgtv0LA4Fb_XVznVzg&oe=691B7A59&_nc_sid=22de04")
            add_recurring_events(events, "LIV/Hinterzimmer Afro (@hinterzimmer.club)", "SATURDAY", "https://www.instagram.com/liv.bielefeld/?hl=de", 'weekly', None,'23:00','Party')
            add_recurring_events(events, "LIV/Hinterzimmer Afro (@hinterzimmer.club)", "FRIDAY", "https://www.instagram.com/liv.bielefeld/?hl=de", 'weekly', None,'23:00','Party')
            add_recurring_events(events, "CUTIE DANCE(@cutiebielefeld)", "SATURDAY", "https://www.instagram.com/cutiebielefeld/?hl=de", 'weekly', None,'23:00','Party')
            add_recurring_events(events, "CUTIE DANCE (@cutiebielefeld)", "FRIDAY", "https://www.instagram.com/cutiebielefeld/?hl=de", 'weekly', None,'23:00','Party')
            add_recurring_events(events, "Afterwork (@harmsmarkt)", "THURSDAY", "https://harms-markt.de/allgemein/after-work/", 'weekly', None, '18:00','Ausgehen')
            add_recurring_events(events, "PingPong(@nr.z.p)", "THURSDAY", nrzp, 'weekly',None,'21:00','Ausgehen','https://nrzp.de/wp-content/uploads/2023/02/dein_abschnittstext.jpg')
            add_recurring_events(events, "Kneipenquiz(@gegenueber_bar)", "TUESDAY", 'https://www.instagram.com/gegenueber_bar/?hl=de', 'monthly_nth_weekday', 2, '20:00','Ausgehen')
            add_recurring_events(events, "Wochenmarkt(@Alter Markt)", "TUESDAY", 'https://www.bielefeld.jetzt/wochenmarkt', 'weekly',None, '07:00','Ausgehen','https://www.bielefeld.jetzt/sites/default/files/styles/large/public/bild/2025/Altstadtmarkt-9.jpg?itok=Ixkx10CN')
            add_recurring_events(events, "Wochenmarkt(@Siegfriedplatz)", "WEDNESDAY", 'https://www.bielefeld.jetzt/wochenmarkt', 'weekly',None, '07:00','Ausgehen','https://www.bielefeld.jetzt/sites/default/files/styles/large/public/bild/2025/Altstadtmarkt-9.jpg?itok=Ixkx10CN')
            add_recurring_events(events, "Wochenmarkt (@Brackwede)", "THURSDAY", 'https://www.bielefeld.jetzt/wochenmarkt', 'weekly',None, '07:00','Ausgehen','https://www.bielefeld.jetzt/sites/default/files/styles/large/public/bild/2025/Altstadtmarkt-9.jpg?itok=Ixkx10CN')
            add_recurring_events(events, "Wochenmarkt (@Alter Markt, Siegfriedplatz)", "FRIDAY", 'https://www.bielefeld.jetzt/wochenmarkt', 'weekly',None, '07:00','Ausgehen','https://www.bielefeld.jetzt/sites/default/files/styles/large/public/bild/2025/Altstadtmarkt-9.jpg?itok=Ixkx10CN')
            add_recurring_events(events, "Wochenmarkt (@Alter Markt)", "SATURDAY", 'https://www.bielefeld.jetzt/wochenmarkt', 'weekly',None, '07:00','Ausgehen','https://www.bielefeld.jetzt/sites/default/files/styles/large/public/bild/2025/Altstadtmarkt-9.jpg?itok=Ixkx10CN')
            add_recurring_events(events, "Sip&Sketch (@kunsthalle_bielefeld)", "FRIDAY", 'https://kunsthalle-bielefeld.de/programm/veranstaltungen/#10209', 'monthly_nth_weekday',2, '17:30','Kreativität')
            add_recurring_events(events, "Lauftreff @teilzeitläufer (@Rathaus)", "WEDNESDAY", 'https://www.instagram.com/teilzeitlaeuferbi/', 'weekly',None, '20:00','Sport')
            add_recurring_events(events, "DIES DAS COMEDY - OPEN MIC (@diesdascomedy)", "WEDNESDAY",'https://www.instagram.com/diesdascomedy/', 'monthly_nth_weekday',2,'20:00','Ausgehen',"https://img.evbuc.com/https%3A%2F%2Fcdn.evbuc.com%2Fimages%2F1149914903%2F458602689502%2F1%2Foriginal.jpg?w=940&auto=format%2Ccompress&q=75&sharp=10&rect=0%2C0%2C2160%2C1080&s=9fe71dc7482ee7b9a2010ffe02860068")
            add_recurring_events(events, "DIES DAS COMEDY - OPEN MIC (@diesdascomedy)", "WEDNESDAY",'https://www.instagram.com/diesdascomedy/', 'monthly_nth_weekday',4,'20:00','Ausgehen',"https://img.evbuc.com/https%3A%2F%2Fcdn.evbuc.com%2Fimages%2F1149914903%2F458602689502%2F1%2Foriginal.jpg?w=940&auto=format%2Ccompress&q=75&sharp=10&rect=0%2C0%2C2160%2C1080&s=9fe71dc7482ee7b9a2010ffe02860068")
    return events

def split_dates(date_string):
    date_string = date_string.strip('[]')
    day_part, date_part = date_string.split(', ')
    days = day_part.split(' + ')
    dates = date_part.split(' + ')
    return [f'{day}, {date}' for day, date in zip(days, dates)]

def split_dates2(date_string):
    date_string = date_string.strip('[]')
    day_part, date_part = date_string.split(', ')
    days = day_part.split(' – ')
    dates = date_part.split(' – ')
    return [f'{day}, {date}' for day, date in zip(days, dates)]

def format_date(date_str):
    try:
        date_str = date_str.split(' ')[0]
        if ' - ' in date_str:
            start_date_str, end_date_str = date_str.split(' - ')
            start_date = dt.strptime(start_date_str.strip(), '%d.%m.%Y')
            end_date = dt.strptime(end_date_str.strip(), '%d.%m.%Y')
            formatted_start_date = start_date.strftime('%a, %d.%m')
            formatted_end_date = end_date.strftime('%d.%m')
            return f"{formatted_start_date} - {formatted_end_date}"
        else:
            date_obj = dt.strptime(date_str.strip(), '%d.%m.%Y')
            return date_obj.strftime('%a, %d.%m')
    except ValueError:
        return date_str

def format_date2(date_str):
    input_format = "%d.%m.%y"
    output_format = "%a, %d.%m"
    try:
        date_obj = dt.strptime(date_str, input_format)
        return date_obj.strftime(output_format)
    except ValueError:
        return "Invalid date format"

def add_recurring_events(
        events: list,
        event_name: str,
        day_name: str,
        base_url: str,
        frequency: str,
        nth: Optional[int],
        event_time: str,
        category: str,
        image_url: Optional[str] = None,
) -> None:
    cal = calendar.Calendar()
    day_name_upper = day_name.upper()
    try:
        weekday_number = getattr(calendar, day_name_upper)
    except AttributeError:
        weekday_map = {"MONDAY":0, "TUESDAY":1, "WEDNESDAY":2, "THURSDAY":3, "FRIDAY":4, "SATURDAY":5, "SUNDAY":6}
        weekday_number = weekday_map.get(day_name_upper, 0)
    def add_event(month, day):
        day_abbr = day_name[:2].capitalize()
        event_date = f"{day_abbr}, {str(day).zfill(2)}.{str(month).zfill(2)}.{TARGET_YEAR}"
        events.append({
            'date': event_date,
            'time': event_time,
            'event': event_name,
            'category': category,
            'link': base_url,
            'image_url': image_url
        })
    for month in range(1, 13):
        if frequency == 'weekly':
            for day, weekday in cal.itermonthdays2(TARGET_YEAR, month):
                if day != 0 and weekday == weekday_number:
                    add_event(month, day)
        elif frequency == 'monthly_last':
            month_calendar = calendar.monthcalendar(TARGET_YEAR, month)
            last_occurrence = None
            for week in month_calendar:
                if week[weekday_number] != 0:
                    last_occurrence = week[weekday_number]
            if last_occurrence:
                add_event(month, last_occurrence)
        elif frequency == 'monthly_nth_weekday' and nth is not None:
            count = 0
            for day, weekday in cal.itermonthdays2(TARGET_YEAR, month):
                if day != 0 and weekday == weekday_number:
                    count += 1
                    if count == nth:
                        add_event(month, day)
                        break

TODAY = datetime.date.today()
_WD   = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

def parse_event_date(s: str) -> Optional[datetime.date]:
    if not s:
        return None

    s = s.split(" - ")[0].strip()

    m = re.match(r"^[A-Za-z]{2,3}\.?,\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", s)
    if m:
        d, mth, y = map(int, m.groups())
        if y < 100:                       # 25 → 2025
            y += 2000
        return datetime.date(y, mth, d)

    m = re.match(r"^[A-Za-z]{2,3}\.?,\s*(\d{1,2})\.(\d{1,2})$", s)
    if m:
        d, mth = map(int, m.groups())
        return datetime.date(TODAY.year, mth, d)

    return None

if __name__ == '__main__':
    sources = [
        platzhirsch, irish_pub, movie,
        bielefeld_jetzt, forum, f2f, sams, nrzp,
        bunker,stereobielefeld, cafe, arminia, impro, hsp,
        *[f"https://rausgegangen.de/en/{slug}/eventsbydate/" for slug in RAUSGEGANGEN_CITIES.values()]
        #vhs,theater
    ]
    events = []
    MAX_WORKERS = 25

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(scrape_events, source_url): source_url for source_url in sources}

        for future in as_completed(future_to_url):
            try:
                events_from_source = future.result()
                events.extend(events_from_source)
            except Exception:
                pass
    filtered_events = []
    for ev in events:
        ev_date = parse_event_date(ev.get("date", ""))
        if ev_date and ev_date >= TODAY:
            filtered_events.append(ev)

    filtered_events.sort(key=lambda e: parse_event_date(e["date"]))

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(filtered_events, f, indent=4, ensure_ascii=False)
