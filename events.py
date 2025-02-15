import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
from datetime import datetime as dt
from urllib.parse import urljoin
import calendar
import traceback
import re
import requests

current_month = '02'
#datetime.datetime.now().strftime('%m'))
bielefeld_guide = 'https://www.bielefeld-guide.de/events/weekend-guide/'
bielefeld_jetzt = 'https://www.bielefeld.jetzt/termine/suche?dateFrom=2025-02-01&dateTo=2025-02-28&rubrik%5B0%5D=k24&rubrik%5B1%5D=k246&rubrik%5B2%5D=k215&ort=0&stadtbezirk=0&freitext='
forum = 'https://forum-bielefeld.com/category/veranstaltungen/'
nrzp = 'https://nrzp.de/programm/'
bunker = 'https://bunker-ulmenwall.org/category/programm/'
sams = 'https://www.club-sams.de/'
movie = 'https://www.movie-bielefeld.de/'
platzhirsch = 'https://www.facebook.com/search/top?q=platzhirsch'
irish_pub = 'https://www.irishpub-bielefeld.de/'
f2f = 'https://face-to-face-dating.de/bielefeld'
stereo = 'https://stereo-bielefeld.de/programm/'
cafe= "https://cafeeuropa.de/"



def scrape_events(base_url):
    events = []

    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    if (base_url == bielefeld_guide):
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            text = link.get_text()
            full_link = urljoin(base_url, href)

            date_match = re.search(r'\[(.*?)\]', text)
            if date_match:
                date = date_match.group(1)
                event = text.split('] ')[1].strip()

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
            event_link = event_container.find('a', class_='box-item')['href']
            event_name = event_container.find('h3').get_text(strip=True)
            p_tags = event_container.find_all('p')

            if len(p_tags) >= 3:
                raw_event_date = p_tags[1].get_text(strip=True)
                event_location = p_tags[2].get_text(strip=True)
                formatted_event_date = format_date(raw_event_date)
                formatted_event_name = f"{event_name} (@{event_location})"

                if not any(substring in event_location for substring in [
                        "Nr. z. P",
                        "Bunker Ulmenwall",
                        "Forum",
                        "Johanneskirche Quelle (ev.)",
                        "Zionskirche Bethel (ev.)",
                        "Altstädter Nicolaikirche (ev.)",
                        "Peterskirche Kirchdornberg (ev.)",
                        "Johanniskirche (ev.)",
                        "Peter-und-Pauls-Kirche Heepen (ev.)",
                        "Neustädter Marienkirche (ev.)",
                        "Kirche Brake (ev.)",
                        "Haus der Kirche",
                        "Capella Hospitalis",
                        "Thomaskirche Schildesche (ev.)",
                        "Eckardtsheim","Ev.-Luth. Bartholomäus-Kirchengemeinde Bielefeld-Brackwede",
                        "Bartholomäuskirche Brackwede (ev.-luth.)",
"St. Jodokus-Kirche (kath.)"
                ]):
                    events.append({
                        'date': formatted_event_date,
                        'event': formatted_event_name,
                        'link': urljoin(base_url, event_link)
                    })

    if (base_url == forum):
        articles = soup.find_all('article', class_='post')
        for article in articles:
            date_div = article.find('div', class_='forumevent_date')
            if date_div:
                day = date_div.find('span', class_='day').text
                month_name = date_div.find('span', class_='month').text
                month_number = datetime.datetime.strptime(month_name,
                                                          '%b').strftime('%m')
                dayname = date_div.find('span', class_='dayname').text[:2]

                if month_number == current_month:
                    date = f"{dayname}, {day}.{month_number}"

                    title_div = article.find('div', class_='entry-title')
                    if title_div:
                        event = f"{title_div.get_text(strip=True)} (@Forum)"
                        full_link = urljoin(base_url,
                                            title_div.find('a')['href'])
                        events.append({
                            'date': date,
                            'event': event,
                            'link': full_link
                        })
    if base_url == nrzp:
        articles = soup.find_all('div', class_='eventcalender-row')

        for article in articles:
            date_div = article.find('div', class_='eventcalender-date')
            event_date = date_div.get_text(strip=True)

            match = re.match(r'(\w{2})\. (\d{2}) (\d{2})', event_date)
            if match:

                day_name, day, month = match.groups()
                if month == current_month:
                    event_date = f"{day_name}, {day}.{month}"

                    next_link = article.find_next_sibling('a',
                                                          class_='menu_btn')
                    if next_link:
                        event_name = f"{next_link.find('span', class_='span_left').get_text(strip=True)} (@Nr.z.P.)"
                        event_link = next_link['href']
                        events.append({
                            'date': event_date,
                            'event': event_name,
                            'link': event_link
                        })
        add_recurring_events(events, "PingPong(@Nr.z.P.)", "THURSDAY", nrzp,
                             'weekly', None)

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
            day_name, day, month_name, year = event_date.split(' ')
            month_name = months[month_name]
            month_number = datetime.datetime.strptime(month_name,
                                                      '%B').strftime('%m')
            event_date = f"{day_name}, {day}{month_number}"
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
                    date_obj = datetime.datetime.strptime(
                        start_date, '%d.%m.%Y %H:%M')
                    formatted_date = date_obj.strftime('%a, %d.%m')

            events.append({
                'date': formatted_date,
                'event': event_name,
                'link': event_link
            })
    if base_url == stereo:

        for event in soup.find_all('div', class_='evo_event_schema'):
            script_tag = event.find('script', type='application/ld+json')
            if script_tag and script_tag.string:
                cleaned = script_tag.string.replace('\n', '').replace(
                    '\r', '').replace('\t', '')
                event_name = re.search(r'name": "(.*?)"', cleaned).group(1)
                start_date_str = re.search(r'startDate": "(.*?)"',
                                           cleaned).group(1)
                url = re.search(r'url": "(.*?)"', cleaned).group(1)

                start_date_str_parts = start_date_str.split('T')
                date_part = start_date_str_parts[0].split('-')
                time_part = start_date_str_parts[1]

                # Füge führende Nullen hinzu
                date_part[1] = date_part[1].zfill(2)  # Monat
                date_part[2] = date_part[2].zfill(2)  # Tag

                # Korrigiere die Zeitzone von '+2:00' nach '+02:00'
                timezone_part = time_part[-6:]  # Zieht '+2:00' ab
                adjusted_timezone = timezone_part.replace(
                    '+2:00', '+02:00').replace('-2:00', '-02:00')
                formatted_date_str = f"{date_part[0]}-{date_part[1]}-{date_part[2]}T{time_part[:-6]}{adjusted_timezone}"

                formatted_date_str = formatted_date_str.replace(
                    '+1:00', '+01:00')
                # Umwandeln und formatieren

                parsed_date = dt.fromisoformat(formatted_date_str)
                formatted_date = parsed_date.strftime('%a, %d.%m')

                # Event zur Liste hinzufügen
                events.append({
                    "date": formatted_date,
                    "event": f"{event_name} (@Stereo)",
                    "link": url
                })

    if (base_url == f2f):

        container = soup.find('div', class_='wpf2f-public-widget')
        event_containers = container.find_all('a')

        events = []
        for event in event_containers:
            date = event.find(
                'span',
                class_='font-semibold text-md text-start').text.strip()
            date = date.split(' ab')[0].strip()
            date = format_date2(date)
            event_name = event['title'].split("in Bielefeld am ")[0].strip()
            link = event['href']

            events.append({"date": date, "event": event_name, 'link': link})

    if base_url == movie:
        add_recurring_events(events, "Salsa Party (@Movie)", "THURSDAY", movie,
                             'weekly', None)
    if base_url == platzhirsch:
        add_recurring_events(events, "Afterwork Party (@Platzhirsch)",
                             "THURSDAY", platzhirsch, 'weekly', None)
    if base_url == irish_pub:
        add_recurring_events(events, "Pub Quiz (@Irish Pub)", "MONDAY",
                             irish_pub, 'weekly', None)
        add_recurring_events(events, "Karaoke (@Irish Pub)", "WEDNESDAY",
                             irish_pub, 'weekly', None)
        add_recurring_events(
            events, "*TRIBE TUESDAY RUN(@GELLERSHAGEN PARK)*", "TUESDAY",
            'https://www.instagram.com/p/C__Hi7qoFmn/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
            'weekly', None)
        add_recurring_events(
            events, "*TRIBE KENNENLERNABEND*", "SUNDAY",
            'https://www.instagram.com/p/CnjcdapLOe7/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
            'monthly_last', None)
        add_recurring_events(events, "*TRIBE WANDERSONNTAG*", "SUNDAY",
                             irish_pub, 'monthly_nth_weekday', 2)
        add_recurring_events(
            events, "*TRIBE CREATIVE CIRCLES*", "FRIDAY",
            'https://www.instagram.com/reel/DBwDGB9IL3_/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==',
            'monthly_last', None)

    return events


