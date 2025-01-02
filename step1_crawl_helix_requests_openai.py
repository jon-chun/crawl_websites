import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

def parse_date_time(p_tag, year=None):
    """
    Extract the date and time from the <p> containing something like:
        "Saturday, May 5th<br/>4:30 - 6:30PM"
    If year is provided, we can append it to the date string.
    Returns (full_date_str, time_str).
    """

    # Convert <br> to space => "Saturday, May 5th 4:30 - 6:30PM"
    raw_text = p_tag.get_text(" ", strip=True)

    # Example: "Saturday, May 5th 4:30 - 6:30PM"
    # We want to separate the "Saturday, May 5th" from "4:30 - 6:30PM"
    # Some WordPress pages may use fancy dashes, so we unify them:
    cleaned_text = re.sub(r"[–—]", "-", raw_text)

    # Regex that looks for the time range: "4:30 - 6:30PM"
    time_pattern = re.compile(r"(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*[AaPp]\.?[Mm]\.?)")
    match = time_pattern.search(cleaned_text)

    if not match:
        # No time found, we store everything in date
        return (cleaned_text, "")

    time_str = match.group(1).strip()
    # Everything else is date
    date_str = cleaned_text.replace(time_str, "").strip(",;: ")
    
    # Optionally append the loop "year" if we want a complete date:
    # e.g. "Saturday, May 5th, 2012"
    if year:
        date_str = f"{date_str}, {year}"

    return date_str, time_str


