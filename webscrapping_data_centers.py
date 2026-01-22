import requests
import pandas as pd
from bs4 import BeautifulSoup
import time

url = "https://www.datacentermap.com/usa/illinois/chicago/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# Request page
response = requests.get(url, headers=headers)
response.raise_for_status()

# Parse HTML
soup = BeautifulSoup(response.text, "html.parser")

# Find all data center cards
cards = soup.find_all("a", class_="ui card")

data_list = []

for card in cards:
    # Facility name
    header_div = card.find("div", class_="header")
    facility_name = header_div.get_text(strip=True) if header_div else "N/A"

    # Description block
    description_div = card.find("div", class_="description")

    details = list(description_div.stripped_strings) if description_div else []

    record = {
        "facility": facility_name,
        "operator": details[0] if len(details) > 0 else "N/A",
        "street": details[1] if len(details) > 1 else "N/A",
        "zip_code": details[2] if len(details) > 2 else "N/A",
        "city": details[3] if len(details) > 3 else "Chicago",
    }

    data_list.append(record)

# Create DataFrame
df = pd.DataFrame(data_list)

print(f"Scraped {len(df)} Chicago data centers")
print(df.head())

df



# Save the file to your current local directory
file_name = "chicago_datacenters.csv"
df.to_csv(file_name, index=False)

print(f"File saved locally as {file_name}")