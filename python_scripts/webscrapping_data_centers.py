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

# --- Core Logic Functions ---

def parse_datacenter_cards(soup, city_name):
    """
    Extracts data from BeautifulSoup cards. 
    Separated from the network request to allow for unit testing.
    """
    records = []
    cards = soup.select(".ui.card")
    
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

# --- Tests ---

def test_city_to_state_mapping():
    """Verify state mapping for critical cities."""
    assert CITY_TO_STATE["Chicago"] == "IL"
    assert CITY_TO_STATE["Los Angeles"] == "CA"

def test_html_parsing_logic():
    """Test extraction logic using a mocked HTML snippet (No internet needed)."""
    mock_html = """
    <div class="ui card">
        <div class="header">Test Lab</div>
        <div class="description">
            CloudCorp<br/>123 Tech Lane<br/>60616<br/>Chicago
        </div>
    </div>
    """
    soup = BeautifulSoup(mock_html, "html.parser")
    results = parse_datacenter_cards(soup, "Chicago")
    
    assert len(results) == 1
    assert results[0]["facility"] == "Test Lab"
    assert results[0]["zip_code"] == "60616"
    assert results[0]["state"] == "IL"

# --- Main Execution Block ---

if __name__ == "__main__":
    all_data = []

    for city_name, path in CITIES:
        url = f"https://www.datacentermap.com/usa/{path}/"
        print(f"Scraping {city_name}...")

        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Process the HTML
            city_records = parse_datacenter_cards(soup, city_name)
            all_data.extend(city_records)

            # Respectful delay between cities
            time.sleep(2)

        except Exception as e:
            print(f"Could not scrape {city_name}: {e}")

    # Create DataFrame and Save
    if all_data:
        df = pd.DataFrame(all_data)
        print(f"\nTotal data centers scraped: {len(df)}")
        
        file_name = "top_us_cities_datacenters.csv"
        df.to_csv(file_name, index=False)
        print(f"File saved locally as {file_name}")
    else:
        print("No data was collected.")