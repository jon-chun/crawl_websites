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
    
    for year in range(start_year, end_year + 1):
        # Construct the year-specific URL
        url = f"{base_url}{year}/"
        
        try:
            response = requests.get(url)
            # If there's no valid page or some years are missing, skip gracefully
            if response.status_code != 200:
                print(f"Skipping {url}, status code: {response.status_code}")
                continue
        except requests.exceptions.RequestException as e:
            print(f"Request error for {url}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Each roundtable is typically enclosed within HTML elements.
        # This might differ across years, so adjust the selectors as needed.
        # Commonly, roundtables appear as <article> or <div> with a class like 'event-item'.
        
        # Let's look for something like:
        # <div class="roundtable ..."> or <article> with a link to the roundtable detail
        events = soup.find_all("article", class_="roundtable")
        if not events:
            # Some years, the structure may differ. Try fallback selectors or skip.
            events = soup.find_all("div", class_="roundtable")
        
        for event in events:
            # Extract link to the roundtable detail page
            a_tag = event.find("a")
            if not a_tag:
                continue
            roundtable_link = a_tag.get("href")
            
            # Now visit the detail page
            roundtable_data = crawl_roundtable_detail(roundtable_link)
            if roundtable_data:
                current_id += 1
                roundtable_data["id"] = current_id
                all_roundtables.append(roundtable_data)
    
    return all_roundtables

def crawl_roundtable_detail(url):
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
        response = requests.get(url)
        if response.status_code != 200:
            return None
    except requests.exceptions.RequestException:
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
    
    # 2) Date & Time
    # Often the date/time is in a <div class="roundtable-time"> or similar container
    # We might see something like: "Saturday, May 5th, 2012, 4:30 - 6:30PM"
    # We'll attempt to parse date/time from a single string if it’s combined.
    date_time_tag = soup.find("div", class_="roundtable-time")
    if date_time_tag:
        date_time_text = date_time_tag.get_text(strip=True)
        # Try splitting into date and time if feasible
        # This is site-specific – you may need a more robust pattern matching
        # For illustration, we assume date and time are separated by a comma after the date
        # e.g., "Saturday, May 5th, 2012, 4:30 - 6:30PM"
        # We'll use a simplistic approach here:
        parts = date_time_text.split(", ")
        if len(parts) >= 4:
            # date might be something like "Saturday", "May 5th", "2012"
            day_of_week = parts[0]
            month_day = parts[1]
            year = parts[2]
            # The rest is time
            time_part = ", ".join(parts[3:])
            
            roundtable_info["date"] = f"{day_of_week}, {month_day}, {year}"
            roundtable_info["time"] = time_part
        else:
            # If splitting fails, store the text as is or attempt a regex
            roundtable_info["date"] = date_time_text
            roundtable_info["time"] = ""
    
    # 3) Description
    # The main description might be in a <div class="roundtable-description"> or inside <div class="entry-content">
    description_tag = soup.find("div", class_="entry-content")
    if description_tag:
        paragraphs = description_tag.find_all("p", recursive=False)
        # If the site has multiple paragraphs, we can combine them.
        full_description = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        roundtable_info["description"] = full_description
    
    # 4) Panelists (names, titles, and bios)
    # The site might list speakers in a <section class="speakers"> or similar. 
    # We must gather:
    #   "name_1", "title_1", "description_1"
    #   "name_2", "title_2", "description_2", etc.
    panelist_container = soup.find("section", class_="speakers")
    # Fallback if the structure is different
    if not panelist_container:
        panelist_container = soup.find("div", class_="speakers")
    
    if panelist_container:
        # Each speaker might be in an article tag or div
        speakers = panelist_container.find_all("article", class_="speaker")
        if not speakers:
            speakers = panelist_container.find_all("div", class_="speaker")
        
        # Iterate through each speaker
        for idx, speaker in enumerate(speakers, start=1):
            # speaker name might be in <h3> or <h4> or <span class="name">, etc.
            name_tag = speaker.find(["h3", "h4", "span"], class_=re.compile("name|speaker-name"))
            speaker_name = name_tag.get_text(strip=True) if name_tag else ""
            
            # speaker title might be in <p class="speaker-title"> or <div class="title">
            title_tag = speaker.find(["p", "div"], class_=re.compile("title|speaker-title"))
            speaker_title = title_tag.get_text(strip=True) if title_tag else ""
            
            # bio could be in a paragraph or div with class "bio"
            bio_tag = speaker.find(["p", "div"], class_=re.compile("bio|speaker-bio"))
            speaker_bio = ""
            if bio_tag:
                speaker_bio = bio_tag.get_text(strip=True)
            else:
                # Sometimes the bio is in multiple paragraphs, so we could do:
                bio_paras = speaker.find_all("p")
                speaker_bio = " ".join([para.get_text(strip=True) for para in bio_paras])
            
            # Add to the dictionary
            roundtable_info["panelist"][f"name_{idx}"] = speaker_name
            roundtable_info["panelist"][f"title_{idx}"] = speaker_title
            roundtable_info["panelist"][f"description_{idx}"] = speaker_bio
    
    return roundtable_info

if __name__ == "__main__":
    # Crawl and collect data
    data = crawl_helixcenter_roundtables()
    
    # Save to JSON file
    with open("helixcenter_roundtables.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Crawling complete. Data saved to helixcenter_roundtables.json")
