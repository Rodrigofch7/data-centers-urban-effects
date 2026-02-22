import pandas as pd
import string

chicago_data_centers = pd.read_csv("data/chicago_data_centers.csv")

# Defining a dictionary with words to standardize data center addresses:
WORDS = {
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "boulevard": "blvd",
    "drive": "dr",
    "lane": "ln",
    "place": "pl",
    "court": "ct"
}

def standard_street(address):
    if pd.isna(address):
        return ""

    street_clean = str(address).lower().strip()

    # Removing punctuation by translating to spaces:
    translation = str.maketrans({ch: " " for ch in string.punctuation})
    street_clean = street_clean.translate(translation)

    tokens = street_clean.split()  # Splitting on whitespace

    clean_tokens = []
    for token in tokens:
        clean_tokens.append(WORDS.get(token, token))

    return "_".join(clean_tokens)

# Creating a standardized street key:
chicago_data_centers["street_standard"] = chicago_data_centers["street"].apply(standard_street)

# Counting how many rows share the same standardized street:
chicago_data_centers["address_count"] = (
    chicago_data_centers.groupby("street_standard")["street_standard"].transform("size"))

# Dropping duplicates by standardized street and keeping first:
cleaned_data = chicago_data_centers.drop_duplicates(subset=["street_standard"], keep="first")

cleaned_data.to_csv("data/chicago_data_centers.csv", index=False)