def split_dates(date_string):
    date_string = date_string.strip('[]')
    day_part, date_part = date_string.split(', ')
    days = day_part.split(' + ')
    dates = date_part.split(' + ')
    dates[0] += current_month

    return [f'{day}, {date}' for day, date in zip(days, dates)]


def format_date(date_str):
    try:
        # Remove the time part if present
        date_str = date_str.split(' ')[0]

        # Check if date_str contains a date range
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


def split_dates2(date_string):
    date_string = date_string.strip('[]')
    day_part, date_part = date_string.split(', ')

    days = day_part.split(' – ')
    dates = date_part.split(' – ')
    dates[0] += current_month
    return [f'{day}, {date}' for day, date in zip(days, dates)]


def format_date2(date_str):

    input_format = "%d.%m.%y"  # For example: "20.09.24"

    output_format = "%a, %d.%m"  # For example: "Tu, 10.09"

    try:
        date_obj = dt.strptime(date_str, input_format)

        return date_obj.strftime(output_format)
    except ValueError:
        return "Invalid date format"


def add_recurring_events(events, event_name, day_name, base_url, frequency,
                         nth):
    now = datetime.datetime.now()
    year = now.year
    month = int(current_month)

    day_name_upper = day_name.upper()
    weekday_number = getattr(calendar, day_name_upper)
    cal = calendar.Calendar()

    def add_event(day):

        day_abbr = day_name[:2].capitalize()
        event_date = f"{day_abbr}, {str(day).zfill(2)}.{str(month).zfill(2)}"
        events.append({
            'date': event_date,
            'event': event_name,
            'link': base_url
        })

    if frequency == 'weekly':
        # Find all occurrences of the specified weekday in the current month
        for day, weekday in cal.itermonthdays2(year, month):
            if day != 0 and weekday == weekday_number:
                add_event(day)

    elif frequency == 'monthly_last':
        # Find the last occurrence of the specified weekday in the current month
        last_day_of_month = max(
            week[weekday_number]
            for week in calendar.monthcalendar(year, month)
            if week[weekday_number] != 0)
        add_event(last_day_of_month)

    elif frequency == 'monthly_nth_weekday' and nth is not None:
        # Add event on the nth occurrence of the specified weekday in the current month
        count = 0
        for day, weekday in cal.itermonthdays2(year, month):
            if day != 0 and weekday == weekday_number:
                count += 1
                if count == nth:
                    add_event(day)
                    break


def add_new_events(events, event_date, event_name, base_url):
    events.append({
        'date': event_date,
        'event': event_name,
        'link': base_url,
    })


if __name__ == '__main__':
    events = scrape_events(bielefeld_jetzt) + scrape_events(
        forum) + scrape_events(platzhirsch) + scrape_events(
            irish_pub) + scrape_events(f2f) + scrape_events(
                sams) + scrape_events(movie) + scrape_events(
                    nrzp) + scrape_events(bunker) + scrape_events(stereo)
    #scrape_events(bielefeld_guide)

    # +
    with open('events.json', 'w') as file:
        json.dump(events, file, indent=4)


    
    
