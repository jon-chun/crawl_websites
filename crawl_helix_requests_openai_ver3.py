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
        - Panelists: name, title, short bio
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
        
        print(f"[DEBUG] Attempting to crawl roundtables for year: {year} at URL: {url}")
        
        try:
            response = requests.get(url, headers=headers)
            status_code = response.status_code
            
            print(f"[DEBUG] Received response code {status_code} for {url}")
            if status_code != 200:
                print(f"[DEBUG] Skipping {url}, status code: {status_code}")
                continue
            
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Request error for {url}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Attempt to locate the event listing (the site structure may vary by year).
        # We look for either <article class="roundtable"> or <div class="roundtable">
        events = soup.find_all("article", class_="roundtable")
        if not events:
            events = soup.find_all("div", class_="roundtable")
        
        print(f"[DEBUG] Found {len(events)} roundtable items for year {year}")
        
        for event in events:
            # Extract link to the roundtable detail page
            a_tag = event.find("a")
            if not a_tag:
                continue
            roundtable_link = a_tag.get("href")
            
            # Now visit the detail page
            if roundtable_link:
                print(f"[DEBUG] Crawling data from detail page: {roundtable_link}")
                roundtable_data = crawl_roundtable_detail(roundtable_link, headers)
                if roundtable_data:
                    current_id += 1
                    roundtable_data["id"] = current_id
                    all_roundtables.append(roundtable_data)
                else:
                    print(f"[DEBUG] No data returned for roundtable link: {roundtable_link}")
    
    return all_roundtables


