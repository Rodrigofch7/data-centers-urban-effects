import requests
import pandas as pd
from bs4 import BeautifulSoup
import time

# List of the top 10 biggest American cities and their corresponding Data Center Map paths
cities = [
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

# State-only mapping
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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

all_data = []

for city_name, path in cities:
    url = f"https://www.datacentermap.com/usa/{path}/"
    print(f"Scraping {city_name}...")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.select(".ui.card")

        for card in cards:
            header_div = card.find("div", class_="header")
            facility_name = header_div.get_text(strip=True) if header_div else "N/A"

            description_div = card.find("div", class_="description")
            details = list(description_div.stripped_strings) if description_div else []

            record = {
                "scraped_city": city_name,
                "state": CITY_TO_STATE[city_name],  
                "facility": facility_name,
                "operator": details[0] if len(details) > 0 else "N/A",
                "street": details[1] if len(details) > 1 else "N/A",
                "zip_code": details[2] if len(details) > 2 else "N/A",
                "city_in_desc": details[3] if len(details) > 3 else "N/A",
            }
            all_data.append(record)

        # Respectful delay between cities
        time.sleep(2)

    except Exception as e:
        print(f"Could not scrape {city_name}: {e}")

# Create DataFrame
df = pd.DataFrame(all_data)

print(f"\nTotal data centers scraped: {len(df)}")
print(df.head())

# Save to CSV
file_name = "top_us_cities_datacenters.csv"
df.to_csv(file_name, index=False)
print(f"File saved locally as {file_name}")
