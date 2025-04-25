import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
from datetime import datetime as dt
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
stereo = 'https://stereo-bielefeld.de/programm/'
cafe = "https://cafeeuropa.de/"
arminia = "https://www.arminia.de/profis/saison/arminia-spiele"
cutie = "https://www.instagram.com/cutiebielefeld/?hl=de"

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
                    event = f"{title_div.get_text(strip=True)} (@Forum)"
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
            event_title += " (@CafeEuropa)"
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
                    event_name = f"{next_link.find('span', class_='span_left').get_text(strip=True)} (@Nr.z.P.)"
                    event_link = next_link['href']
                    events.append({
                        'date': event_date,
                        'event': event_name,
                        'link': event_link
                    })
        add_recurring_events(events, "PingPong(@Nr.z.P.)", "THURSDAY", nrzp, 'weekly', None)

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
            event_date = f"{day_name}, {day}{datetime.datetime.strptime(month_name, '%B').strftime('%m')}"
            event_name_tag = article.find('h2', class_='entry-title')
            event_name = f"{event_name_tag.get_text(strip=True)} (@Bunker Ulmenwall)"
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
            event_name = f"{head_tag.get_text(strip=True)} (@SAMS)"
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

    if base_url == cutie:
        tp="cutiebielefeld"; ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        h={"User-Agent":ua,"Accept-Language":"en-US,en;q=0.9"}
        html=requests.get(f"https://www.instagram.com/{tp}/", headers=h).text
        raw=re.search(r'__additionalDataLoaded\("profilePage_.*?",\s*(\{.*?\})\);', html).group(1)
        j=json.loads(raw)
        n=j["graphql"]["user"]["edge_owner_to_timeline_media"]["edges"][0]["node"]
        c=n["edge_media_to_caption"]["edges"][0]["node"]["text"]
        dm=re.search(r"(\d{1,2}\.\d{1,2}\.)", c); em=re.search(r'(?:„|"|»)?([\w\s@()&\.-]+?)(?:“|"|«)?(?=\s|$)', c); lm=re.search(r"(https?://[^\s]+)", c)
        print({"date": dm.group(1), "event": em.group(1).strip(), "link": lm.group(1)})
        events.append({"date": dm.group(1), "event": em.group(1).strip(), "link": lm.group(1)})

    if base_url == stereo:
        for event in soup.find_all('div', class_='evo_event_schema'):
            script_tag = event.find('script', type='application/ld+json')
            if script_tag and script_tag.string:
                cleaned = script_tag.string.replace('\n', '').replace('\r', '').replace('\t', '')
                event_name = re.search(r'name": "(.*?)"', cleaned).group(1)
                start_date_str = re.search(r'startDate": "(.*?)"', cleaned).group(1)
                url_match = re.search(r'url": "(.*?)"', cleaned)
                url_extracted = url_match.group(1) if url_match else base_url
                start_date_str_parts = start_date_str.split('T')
                date_part = start_date_str_parts[0].split('-')
                time_part = start_date_str_parts[1]
                date_part[1] = date_part[1].zfill(2)
                date_part[2] = date_part[2].zfill(2)
                timezone_part = time_part[-6:]
                adjusted_timezone = timezone_part.replace('+2:00', '+02:00').replace('-2:00', '-02:00')
                formatted_date_str = f"{date_part[0]}-{date_part[1]}-{date_part[2]}T{time_part[:-6]}{adjusted_timezone}"
                formatted_date_str = formatted_date_str.replace('+1:00', '+01:00')
                parsed_date = dt.fromisoformat(formatted_date_str)
                formatted_date = parsed_date.strftime('%a, %d.%m')
                events.append({
                    "date": formatted_date,
                    "event": f"{event_name} (@Stereo)",
                    "link": url_extracted
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

                date_block = all_divs[i]
                team1_block = all_divs[i + 1]
                team2_block = all_divs[i + 2]


                team1 = team1_block.get_text(strip=True)
                team2 = team2_block.get_text(strip=True)

                if team1 == "Arminia Bielefeld":
                    datum_raw = date_block.get_text(separator="\n").strip()
                    datum = datum_raw.split("\n")[-1].strip()#
                    if "2025" in datum:
                        gegner = team2
                        datum = datum[4:].strip()
                        datum_dt = dt.strptime(datum, "%d.%m.%Y %H:%M")
                        formatted = datum_dt.strftime("%a, %d.%m")
                        events.append({
                            "date": formatted,
                            "event": f"Arminia vs. {gegner}",
                            "link": base_url
                        })


    if base_url in [movie, platzhirsch, irish_pub]:
        if base_url == movie:
            add_recurring_events(events, "Salsa Party (@Movie)", "THURSDAY", movie, 'weekly', None)
        elif base_url == platzhirsch:
            add_recurring_events(events, "Afterwork Party (@Platzhirsch)", "THURSDAY", platzhirsch, 'weekly', None)
        elif base_url == irish_pub:
            add_recurring_events(events, "Pub Quiz (@Irish Pub)", "MONDAY", irish_pub, 'weekly', None)
            add_recurring_events(events, "Art Night (@Loom)", "WEDNESDAY",'https://www.loom-bielefeld.de/events/mini-artnight-e49416/', 'weekly', None)
            add_recurring_events(events, "Karaoke (@Irish Pub)", "WEDNESDAY", irish_pub, 'weekly', None)
            add_recurring_events(events, "*TRIBE TUESDAY RUN(@GELLERSHAGEN PARK TEICH)*", "TUESDAY",
                                 'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None)
            add_recurring_events(events, "*TRIBE POWERWORKOUT (@GELLERSHAGEN PARK TEICH)*", "THURSDAY",
                                 'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'weekly', None)
            add_recurring_events(events, "*TRIBE KENNENLERNABEND*", "SUNDAY",
                                 'https://www.instagram.com/p/CnjcdapLOe7/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'monthly_last', None)
            add_recurring_events(events, "*TRIBE WANDERSONNTAG*", "SUNDAY", irish_pub, 'monthly_nth_weekday', 2)
            add_recurring_events(events, "*TRIBE CREATIVE CIRCLES*", "FRIDAY",
                                 'https://www.instagram.com/reel/DBwDGB9IL3_/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
                                 'monthly_last', None)
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
        bunker, stereo, cafe, arminia, cutie
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
