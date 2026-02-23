import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import pytest

# --- Configuration & Metadata ---
CITIES = [
    ("New York", "new-york/new-york"),
    ("Los Angeles", "california/los-angeles"),
    ("Chicago", "illinois/chicago"),
    ("Houston", "texas/houston"),
    ("Phoenix", "arizona/phoenix"),
    ("Philadelphia", "pennsylvania/philadelphia"),
    ("San Antonio", "texas/san-antonio"),
    ("San Diego", "california/san-diego"),
    ("Dallas", "texas/dallas"),
    ("Jacksonville", "florida/jacksonville"),
    ("Miami", "florida/miami"),
    ("Boston", "massachusetts/boston"),
    ("Atlanta", "georgia/atlanta"),
    ("Santa Clara", "california/santa-clara"),
    ("Denver", "colorado/denver"),
]

CITY_TO_STATE = {
    "New York": "NY", "Los Angeles": "CA", "Chicago": "IL", "Houston": "TX",
    "Phoenix": "AZ", "Philadelphia": "PA", "San Antonio": "TX", "San Diego": "CA",
    "Dallas": "TX", "Jacksonville": "FL", "Miami": "FL", "Boston": "MA",
    "Atlanta": "GA", "Santa Clara": "CA", "Denver": "CO",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- Core Logic ---

def parse_datacenter_html(html_content, city_name):
    """
    Parses HTML content and returns a list of dictionaries.
    Extracted into a function so we can test it without hitting the web.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.select(".ui.card")
    records = []

    for card in cards:
        header_div = card.find("div", class_="header")
        facility_name = header_div.get_text(strip=True) if header_div else "N/A"

        description_div = card.find("div", class_="description")
        details = list(description_div.stripped_strings) if description_div else []

        record = {
            "scraped_city": city_name,
            "state": CITY_TO_STATE.get(city_name, "N/A"),  
            "facility": facility_name,
            "operator": details[0] if len(details) > 0 else "N/A",
            "street": details[1] if len(details) > 1 else "N/A",
            "zip_code": details[2] if len(details) > 2 else "N/A",
            "city_in_desc": details[3] if len(details) > 3 else "N/A",
        }
        records.append(record)
    return records

def run_scraper():
    """Main execution loop for the scraper."""
    all_data = []
    for city_name, path in CITIES:
        url = f"https://www.datacentermap.com/usa/{path}/"
        print(f"Scraping {city_name}...")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            city_records = parse_datacenter_html(response.text, city_name)
            all_data.extend(city_records)
            time.sleep(2) # Respectful delay
        except Exception as e:
            print(f"Could not scrape {city_name}: {e}")
    
    df = pd.DataFrame(all_data)
    df.to_csv("top_us_cities_datacenters.csv", index=False)
    return df

# --- Tests (Pytest) ---

def test_city_to_state_mapping_integrity():
    """Test: Ensure every city in the scraper list has a state mapping."""
    for city_name, _ in CITIES:
        assert city_name in CITY_TO_STATE, f"{city_name} is missing from CITY_TO_STATE"

def test_html_parsing_extraction():
    """Test: Verify that the scraper correctly pulls data from a sample HTML block."""
    sample_html = """
    <div class="ui card">
        <div class="header">Test Facility</div>
        <div class="description">
            Test Operator<br/>
            456 Server Lane<br/>
            90210<br/>
            Los Angeles
        </div>
    </div>
    """
    results = parse_datacenter_html(sample_html, "Los Angeles")
    
    assert len(results) == 1
    assert results[0]["facility"] == "Test Facility"
    assert results[0]["operator"] == "Test Operator"
    assert results[0]["zip_code"] == "90210"
    assert results[0]["state"] == "CA"

def test_parsing_handles_missing_fields():
    """Test: Verify the scraper doesn't crash if HTML fields are missing."""
    empty_html = '<div class="ui card"></div>'
    results = parse_datacenter_html(empty_html, "Chicago")
    
    assert results[0]["facility"] == "N/A"
    assert results[0]["operator"] == "N/A"

# --- Main Guard ---
if __name__ == "__main__":
    # This only runs if you do 'python scrape_datacenters.py'
    # It won't run if you just run 'pytest'
    final_df = run_scraper()
    print(f"\nDone! Scraped {len(final_df)} centers.")