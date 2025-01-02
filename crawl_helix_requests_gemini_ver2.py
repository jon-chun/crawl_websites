import requests
from bs4 import BeautifulSoup
import json
import re
import time
import string

def get_speaker_bio(name):
    """
    Fetches the bio of a speaker from their individual page, if available.

    Args:
        name: The name of the speaker.

    Returns:
        The speaker's bio as a string, or None if not found.
    """
    # Clean up the name for URL
    # Sanitize speaker names to replace spaces and punctuation with dashes
    name_for_url = name.lower().replace(" ", "-")
    for char in string.punctuation:
        name_for_url = name_for_url.replace(char, "-")
    name_for_url = re.sub(r'-+', '-', name_for_url)  # Replace multiple dashes with a single dash
    name_for_url = name_for_url.strip('-')  # Remove leading/trailing dashes

    bio_url = f"https://www.helixcenter.org/participants/{name_for_url}/"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    try:
        response = requests.get(bio_url, headers=headers)
        response.raise_for_status()

        if response.url == "https://www.helixcenter.org/": #check for redirect to homepage
            print(f"    No dedicated bio page found for {name}. Bio will be extracted from roundtable page")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Assuming bio is within the main content area, e.g., <div class="entry-content">
        bio_element = soup.find('div', class_='entry-content')
        if bio_element:
            # Extract all text, join, and strip extra whitespace
            bio = ' '.join(bio_element.stripped_strings)
            return bio

        return None

    except requests.exceptions.RequestException as e:
        print(f"    Error fetching bio for {name}: {e}")
        return None
    except Exception as e:
        print(f"    An unexpected error occurred while fetching bio for {name}: {e}")
        return None

def get_roundtable_details(url):
    """
    Fetches details of a specific roundtable event from its URL.

    Args:
        url: The URL of the roundtable event page.

    Returns:
        A dictionary containing the roundtable details, or None if an error occurs.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        if response.url == "https://www.helixcenter.org/": #check for redirect to homepage
            print(f"    Error fetching roundtable details from {url} - Page redirects to homepage")
            return None

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
            if not p.find('strong') and not p.find('em'):
                description += p.text.strip() + " "

        panelists = {}
        speaker_elements = soup.find_all('div', class_='su-accordion su-u-trim')
        for i, speaker_element in enumerate(speaker_elements):
            speaker_name = speaker_element.find('strong').text.strip()
            speaker_title = speaker_element.find('em').text.strip()

            # Fetch bio from individual page or use the one on roundtable page
            speaker_bio = get_speaker_bio(speaker_name)
            if speaker_bio is None:
                speaker_bio_paragraphs = speaker_element.find_all('p')[1:]
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
        print(f"    Error fetching roundtable details from {url}: {e}")
        return None
    except AttributeError as e:
        print(f"    Error parsing roundtable details from {url}: {e}")
        return None
    except Exception as e:
        print(f"    An unexpected error occurred processing {url}: {e}")
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

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    for year in range(12, 25):
        year_url = f"{base_url}{year}/"
        print(f"Crawling {year_url}")

        try:
            response = requests.get(year_url, headers=headers)
            response.raise_for_status()

            if response.url == "https://www.helixcenter.org/": #check for redirect to homepage
                print(f"    Error fetching roundtable details from {year_url} - Page redirects to homepage")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all event links on the page
            event_links = soup.select('.entry-content ul li a')

            for link in event_links:
                event_url = link['href']
                if 'roundtables' not in event_url:
                    continue
                print(f"  Fetching details from {event_url}")

                roundtable_details = get_roundtable_details(event_url)
                if roundtable_details:
                    roundtable_data[f"id_{id_counter}"] = {
                        "id": id_counter,
                        **roundtable_details
                    }
                    id_counter += 1
                time.sleep(1)  # Be polite and add a delay

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