import requests
from bs4 import BeautifulSoup
import json
import re
import time

def get_roundtable_details(url):
    """
    Fetches details of a specific roundtable event from its URL.

    Args:
        url: The URL of the roundtable event page.

    Returns:
        A dictionary containing the roundtable details, or None if an error occurs.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.find('h1', class_='page-title').text.strip()
        date_time_str = soup.find('h3', class_='event-date').text.strip()

        # Extract date and time using regular expressions
        match = re.match(r"^(.*?), (.*?)$", date_time_str)
        if match:
            date = match.group(1)
            time_range = match.group(2)
        else:
            date = date_time_str
            time_range = ""


        description = ""
        description_elements = soup.find_all('div', class_='entry-content')[0].find_all('p')
        for p in description_elements:
            #exclude date/time and speaker info
            if not p.find('strong') and not p.find('em'):
                description += p.text.strip() + " "

        panelists = {}
        speaker_elements = soup.find_all('div', class_='su-accordion su-u-trim')
        for i, speaker_element in enumerate(speaker_elements):
            speaker_name = speaker_element.find('strong').text.strip()
            speaker_title = speaker_element.find('em').text.strip()

            speaker_bio_paragraphs = speaker_element.find_all('p')[1:] #skip name and title
            speaker_bio = " ".join([p.text.strip() for p in speaker_bio_paragraphs])


            panelists[f"name_{i+1}"] = speaker_name
            panelists[f"title_{i+1}"] = speaker_title
            panelists[f"description_{i+1}"] = speaker_bio

        return {
            "title": title,
            "date": date,
            "time": time_range,
            "description": description.strip(),
            "panelist": panelists
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching roundtable details from {url}: {e}")
        return None
    except AttributeError as e:
        print(f"Error parsing roundtable details from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred processing {url}: {e}")
        return None

def crawl_helixcenter_roundtables():
    """
    Crawls the Helix Center website for roundtable information from 2012 to 2024.

    Returns:
        A dictionary containing aggregated roundtable data.
    """
    base_url = "https://www.helixcenter.org/roundtables/20"
    roundtable_data = {}
    id_counter = 1

    for year in range(12, 25):
        year_url = f"{base_url}{year}/"
        print(f"Crawling {year_url}")

        try:
            response = requests.get(year_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all event links on the page
            event_links = soup.select('.entry-content ul li a')

            for link in event_links:
                event_url = link['href']
                if 'roundtables' not in event_url: #exclude links not related to roundtables
                    continue
                print(f"  Fetching details from {event_url}")

                roundtable_details = get_roundtable_details(event_url)
                if roundtable_details:
                    roundtable_data[f"id_{id_counter}"] = {
                        "id": id_counter,
                        **roundtable_details
                    }
                    id_counter += 1
                time.sleep(1)  # Be polite and add a delay between requests

        except requests.exceptions.RequestException as e:
            print(f"Error crawling {year_url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while crawling {year_url}: {e}")

    return roundtable_data

if __name__ == "__main__":
    roundtable_data = crawl_helixcenter_roundtables()

    with open("helixcenter_roundtables.json", "w") as f:
        json.dump(roundtable_data, f, indent=2)

    print("Roundtable data saved to helixcenter_roundtables.json")