import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
from datetime import datetime as dt, timedelta
from urllib.parse import urljoin
import calendar
import traceback

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

    if base_url == bielefeld_jetzt:
        event_containers = soup.find_all('div', class_='veranstaltung')
        for event_container in event_containers:
            try:
                event_link = event_container.find('a', class_='box-item')['href']
                event_name = event_container.find('h3').get_text(strip=True)
                p_tags = event_container.find_all('p')
                if len(p_tags) >= 3:
                    raw_event_date = p_tags[1].get_text(strip=True)
                    event_location = p_tags[2].get_text(strip=True)
                    formatted_event_date = format_date(raw_event_date)
                    formatted_event_name = f"{event_name} (@{event_location})"

                    # Filter: Ausschließen bestimmter Veranstaltungsorte
                    if not any(substring in event_location for substring in [
                        "Nr. z. P", "Bunker Ulmenwall", "Forum",
                        "Johanneskirche Quelle (ev.)",
                        "Zionskirche Bethel (ev.)",
                        "Altstädter Nicolaikirche (ev.)",
                        "Peterskirche Kirchdornberg (ev.)",
                        "Johanniskirche (ev.)",
                        "Peter-und-Pauls-Kirche Heepen (ev.)",
                        "Neustädter Marienkirche (ev.)", "Kirche Brake (ev.)",
                        "Haus der Kirche", "Capella Hospitalis",
                        "Thomaskirche Schildesche (ev.)", "Eckardtsheim",
                        "Ev.-Luth. Bartholomäus-Kirchengemeinde Bielefeld-Brackwede",
                        "Bartholomäuskirche Brackwede (ev.-luth.)",
                        "St. Jodokus-Kirche (kath.)","Theaterwerkstatt Bethel","Pappelkrug","Marienkirche Jöllenbeck (ev.)",
                        "Haus Wellensiek","Neue Schmiede","Movement-Theater","Musik- und Kunstschule","Bielefeld-Schildesche",
                        "Kreuzkirche Sennestadt (ev.)","Museum Peter August Böckstiegel","Bielefeld-Gadderbaum",
                        "Süsterkirche (ev.-ref.)","Ev. Kirche Ummeln"



                    ]):
                        events.append({
                            'date': formatted_event_date,
                            'event': formatted_event_name,
                            'link': urljoin(base_url, event_link)
                        })
            except Exception as e:
                print(f"Fehler bei bielefeld.jetzt: {e}")
                continue

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
                    events.append({
                        'date': date,
                        'event': event,
                        'link': full_link
                    })

    if base_url == cafe:
        MONTHS = {
            "Januar": "01",
            "Februar": "02",
            "März": "03",
            "April": "04",
            "Mai": "05",
            "Juni": "06",
            "Juli": "07",
            "August": "08",
            "September": "09",
            "Oktober": "10",
            "November": "11",
            "Dezember": "12"
        }
        ticket_links = soup.find_all('a', string=lambda s: s and "Tickets kaufen" in s)
        for link in ticket_links:
            title_elem = link.find_previous(lambda tag: tag.name in ['h2', 'h3', 'h4'] and "•" in tag.get_text())
            if not title_elem:
                continue
            event_title = title_elem.get_text(strip=True)
            prev_text = title_elem.find_previous(string=re.compile(r'\d{1,2}\.\s*[A-Za-zäöüÄÖÜ]+'))
            if prev_text:
                date_text = prev_text.strip()
            else:
                continue
            m = re.search(r'(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)', date_text)
            if m:
                day = m.group(1)
                month_name = m.group(2)
                month_number = MONTHS.get(month_name, "00")
            else:
                continue
            now = datetime.datetime.now()
            candidate_date = datetime.datetime(TARGET_YEAR, int(month_number), int(day))
            if candidate_date.date() < datetime.date(TARGET_YEAR, 1, 1):
                event_year = TARGET_YEAR + 1
            else:
                event_year = TARGET_YEAR
            event_date = datetime.datetime(event_year, int(month_number), int(day))
            adjusted_date = event_date - datetime.timedelta(days=1)
            weekday_candidate = adjusted_date.strftime("%a")
            weekday_map = {
                "Mon": "Mo",
                "Tue": "Di",
                "Wed": "Mi",
                "Thu": "Do",
                "Fri": "Fr",
                "Sat": "Sa",
                "Sun": "So"
            }
            weekday_candidate = weekday_map.get(weekday_candidate, weekday_candidate)
            date_str = f"{weekday_candidate}, {adjusted_date.day:02d}.{adjusted_date.month:02d}"
            full_link = urljoin(base_url, link.get('href'))
            event_title += " (@cafe_europa_bi)"
            events.append({
                "date": date_str,
                "event": event_title,
                "link": full_link
            })

    if base_url == nrzp:
        articles = soup.find_all('div', class_='eventcalender-row')
        for article in articles:
            date_div = article.find('div', class_='eventcalender-date')
            event_date = date_div.get_text(strip=True)
            match = re.match(r'(\w{2})\. (\d{2}) (\d{2})', event_date)
            if match:
                day_name, day, month = match.groups()
                event_date = f"{day_name}, {day}.{month}"
                next_link = article.find_next_sibling('a', class_='menu_btn')
                if next_link:
                    event_name = f"{next_link.find('span', class_='span_left').get_text(strip=True)} (@nr.z.p)"
                    event_link = next_link['href']
                    events.append({
                        'date': event_date,
                        'event': event_name,
                        'link': event_link
                    })
        add_recurring_events(events, "PingPong(@nr.z.p)", "THURSDAY", nrzp, 'weekly', None)

    if base_url == bunker:
        months = {
            'Januar': 'January',
            'Februar': 'February',
            'März': 'March',
            'April': 'April',
            'Mai': 'May',
            'Juni': 'June',
            'Juli': 'July',
            'August': 'August',
            'September': 'September',
            'Oktober': 'October',
            'November': 'November',
            'Dezember': 'December'
        }
        articles = soup.find_all('article', class_='entry')
        for article in articles:
            date_div = article.find('div', class_='entry-summary')
            event_date = date_div.get_text(strip=True)
            try:
                day_name, day, month_name, year = event_date.split(' ')
            except Exception:
                continue
            month_name = months.get(month_name, month_name)
            day_padded   = day.rstrip('.').zfill(2)           
            month_padded = datetime.datetime.strptime(month_name, '%B').strftime('%m')  # "05"
            event_date = f"{day_name}, {day_padded}.{month_padded}"
            #event_date = f"{day_name}, {day}{datetime.datetime.strptime(month_name, '%B').strftime('%m')}"
            event_name_tag = article.find('h2', class_='entry-title')
            event_name = f"{event_name_tag.get_text(strip=True)} (@bunkerulmenwall)"
            event_link_tag = article.find('a', class_='post-thumbnail')
            event_link = event_link_tag['href']
            events.append({
                'date': event_date,
                'event': event_name,
                'link': event_link
            })

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
                    date_obj = datetime.datetime.strptime(start_date, '%d.%m.%Y %H:%M')
                    formatted_date = date_obj.strftime('%a, %d.%m')
            events.append({
                'date': formatted_date,
                'event': event_name,
                'link': event_link
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
            year, month, day    = date_part.split('-')
            month = month.zfill(2)
            day   = day.zfill(2)

            # normalize the timezone offset
            tz = time_part[-6:]
            tz = tz.replace('+2:00', '+02:00').replace('-2:00', '-02:00')
            time_core = time_part[:-6]
            iso_str   = f"{year}-{month}-{day}T{time_core}{tz}".replace('+1:00', '+01:00')

            # parse via the module name so we don't shadow anything
            parsed_date   = datetime.datetime.fromisoformat(iso_str)
            formatted_date = parsed_date.strftime('%a, %d.%m')

            events.append({
                "date":  formatted_date,
                "event": f"{event_name} (@stereobielefeld)",
                "link":  url_extracted
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

                    events.append({
                        "date":  formatted,
                        "event": f"Arminia vs. {gegner} (@arminiaofficial)",
                        "link":  base_url
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
    
        # Reverse-Map: aus Wochentag-Index zurück auf Abkürzung
        rev_wd = {v: k for k, v in wd_map.items()}
    
        # 2) Ab heute für 10 Tage
        today = dt.today()
        num_days = 10
    
        time_pattern = re.compile(r"\d{2}:\d{2}-\d{2}:\d{2}$")
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
                if not time_pattern.search(txt):
                    continue
    
                # Event-Name extrahieren
                name = txt.split(":", 1)[1].rsplit(" ", 2)[0].strip()
                key = (date_str, name)
                if key in seen:
                    continue
                seen.add(key)
    
                events.append({
                    "date": date_str,
                    "event": f"{name}(@hochschulsport_bielefeld)",
                    "link": urljoin(BASE_URL, a["href"])
                })

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
                "link":  link
            })


    if base_url == vhs:
        # German weekday abbreviations for strftime-like lookup
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

        # Wir selektieren nur Kurs-Links, die '/programm/kurs/' enthalten
        for a in soup.select("a[href*='/programm/kurs/']"):
            raw_link = a["href"].split("#")[0]  # ohne Anker
            link = raw_link if raw_link.startswith("http") else base + raw_link
            if link in seen_links:
                continue
            seen_links.add(link)

            raw_text = a.get_text(" ", strip=True)
            if not raw_text:
                continue

            # 1) Titel extrahieren (alles vor 'Wann:')
            m_title = re.match(r"^(.*?)\s*Wann:", raw_text)
            title = m_title.group(1).strip() if m_title else raw_text

            # 2) Datum versuchen aus Detailseite
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
                                # use `dt` (the datetime class), not the module
                                event_dt = dt(yr, mth, d)
                                date_str = f"{WEEKDAY_ABBR[event_dt.weekday()]}, {event_dt.day:02d}.{event_dt.month:02d}"
            except Exception:
                pass

            # 3) Fallback: Datum per Regex aus raw_text
            if not date_str:
                # Muster: "Wann: ab Mo. , 13.01.25, 17.30 Uhr"
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
                "link":  link
            })


    if base_url in [movie, platzhirsch, irish_pub]:
        if base_url == movie:
            add_recurring_events(events, "Salsa Party (@movie_liveclub)", "THURSDAY", movie, 'weekly', None)
        elif base_url == platzhirsch:
            add_recurring_events(events, "Afterwork Party (@platzhirschbielefeld)", "THURSDAY", platzhirsch, 'weekly', None)
        elif base_url == irish_pub:
            add_recurring_events(events, "Pub Quiz (@irish_pub_bielefeld)", "MONDAY", irish_pub, 'weekly', None)
            add_recurring_events(events, "Art Night (@loom_bielefeld)", "WEDNESDAY",'https://www.loom-bielefeld.de/events/mini-artnight-e49416/', 'monthly_nth_weekday', 1)
            add_recurring_events(events, "Karaoke (@irish_pub_bielefeld)", "WEDNESDAY", irish_pub, 'weekly', None)
            add_recurring_events(events, "*TRIBE TUESDAY RUN(@GELLERSHAGEN PARK TEICH)*", "TUESDAY",
                                 'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None)
            add_recurring_events(events, "*TRIBE POWERWORKOUT (@GELLERSHAGEN PARK TEICH)*", "THURSDAY",
                                 'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None)
            add_recurring_events(events, "*TRIBE KENNENLERNABEND*", "SUNDAY",
                                 'https://www.instagram.com/p/CnjcdapLOe7/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None)
            add_recurring_events(events, "*TRIBE WANDERSAMSTAG*", "SATURDAY", irish_pub, 'monthly_last', None)
            add_recurring_events(events, "*TRIBE CREATIVE CIRCLES*", "FRIDAY",
                                 'https://www.instagram.com/reel/DBwDGB9IL3_/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'monthly_last', None)
            add_recurring_events(events, "Park Run (@Obersee)", "SATURDAY", "https://www.parkrun.com.de/", 'weekly', None)
            add_recurring_events(events, "Up Runnning Club (@Venue Coffee)", "SUNDAY", "https://www.instagram.com/uprunningclub/?hl=de", 'weekly', None)
            add_recurring_events(events, "LIV/Hinterzimmer Afro (@hinterzimmer.club)", "SATURDAY", "https://www.instagram.com", 'weekly', None)
            add_recurring_events(events, "LIV/Hinterzimmer Afro (@hinterzimmer.club)", "FRIDAY", "https://www.instagram.com", 'weekly', None)
    return events
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

def add_recurring_events(events, event_name, day_name, base_url, frequency, nth):
    cal = calendar.Calendar()
    day_name_upper = day_name.upper()
    try:
        weekday_number = getattr(calendar, day_name_upper)
    except AttributeError:
        weekday_map = {"MONDAY":0, "TUESDAY":1, "WEDNESDAY":2, "THURSDAY":3, "FRIDAY":4, "SATURDAY":5, "SUNDAY":6}
        weekday_number = weekday_map.get(day_name_upper, 0)
    def add_event(month, day):
        day_abbr = day_name[:2].capitalize()
        event_date = f"{day_abbr}, {str(day).zfill(2)}.{str(month).zfill(2)}"
        events.append({
            'date': event_date,
            'event': event_name,
            'link': base_url
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

if __name__ == '__main__':
    sources = [
        bielefeld_jetzt, forum, platzhirsch, irish_pub, f2f, sams, movie, nrzp,
        bunker, stereobielefeld, cafe, arminia
        #hsp, vhs,theater
    ]
    events = []
    for source in sources:
        try:
            events.extend(scrape_events(source))
        except Exception as e:
            print(f"Fehler beim Verarbeiten der Quelle {source}: {e}")
            traceback.print_exc()
    with open('events.json', 'w', encoding='utf-8') as file:
        json.dump(events, file, indent=4, ensure_ascii=False)
