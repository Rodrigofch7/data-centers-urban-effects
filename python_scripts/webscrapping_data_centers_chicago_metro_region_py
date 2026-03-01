import requests
import pandas as pd
from bs4 import BeautifulSoup
import time

# --- Configuration & Metadata ---
# Source: datacentermap.com verified city listings for IL, IN, WI

CITIES = [
    # Illinois (137+55+2+2+2+6+1+4 = 209 total)
    ("Chicago",         "illinois/chicago"),
    ("Aurora",          "illinois/aurora"),
    ("Bloomington",     "illinois/bloomington"),
    ("Peoria",          "illinois/peoria"),
    ("Champaign",       "illinois/champaign"),
    ("Springfield",     "illinois/springfield"),
    ("Rockford",        "illinois/rockford"),
    ("Edwardsville",    "illinois/edwardsville"),
    ("Rantoul",         "illinois/rantoul"),

    # Indiana (1+1+45+13+15+7+2+1+1+1+1 = 88 total)
    ("Columbus",        "indiana/columbus"),
    ("Hammond",         "indiana/hammond"),
    ("Indianapolis",    "indiana/indianapolis"),
    ("South Bend",      "indiana/south-bend"),
    ("Fort Wayne",      "indiana/fort-wayne"),
    ("Gary",            "indiana/gary"),
    ("Evansville",      "indiana/evansville"),
    ("La Porte",        "indiana/la-porte"),
    ("Jeffersonville",  "indiana/jeffersonville"),
    ("Noblesville",     "indiana/noblesville"),
    ("Portage",         "indiana/portage"),

    # Wisconsin (3+2+2+12+12+1+16+1+2 = 51 total)
    ("Appleton",        "wisconsin/appleton"),
    ("Eau Claire",      "wisconsin/eau-claire"),
    ("Green Bay",       "wisconsin/green-bay"),
    ("Kenosha",         "wisconsin/kenosha"),
    ("Madison",         "wisconsin/madison"),
    ("Marshfield",      "wisconsin/marshfield"),
    ("Milwaukee",       "wisconsin/milwaukee"),
    ("Wausau",          "wisconsin/wausau"),
    ("Wisconsin Rapids","wisconsin/wisconsin-rapids"),
]

CITY_TO_STATE = {
    # Illinois
    "Chicago": "IL", "Aurora": "IL", "Bloomington": "IL", "Peoria": "IL",
    "Champaign": "IL", "Springfield": "IL", "Rockford": "IL",
    "Edwardsville": "IL", "Rantoul": "IL",
    # Indiana
    "Columbus": "IN", "Hammond": "IN", "Indianapolis": "IN",
    "South Bend": "IN", "Fort Wayne": "IN", "Gary": "IN",
    "Evansville": "IN", "La Porte": "IN", "Jeffersonville": "IN",
    "Noblesville": "IN", "Portage": "IN",
    # Wisconsin
    "Appleton": "WI", "Eau Claire": "WI", "Green Bay": "WI",
    "Kenosha": "WI", "Madison": "WI", "Marshfield": "WI",
    "Milwaukee": "WI", "Wausau": "WI", "Wisconsin Rapids": "WI",
}

TARGET_STATES = {"IL", "IN", "WI"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# --- Core Logic ---

def parse_datacenter_html(html_content, city_name):
    """
    Parses HTML content and returns a list of datacenter records.
    Kept separate from HTTP logic so it can be unit tested independently.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.select(".ui.card")
    records = []

    for card in cards:
        header_div = card.find("div", class_="header")
        facility_name = header_div.get_text(strip=True) if header_div else "N/A"

        description_div = card.find("div", class_="description")
        details = list(description_div.stripped_strings) if description_div else []

        state = CITY_TO_STATE.get(city_name, "N/A")

        # Safety filter: only keep records belonging to our target states
        if state not in TARGET_STATES:
            continue

        record = {
            "scraped_city": city_name,
            "state": state,
            "facility": facility_name,
            "operator": details[0] if len(details) > 0 else "N/A",
            "street":   details[1] if len(details) > 1 else "N/A",
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
        state = CITY_TO_STATE.get(city_name, "?")
        url = f"https://www.datacentermap.com/usa/{path}/"
        print(f"[{idx}/{total}] Scraping {city_name}, {state} ...")

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

    output_path = "data/il_in_wi_datacenters.csv"
    df.to_csv(output_path, index=False)
    print(f"\nDone! {len(df)} total records saved to '{output_path}'")
    return df


if __name__ == "__main__":
    run_scraper()