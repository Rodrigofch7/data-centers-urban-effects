# To test run: python -m pytest tests/test_webscrapping.py
# To run:      uv run python -m data_centers_next_door.webscrapping.webscrapping_data_centers

import requests
import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path
import time

# To run:
#   uv run python -m data_centers_next_door.webscrapping.webscrapping_data_centers
ROOT = Path(__file__).resolve().parents[2]

OUTPUT_PATH = ROOT / "data/housing_and_data_centers_data/top_us_cities_datacenters.csv"

# ── Configuration & Metadata ──────────────────────────────────────────────────

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
    "New York": "NY",
    "Los Angeles": "CA",
    "Chicago": "IL",
    "Houston": "TX",
    "Phoenix": "AZ",
    "Philadelphia": "PA",
    "San Antonio": "TX",
    "San Diego": "CA",
    "Dallas": "TX",
    "Jacksonville": "FL",
    "Miami": "FL",
    "Boston": "MA",
    "Atlanta": "GA",
    "Santa Clara": "CA",
    "Denver": "CO",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


# ── Core Logic (module-level so importable for tests) ─────────────────────────


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
    total = len(CITIES)

    for idx, (city_name, path) in enumerate(CITIES, start=1):
        url = f"https://www.datacentermap.com/usa/{path}/"
        print(f"[{idx}/{total}] Scraping {city_name}...")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            city_records = parse_datacenter_html(response.text, city_name)
            print(f"  -> Found {len(city_records)} datacenters")
            all_data.extend(city_records)
            time.sleep(2)  # Respectful crawl delay
        except Exception as e:
            print(f"  -> Could not scrape {city_name}: {e}")

    df = pd.DataFrame(all_data)

    if not df.empty:
        df = df.sort_values(["state", "scraped_city"]).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nDone! {len(df)} total records saved to '{OUTPUT_PATH}'")
    return df


if __name__ == "__main__":
    run_scraper()
