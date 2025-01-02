import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time


def parse_date_time(header_section):
    """
    Extract the date and time from the first <p> under the roundtable header.
    Returns (date_str, time_str).
    """

    # Try to locate the paragraphs in the roundtable header
    p_tags = header_section.find_all("p", recursive=False)
    if not p_tags:
        print("[DEBUG] parse_date_time: No <p> tags found in header_section.")
        return "", ""

    # The first <p> typically contains date/time,
    # e.g. "Saturday, May 5th<br/>4:30 - 6:30PM"
    date_time_html = p_tags[0]

    # Convert <br> to space => "Saturday, May 5th 4:30 - 6:30PM"
    raw_text = date_time_html.get_text(" ", strip=True)

    # Some WordPress pages might use en-dash or em-dash instead of a hyphen.
    # This ensures consistency: "4:30 - 6:30PM" rather than "4:30 – 6:30PM".
    cleaned_text = re.sub(r"[–—]", "-", raw_text)

    print(f"[DEBUG] parse_date_time: raw_text='{raw_text}' => cleaned_text='{cleaned_text}'")

    # Regex to match something like "4:30 - 6:30PM" or "4:30 - 6:30 PM"
    # We allow optional space before AM/PM and a relaxed approach to the dash spacing:
    time_pattern = re.compile(
        r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*[AaPp]\.?[Mm]\.?"
    )

    match = time_pattern.search(cleaned_text)
    if match:
        time_str = match.group(0).strip()
        # Everything else is date
        date_str = cleaned_text.replace(time_str, "").strip(", ;:")
        date_str = date_str.strip()
        time_str = time_str.strip()
        print(f"[DEBUG] parse_date_time => date='{date_str}', time='{time_str}'")
        return date_str, time_str
    else:
        # If we can't find a time portion, store the entire string as "date"
        print("[DEBUG] parse_date_time: No time found; storing entire string in 'date'.")
        return cleaned_text, ""


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

    # Typical structure:
    # <article class="post-XXX participant type-participant ...">
    #   <div class="entry-content">
    #       <p>Full biography ...</p>
    #   </div>
    # </article>
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


def crawl_roundtable_detail(url, headers):
    """
    Given a roundtable detail page URL, extract:
        - title
        - date
        - time
        - description
        - panelists (name, title, FULL bio)
    Return a dictionary following the specified structure.
    """
    print(f"[DEBUG] Crawling roundtable detail page: {url}")
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
    main_article = soup.find("article", class_="roundtable")
    if main_article:
        header_section = main_article.find("header", class_="entry-header")
        if header_section:
            # Use the parse_date_time helper
            date_str, time_str = parse_date_time(header_section)

            # Store these in roundtable_info
            roundtable_info["date"] = date_str
            roundtable_info["time"] = time_str

            print(f"[DEBUG] Final stored date='{roundtable_info['date']}', time='{roundtable_info['time']}'")
    else:
        print("[DEBUG] Could not find main_article with class='roundtable' to extract date/time.")

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
            # (a) Name from <h2 class="entry-title">
            name_tag = art.find("h2", class_="entry-title")
            name_str = name_tag.get_text(strip=True) if name_tag else "Unknown"

            # (b) Title from the <p> after the <h2> in the same header block
            speaker_title = ""
            header_div = art.find("header", class_="entry-header")
            if header_div:
                p_title = header_div.find("p")
                if p_title:
                    speaker_title = p_title.get_text(strip=True)

            # (c) Short bio from <div class="entry-content"><p>...</p></div>
            short_bio = ""
            entry_content_div = art.find("div", class_="entry-content")
            if entry_content_div:
                short_p_tags = entry_content_div.find_all("p", recursive=False)
                short_bio = " ".join(
                    p.get_text(" ", strip=True) for p in short_p_tags if p.get_text(strip=True)
                )

            # (d) Check if there's a "read more" link -> get FULL bio
            full_bio = short_bio
            read_more_link = entry_content_div.find("a", class_="read-more") if entry_content_div else None
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
      - Date / Time
      - Description
      - Full list of speakers with titles and FULL bios
    Return a list of dictionaries, each containing data for one roundtable.
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
        # Commonly the events are <article class="roundtable"> or <div class="roundtable">
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

            rt_data = crawl_roundtable_detail(rt_link, headers)
            if rt_data:
                current_id += 1
                rt_data["id"] = current_id
                all_roundtables.append(rt_data)

    return all_roundtables


if __name__ == "__main__":
    start_time = time.time()
    data = crawl_helixcenter_roundtables()
    end_time = time.time()

    # Calculate the execution time
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.6f} seconds")

    datetime_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_filename = f"helixcenter_openai_{datetime_str}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n[DEBUG] Crawl complete. Saved to {output_filename}")
