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
        return "", ""

    # The first <p> typically contains date/time,
    # e.g. "Saturday, May 5th<br/>4:30 - 6:30PM"
    date_time_html = p_tags[0]
    # Convert <br> to space => "Saturday, May 5th 4:30 - 6:30PM"
    raw_text = date_time_html.get_text(" ", strip=True)

    # Some WordPress pages might use an en-dash or em-dash instead of a hyphen.
    # This ensures consistency: "4:30 - 6:30PM" rather than "4:30 – 6:30PM".
    cleaned_text = re.sub(r"[–—]", "-", raw_text)  # Replace en/em dashes with a normal hyphen

    print(f"[DEBUG] Raw date/time text: '{raw_text}' => Cleaned: '{cleaned_text}'")

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
        # E.g., "Saturday, May 5th"
        date_str = date_str.strip()
        time_str = time_str.strip()
        print(f"[DEBUG] => date='{date_str}' time='{time_str}'")
        return date_str, time_str
    else:
        # If we can't find a time portion, just store the entire string as "date"
        print("[DEBUG] No separate time found; storing entire string in 'date'.")
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

    # The typical structure is:
    # <article class="post-XXX participant type-participant ...">
    #   <div class="entry-content">
    #       <p>Full biography ...</p>
    #   </div>
    # </article>
    article_tag = soup.find("article", class_=re.compile(r"(participant|post-\d+)"))
    if not article_tag:
        return None

    content_div = article_tag.find("div", class_="entry-content")
    if not content_div:
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

    #
    # 1) Title
    #
    title_tag = soup.find("h1", class_="entry-title")
    if title_tag:
        roundtable_info["title"] = title_tag.get_text(strip=True)
        print(f"[DEBUG] Roundtable title: {roundtable_info['title']}")

    #
    # 2) Date & Time
    #
    # The snippet shows them in <p>:
    #   <p>Saturday, May 5th<br/>4:30 - 6:30PM</p>
    # We can gather text, e.g. "Saturday, May 5th 4:30 - 6:30PM"
    # Then parse out the time using a regex or splitting by lines.
    #
    main_article = soup.find("article", class_="roundtable")
    if main_article:
        header_section = main_article.find("header", class_="entry-header")
        if header_section:
            # The first <p> might be the date/time
            # p_tags = header_section.find_all("p", recursive=False)
            # e.g. "Saturday, May 5th<br/>4:30 - 6:30PM"
            # if p_tags:
            #     date_time_html = p_tags[0]  # This is the first <p>
            #     # Convert <br/> to spaces so we get "Saturday, May 5th 4:30 - 6:30PM"
            #     date_time_text = date_time_html.get_text(" ", strip=True)
            #     print(f"[DEBUG] Found date_time_text: {date_time_text}")


            # New approach using parse_date_time
            if header_section:
                date_str, time_str = parse_date_time(header_section)
                roundtable_info["date"] = date_str
                roundtable_info["time"] = time_str

                # Usually date_time_text looks like: "Saturday, May 5th 4:30 - 6:30PM"
                # Let's match time with a small regex:
                #   e.g. "4:30 - 6:30PM" or "4:30-6:30 pm"
                time_pattern = re.compile(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*(?:[AaPp][Mm])?")
                match = time_pattern.search(date_str) # (date_time_text)
                if match:
                    time_str = match.group(0)
                    # The rest is date
                    date_str = date_str.replace(time_str, "").strip(", ;:")
                    roundtable_info["date"] = date_str.strip()
                    roundtable_info["time"] = time_str.strip()
                    print(f"[DEBUG] date => '{roundtable_info['date']}', time => '{roundtable_info['time']}'")
                else:
                    # If no match, store it all in date
                    roundtable_info["date"] = date_str
                    print("[DEBUG] Could not parse separate time. All stored in 'date'.")

    #
    # 3) Description
    #
    # Next, the roundtable description is in <div class="entry-content">.
    desc_div = soup.find("div", class_="entry-content")
    if desc_div:
        # Usually multiple paragraphs
        desc_paras = desc_div.find_all("p", recursive=False)
        full_desc = " ".join(p.get_text(strip=True) for p in desc_paras if p.get_text(strip=True))
        roundtable_info["description"] = full_desc
        print(f"[DEBUG] Roundtable description: {roundtable_info['description']}")

    #
    # 4) Panelists
    #
    # <div class="roundtable-participants">
    #   <article class="helix-post post-XXX participant ...">
    #       <h2 class="entry-title">Name</h2>
    #       <p>Speaker Title</p>
    #       <div class="entry-content"><p>Short bio <a class="read-more" href="...">read more »</a></p></div>
    #   </article>
    #   ...
    # </div>
    #
    participants_div = soup.find("div", class_="roundtable-participants")
    if participants_div:
        articles = participants_div.find_all("article", class_=re.compile(r"participant"))
        print(f"[DEBUG] Found {len(articles)} participant entries.")
        for idx, art in enumerate(articles, start=1):
            # 4a) Name from <h2 class="entry-title">
            name_tag = art.find("h2", class_="entry-title")
            name_str = name_tag.get_text(strip=True) if name_tag else "Unknown"

            # 4b) Title from the <p> after the <h2> in the same header block
            # The site layout:
            #   <div class="col-sm-9">
            #       <h2 class="entry-title">Chris Impey</h2>
            #       <p>University Distinguished Professor, Astronomy, University of Arizona</p>
            #   </div>
            header_div = art.find("header", class_="entry-header")
            speaker_title = ""
            if header_div:
                # The <p> with the speaker's title is typically right after the <h2>
                p_title = header_div.find("p")
                if p_title:
                    speaker_title = p_title.get_text(strip=True)

            # 4c) Short bio from <div class="entry-content"><p>...</p></div>
            short_bio = ""
            entry_content_div = art.find("div", class_="entry-content")
            if entry_content_div:
                short_p_tags = entry_content_div.find_all("p", recursive=False)
                short_bio = " ".join(p.get_text(" ", strip=True)
                                     for p in short_p_tags if p.get_text(strip=True))

            # 4d) Check if there's a "read more" link
            # If so, we follow that link to get the FULL bio
            full_bio = short_bio  # default is short if no read more link
            read_more_link = entry_content_div.find("a", class_="read-more") if entry_content_div else None
            if read_more_link:
                speaker_page_href = read_more_link.get("href")
                if speaker_page_href:
                    speaker_full_bio = crawl_speaker_page(speaker_page_href, headers)
                    if speaker_full_bio:
                        full_bio = speaker_full_bio  # override short bio

            # Insert data into the dictionary
            roundtable_info["panelist"][f"name_{idx}"] = name_str
            roundtable_info["panelist"][f"title_{idx}"] = speaker_title
            roundtable_info["panelist"][f"description_{idx}"] = full_bio

            print(f"[DEBUG] -> Speaker #{idx}: {name_str}")
            print(f"         Title: {speaker_title}")
            print(f"         Bio: {full_bio[:80]}{'...' if len(full_bio) > 80 else ''}")

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
        # Commonly the events are in <article class="roundtable"> or <div class="roundtable">
        events = soup.find_all("article", class_="roundtable")
        if not events:
            events = soup.find_all("div", class_="roundtable")
        print(f"[DEBUG] Found {len(events)} events for {year}.")

        for evt in events:
            # Each event typically has a <a href="..."> link
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