def crawl_speaker_page(speaker_url, headers):
    """
    Given the URL to a speaker's page, fetch and extract the FULL speaker bio
    from <div class="entry-content">. Return the text as a single string.
    """
    print(f"[DEBUG]   >> Accessing speaker page: {speaker_url}")
    try:
        resp = requests.get(speaker_url, headers=headers)
        if resp.status_code != 200:
            print(f"[DEBUG]   >> Speaker page request failed with status code {resp.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG]   >> RequestException in speaker page: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    article_tag = soup.find("article", class_=re.compile(r"(participant|post-\d+)"))
    if not article_tag:
        print("[DEBUG] crawl_speaker_page: No matching <article> found.")
        return None

    content_div = article_tag.find("div", class_="entry-content")
    if not content_div:
        print("[DEBUG] crawl_speaker_page: No <div class='entry-content'> found.")
        return None

    paras = content_div.find_all("p", recursive=True)
    full_bio = " ".join(p.get_text(" ", strip=True) for p in paras if p.get_text(strip=True))
    return full_bio


def crawl_roundtable_detail(url, headers, year=None):
    """
    Given a roundtable detail page URL, extract:
        - title
        - date
        - time
        - description
        - panelists (name, title, FULL bio)
    year: the integer year from the top-level listing (e.g. 2012)
    Return a dictionary following the specified structure.
    """
    print(f"[DEBUG] Crawling roundtable detail page: {url} (year={year})")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"[DEBUG] Skipping detail page {url}, status {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] Request exception: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

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
        print(f"[DEBUG] Roundtable title: {roundtable_info['title']}")

    # 2) Date & Time
    # On the example snippet, there's a <div class="col-md-9"> with:
    #   <h1 class="entry-title">...</h1>
    #   <p>Saturday, May 5th<br/>4:30 - 6:30PM</p>
    # Let's locate that second <p> inside the same col-md-9 container:
    main_header = soup.find("header", class_="entry-header")
    if main_header:
        col_md9_div = main_header.find("div", class_="col-md-9")
        if col_md9_div:
            p_tags = col_md9_div.find_all("p", recursive=False)
            # Typically the first <p> is "Saturday, May 5th<br/>4:30 - 6:30PM"
            # or we might need to check the second if the first is the "Past Event" label
            # We'll pick p_tags[0] if it has a time signature. If not, maybe p_tags[1].
            for p_tag in p_tags:
                raw_text = p_tag.get_text(" ", strip=True)
                if "AM" in raw_text or "PM" in raw_text:  # quick check
                    date_str, time_str = parse_date_time(p_tag, year=year)
                    roundtable_info["date"] = date_str
                    roundtable_info["time"] = time_str
                    print(f"[DEBUG] => date='{date_str}', time='{time_str}' from p_tag='{raw_text}'")
                    break
        else:
            print("[DEBUG] Did not find <div class='col-md-9'> in header.")
    else:
        print("[DEBUG] No main_header found for date/time parsing.")

    # 3) Description
    desc_div = soup.find("div", class_="entry-content")
    if desc_div:
        # Usually multiple paragraphs
        desc_paras = desc_div.find_all("p", recursive=False)
        full_desc = " ".join(p.get_text(strip=True) for p in desc_paras if p.get_text(strip=True))
        roundtable_info["description"] = full_desc
        print(f"[DEBUG] Roundtable description: {roundtable_info['description']}")

    # 4) Panelists
    participants_div = soup.find("div", class_="roundtable-participants")
    if participants_div:
        articles = participants_div.find_all("article", class_=re.compile(r"participant"))
        print(f"[DEBUG] Found {len(articles)} participant entries.")
        for idx, art in enumerate(articles, start=1):
            # (a) Name
            name_tag = art.find("h2", class_="entry-title")
            name_str = name_tag.get_text(strip=True) if name_tag else "Unknown"

            # (b) Title
            speaker_title = ""
            header_div = art.find("header", class_="entry-header")
            if header_div:
                p_title = header_div.find("p")
                if p_title:
                    speaker_title = p_title.get_text(strip=True)

            # (c) Short bio
            short_bio = ""
            entry_content_div = art.find("div", class_="entry-content")
            if entry_content_div:
                short_p_tags = entry_content_div.find_all("p", recursive=False)
                short_bio = " ".join(
                    p.get_text(" ", strip=True) for p in short_p_tags if p.get_text(strip=True)
                )

            # (d) read more -> FULL bio
            full_bio = short_bio
            if entry_content_div:
                read_more_link = entry_content_div.find("a", class_="read-more")
                if read_more_link:
                    speaker_page_href = read_more_link.get("href")
                    if speaker_page_href:
                        speaker_full_bio = crawl_speaker_page(speaker_page_href, headers)
                        if speaker_full_bio:
                            full_bio = speaker_full_bio

            # Insert into dictionary
            roundtable_info["panelist"][f"name_{idx}"] = name_str
            roundtable_info["panelist"][f"title_{idx}"] = speaker_title
            roundtable_info["panelist"][f"description_{idx}"] = full_bio

            print(f"[DEBUG] -> Speaker #{idx}: {name_str}")
            print(f"         Title: {speaker_title}")
            print(f"         Bio: {full_bio[:80]}{'...' if len(full_bio) > 80 else ''}")

    else:
        print("[DEBUG] No <div class='roundtable-participants'> found for panelists.")

    return roundtable_info


def crawl_helixcenter_roundtables():
    """
    Crawl Helix Center roundtable pages from 2012 to 2024 and extract event details:
      - Title
      - (Date, Time) from the roundtable detail pages
      - Description
      - Panelists with short or full bios
      We also pass `year` into crawl_roundtable_detail to incorporate
      the year into the date if desired.
    """
    base_url = "https://www.helixcenter.org/roundtables/"
    start_year = 2012
    end_year = 2024
    all_roundtables = []
    current_id = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    for year in range(start_year, end_year + 1):
        year_url = f"{base_url}{year}/"
        print(f"\n[DEBUG] Fetching roundtables for year={year} : {year_url}")
        try:
            resp = requests.get(year_url, headers=headers)
            if resp.status_code != 200:
                print(f"[DEBUG] Skipping {year_url}, status={resp.status_code}")
                continue
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] RequestException for {year_url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        events = soup.find_all("article", class_="roundtable")
        if not events:
            events = soup.find_all("div", class_="roundtable")
        print(f"[DEBUG] Found {len(events)} events for {year}.")

        for evt in events:
            a_tag = evt.find("a")
            if not a_tag:
                continue
            rt_link = a_tag.get("href")
            if not rt_link:
                continue

            rt_data = crawl_roundtable_detail(rt_link, headers, year=year)
            if rt_data:
                current_id += 1
                rt_data["id"] = current_id
                all_roundtables.append(rt_data)

    return all_roundtables


if __name__ == "__main__":
    start_time = time.time()
    data = crawl_helixcenter_roundtables()
    end_time = time.time()

    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.6f} seconds")

    datetime_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"helixcenter_openai_{datetime_str}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n[DEBUG] Crawl complete. Saved to {output_filename}")