def crawl_roundtable_detail(url, headers):
    """
    Given a roundtable detail page URL, extract:
        - title
        - date
        - time
        - description
        - panelists (name, title, short bio)
    Return a dictionary following the specified structure.
    """
    try:
        response = requests.get(url, headers=headers)
        status_code = response.status_code
        print(f"[DEBUG] Detail page response code for {url}: {status_code}")
        if status_code != 200:
            print(f"[DEBUG] Skipping detail page {url} due to status code {status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] Request exception for {url}: {e}")
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
    
    #
    # 1) Title
    #
    title_tag = soup.find("h1", class_="entry-title")
    if title_tag:
        roundtable_info["title"] = title_tag.get_text(strip=True)
        print(f"[DEBUG] Extracted title: {roundtable_info['title']}")
    
    #
    # 2) Date & Time
    #
    # On the Helix Center pages, the date/time might appear in the <p> immediately
    # below the <h1 class="entry-title"> inside the <header> block.
    #
    # Example snippet:
    # <p>Saturday, May 5th<br />4:30 - 6:30PM</p>
    #
    # We'll look for the <article> block with class="roundtable" or with
    # id="post-xxx" and parse the first <p> that might contain date/time.
    #
    # The user-provided HTML snippet shows that it's inside the same .col-md-9 area as the title.
    
    # Look for the main article container
    main_article = soup.find("article", {"class": re.compile(r"(roundtable|post-\d+)")})
    if main_article:
        # In the header section, find all <p> tags
        header_section = main_article.find("header", class_="entry-header")
        if header_section:
            p_tags = header_section.find_all("p", recursive=False)
            # In the snippet, the first p-tag is the one with date/time
            # e.g. "Saturday, May 5th<br/>4:30 - 6:30PM"
            if len(p_tags) >= 1:
                date_time_str = p_tags[0].get_text(separator=" ", strip=True)
                # e.g. "Saturday, May 5th 4:30 - 6:30PM"
                print(f"[DEBUG] Found date/time string: {date_time_str}")
                
                # Let's split it at the space between them or we can look for a newline
                # Often the date might be on the first line and time on the second line.
                # We replaced <br/> with space via `separator=" "`.
                # We can attempt a naive approach:
                # We'll try to parse out the time portion. Often it's something like "4:30 - 6:30PM"
                
                # We'll find the part that looks like a time range with a regex
                time_pattern = re.compile(r"\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?")
                match = time_pattern.search(date_time_str)
                if match:
                    time_str = match.group(0)
                    # The rest of the string (before that match) we treat as the date
                    date_str = date_time_str.replace(time_str, "").strip(" ,")
                    
                    roundtable_info["date"] = date_str
                    roundtable_info["time"] = time_str
                    print(f"[DEBUG] Parsed date => '{date_str}', time => '{time_str}'")
                else:
                    # If we can't find a time range, just store the entire thing as date
                    roundtable_info["date"] = date_time_str
                    print(f"[DEBUG] Could not parse time. Storing entire string in 'date'.")
    
    #
    # 3) Description
    #
    # The main description in the snippet is inside <div class="entry-content">.
    #
    description_tag = soup.find("div", class_="entry-content")
    if description_tag:
        # The snippet often has multiple paragraphs.
        # We can combine them or store them as one block:
        paragraphs = description_tag.find_all("p", recursive=False)
        full_description = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        roundtable_info["description"] = full_description
        print(f"[DEBUG] Extracted description: {roundtable_info['description']}")
    
    #
    # 4) Panelists
    #
    # In the provided snippet, the participants are listed in:
    #   <div class="roundtable-participants">
    #       <article id="post-XXX" class="helix-post post-XXX participant ...">
    #          <h2 class="entry-title"><a href="...">NAME</a></h2>
    #          <p>TITLE</p>
    #          <div class="entry-content"><p>SHORT BIO + read more link</p></div>
    #       </article>
    #       ...
    #   </div>
    #
    # We'll grab them from each <article> with class "participant".
    #
    roundtable_participants_div = soup.find("div", class_="roundtable-participants")
    if roundtable_participants_div:
        participant_articles = roundtable_participants_div.find_all("article", class_=re.compile(r"participant"))
        
        print(f"[DEBUG] Found {len(participant_articles)} participant entries in roundtable-participants.")
        
        for idx, article_tag in enumerate(participant_articles, start=1):
            # Name: <h2 class="entry-title"><a>NAME</a></h2>
            name_tag = article_tag.find("h2", class_="entry-title")
            speaker_name = name_tag.get_text(strip=True) if name_tag else ""
            
            # Title: the next <p> inside the same header
            # Structure: 
            #   <header>... <h2>...</h2> <p>title here</p> ...
            # But in the snippet, the <p> might be in the same <div class="col-sm-9">
            # We'll attempt a direct approach:
            # article_tag.find("p") that is near the name 
            # Often the second col-sm-9 <p> is the person's position. We can do:
            speaker_title = ""
            
            header_div = article_tag.find("header", class_="entry-header")
            if header_div:
                # sometimes the <p> with the person's title is in the same header div
                p_in_header = header_div.find_all("p", recursive=False)
                if p_in_header:
                    # Typically the first <p> after the <h2> is the title
                    speaker_title = p_in_header[0].get_text(strip=True)

            # Short bio: inside <div class="entry-content"><p>...</p></div>
            short_bio = ""
            entry_content_div = article_tag.find("div", class_="entry-content")
            if entry_content_div:
                # Usually there's a <p> containing the short bio
                # "Chris Impey is ... <a class='read-more' ..."
                bio_paras = entry_content_div.find_all("p", recursive=False)
                # Combine them if multiple
                short_bio = " ".join(
                    p.get_text(" ", strip=True)
                    for p in bio_paras if p.get_text(strip=True)
                )
            
            # Insert into the roundtable_info dictionary
            roundtable_info["panelist"][f"name_{idx}"] = speaker_name
            roundtable_info["panelist"][f"title_{idx}"] = speaker_title
            roundtable_info["panelist"][f"description_{idx}"] = short_bio
            
            print(f"[DEBUG] Participant {idx} => Name: {speaker_name}")
            print(f"                 => Title: {speaker_title}")
            print(f"                 => Short Bio: {short_bio}")
    else:
        print("[DEBUG] No 'roundtable-participants' container found.")
    
    return roundtable_info


if __name__ == "__main__":
    # Crawl and collect data
    data = crawl_helixcenter_roundtables()
    
    # Save to JSON file with the new name:
    output_filename = "helixcenter_openai_ver2.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n[DEBUG] Crawling complete. Data saved to {output_filename}")
