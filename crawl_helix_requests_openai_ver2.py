import requests
from bs4 import BeautifulSoup
import json
import re

def crawl_helixcenter_roundtables():
    """
    Crawl Helix Center roundtable pages from 2012 to 2024 and extract event details:
        - Title
        - Date/Time
        - Full Paragraph Description
        - Full list of speakers with titles and bios
    Return a list of dictionaries, each containing data for one roundtable.
    """
    
    base_url = "https://www.helixcenter.org/roundtables/"
    start_year = 2012
    end_year = 2024
    
    all_roundtables = []
    current_id = 0  # We can increment this as we parse each event
    
    # Add custom headers to reduce chance of 406 error
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    for year in range(start_year, end_year + 1):
        # Construct the year-specific URL
        url = f"{base_url}{year}/"
        
        print(f"DEBUG: Attempting to crawl roundtables for year: {year} at URL: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            status_code = response.status_code
            
            print(f"DEBUG: Received response code {status_code} for {url}")
            if status_code != 200:
                print(f"Skipping {url}, status code: {status_code}")
                continue
            
        except requests.exceptions.RequestException as e:
            print(f"Request error for {url}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Attempt to locate the event listing (the site structure may vary by year).
        # Adjust selectors if necessary.
        # For instance, Helix Center might label them as <article class="roundtable"> or <div class="roundtable">
        events = soup.find_all("article", class_="roundtable")
        if not events:
            events = soup.find_all("div", class_="roundtable")
        
        print(f"DEBUG: Found {len(events)} roundtable items for year {year}")
        
        for event in events:
            # Extract link to the roundtable detail page
            a_tag = event.find("a")
            if not a_tag:
                continue
            roundtable_link = a_tag.get("href")
            
            # Now visit the detail page
            if roundtable_link:
                print(f"DEBUG: Crawling data from detail page: {roundtable_link}")
                roundtable_data = crawl_roundtable_detail(roundtable_link, headers)
                if roundtable_data:
                    current_id += 1
                    roundtable_data["id"] = current_id
                    all_roundtables.append(roundtable_data)
                else:
                    print(f"DEBUG: No data returned for roundtable link: {roundtable_link}")
    
    return all_roundtables

def crawl_roundtable_detail(url, headers):
    """
    Given a roundtable detail page URL, extract:
        - title
        - date
        - time
        - description
        - panelists (name, title, bio)
    Return a dictionary following the specified structure.
    """
    try:
        response = requests.get(url, headers=headers)
        status_code = response.status_code
        print(f"DEBUG: Detail page response code for {url}: {status_code}")
        if status_code != 200:
            print(f"DEBUG: Skipping detail page {url} due to status code {status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Request exception for {url}: {e}")
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Initialize the data structure
    roundtable_info = {
        "id": None,
        "title": "",
        "date": "",
        "time": "",
        "description": "",
        "panelist": {}
    }
    
    # 1) Title
    title_tag = soup.find("h1", class_="entry-title")
    if title_tag:
        roundtable_info["title"] = title_tag.get_text(strip=True)
        print(f"DEBUG: Extracted title: {roundtable_info['title']}")
    
    # 2) Date & Time
    # Often the date/time is in a <div class="roundtable-time"> or similar container
    date_time_tag = soup.find("div", class_="roundtable-time")
    if date_time_tag:
        date_time_text = date_time_tag.get_text(strip=True)
        print(f"DEBUG: Raw date/time string found: {date_time_text}")
        # Attempt simplistic parse
        parts = date_time_text.split(", ")
        if len(parts) >= 4:
            # Typically: "Saturday, May 5th, 2012, 4:30 - 6:30PM"
            day_of_week = parts[0]
            month_day = parts[1]
            year = parts[2]
            time_part = ", ".join(parts[3:])
            
            roundtable_info["date"] = f"{day_of_week}, {month_day}, {year}"
            roundtable_info["time"] = time_part
            print(f"DEBUG: Extracted date: {roundtable_info['date']} and time: {roundtable_info['time']}")
        else:
            # If parsing fails, store the entire text in 'date'
            roundtable_info["date"] = date_time_text
            print(f"DEBUG: Could not split date/time. Stored in 'date': {date_time_text}")
    
    # 3) Description
    # The main description might be in a <div class="roundtable-description"> or inside <div class="entry-content">
    description_tag = soup.find("div", class_="entry-content")
    if description_tag:
        paragraphs = description_tag.find_all("p", recursive=False)
        full_description = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        roundtable_info["description"] = full_description
        print(f"DEBUG: Extracted description: {roundtable_info['description']}")
    
    # 4) Panelists (names, titles, and bios)
    # The site might list speakers in a <section class="speakers"> or <div class="speakers">
    panelist_container = soup.find("section", class_="speakers")
    if not panelist_container:
        panelist_container = soup.find("div", class_="speakers")
    
    if panelist_container:
        speakers = panelist_container.find_all("article", class_="speaker")
        if not speakers:
            speakers = panelist_container.find_all("div", class_="speaker")
        
        print(f"DEBUG: Found {len(speakers)} speaker entries")
        
        # Iterate through each speaker
        for idx, speaker in enumerate(speakers, start=1):
            name_tag = speaker.find(["h3", "h4", "span"], class_=re.compile("name|speaker-name"))
            speaker_name = name_tag.get_text(strip=True) if name_tag else ""
            
            title_tag = speaker.find(["p", "div"], class_=re.compile("title|speaker-title"))
            speaker_title = title_tag.get_text(strip=True) if title_tag else ""
            
            bio_tag = speaker.find(["p", "div"], class_=re.compile("bio|speaker-bio"))
            speaker_bio = ""
            if bio_tag:
                speaker_bio = bio_tag.get_text(strip=True)
            else:
                bio_paras = speaker.find_all("p")
                speaker_bio = " ".join([para.get_text(strip=True) for para in bio_paras])
            
            roundtable_info["panelist"][f"name_{idx}"] = speaker_name
            roundtable_info["panelist"][f"title_{idx}"] = speaker_title
            roundtable_info["panelist"][f"description_{idx}"] = speaker_bio
            
            print(f"DEBUG: Speaker {idx}:")
            print(f"       Name: {speaker_name}")
            print(f"       Title: {speaker_title}")
            print(f"       Bio: {speaker_bio}")
    else:
        print("DEBUG: No panelist container found.")
    
    return roundtable_info

if __name__ == "__main__":
    # Crawl and collect data
    data = crawl_helixcenter_roundtables()
    
    # Save to JSON file with the new name:
    output_filename = "helixcenter_openai_ver2.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nCrawling complete. Data saved to {output_filename}")
