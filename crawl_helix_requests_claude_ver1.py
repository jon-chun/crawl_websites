import requests
from bs4 import BeautifulSoup
import json
import logging
from datetime import datetime
import re
import time
from typing import Dict, List, Optional
import concurrent.futures
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)

class HelixCenterCrawler:
    """Crawler for extracting roundtable information from Helix Center website."""
    
    def __init__(self, base_url: str = "https://www.helixcenter.org/roundtables/20"):
        """
        Initialize the crawler with base URL and necessary attributes.
        
        Args:
            base_url (str): The base URL for Helix Center roundtables
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.roundtables = []
        
    def generate_urls(self) -> List[str]:
        """Generate all roundtable URLs from 2012 to 2024."""
        return [f"{self.base_url}{str(year).zfill(2)}/" for year in range(12, 25)]

    def get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse page content with error handling and rate limiting.
        
        Args:
            url (str): URL to fetch
            
        Returns:
            Optional[BeautifulSoup]: Parsed page content or None if failed
        """
        try:
            time.sleep(1)  # Rate limiting
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"Error fetching {url}: {str(e)}")
            return None

    def extract_event_info(self, event_url: str) -> Dict:
        """
        Extract detailed information from an individual event page.
        
        Args:
            event_url (str): URL of the event page
            
        Returns:
            Dict: Dictionary containing event details
        """
        soup = self.get_page_content(event_url)
        if not soup:
            return {}

        event_info = {
            'title': '',
            'date': '',
            'time': '',
            'description': '',
            'panelist': {}
        }

        try:
            # Extract title
            title_elem = soup.find('h1', class_='entry-title')
            if title_elem:
                event_info['title'] = title_elem.text.strip()

            # Extract date and time
            datetime_elem = soup.find('div', class_='event-date-time')
            if datetime_elem:
                date_text = datetime_elem.get_text()
                # Split date and time using regex
                date_match = re.search(r'([A-Za-z]+,\s+[A-Za-z]+\s+\d+(?:st|nd|rd|th)?,\s+\d{4})', date_text)
                time_match = re.search(r'(\d+:\d+\s*(?:AM|PM)\s*-\s*\d+:\d+\s*(?:AM|PM))', date_text)
                
                if date_match:
                    event_info['date'] = date_match.group(1)
                if time_match:
                    event_info['time'] = time_match.group(1)

            # Extract description
            description_elem = soup.find('div', class_='event-description')
            if description_elem:
                event_info['description'] = description_elem.get_text().strip()

            # Extract panelist information
            panelist_section = soup.find('div', class_='event-speakers')
            if panelist_section:
                panelists = panelist_section.find_all('div', class_='speaker')
                for idx, panelist in enumerate(panelists, 1):
                    name = panelist.find('h3', class_='speaker-name')
                    title = panelist.find('div', class_='speaker-title')
                    bio = panelist.find('div', class_='speaker-bio')
                    
                    if name:
                        event_info['panelist'][f'name_{idx}'] = name.text.strip()
                    if title:
                        event_info['panelist'][f'title_{idx}'] = title.text.strip()
                    if bio:
                        event_info['panelist'][f'description_{idx}'] = bio.text.strip()

        except Exception as e:
            logging.error(f"Error extracting info from {event_url}: {str(e)}")

        return event_info

    def process_year_page(self, url: str) -> List[Dict]:
        """
        Process a yearly roundtable page and extract all event information.
        
        Args:
            url (str): URL of the yearly roundtable page
            
        Returns:
            List[Dict]: List of event information dictionaries
        """
        soup = self.get_page_content(url)
        if not soup:
            return []

        events = []
        event_links = soup.find_all('a', class_='event-link')
        
        for event_link in event_links:
            event_url = urljoin(url, event_link['href'])
            event_info = self.extract_event_info(event_url)
            if event_info:
                events.append(event_info)

        return events

    def crawl(self) -> None:
        """
        Main crawling method to process all years and save results.
        """
        urls = self.generate_urls()
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(self.process_year_page, url): url for url in urls}
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    events = future.result()
                    self.roundtables.extend(events)
                    logging.info(f"Processed {url}: Found {len(events)} events")
                except Exception as e:
                    logging.error(f"Error processing {url}: {str(e)}")

        # Add IDs to events
        for idx, event in enumerate(self.roundtables, 1):
            event['id'] = idx

        # Save results to JSON file
        self.save_results()

    def save_results(self) -> None:
        """
        Save crawled results to JSON file.
        """
        try:
            with open('helixcenter_roundtables.json', 'w', encoding='utf-8') as f:
                json.dump(self.roundtables, f, indent=2, ensure_ascii=False)
            logging.info(f"Results saved to helixcenter_roundtables.json")
        except Exception as e:
            logging.error(f"Error saving results: {str(e)}")

def main():
    """
    Main function to run the crawler.
    """
    logging.info("Starting Helix Center crawler")
    crawler = HelixCenterCrawler()
    crawler.crawl()
    logging.info("Crawler finished")

if __name__ == "__main__":
    main()