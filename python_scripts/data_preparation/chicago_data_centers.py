import pandas as pd
import string

# Defining a dictionary with words to standardize data center addresses:
WORDS = {"north": "n",
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
    "court": "ct"}

# Address standardization helper function:
def standard_street(address):
    if pd.isna(address):
        return ""

    street_clean = str(address).lower().strip()

    # Replacing punctuation with spaces:
    translation = str.maketrans({ch: " " for ch in string.punctuation})
    street_clean = street_clean.translate(translation)

    tokens = street_clean.split() # Splitting on whitespace

    clean_tokens = []
    for token in tokens:
        clean_tokens.append(WORDS.get(token, token))

    return "_".join(clean_tokens)

# Clean scraped data center dataset:
def clean_scraped_datacenters():
    
    chicago_datacenters:  pd.DataFrame = pd.read_csv("data/top_us_cities_datacenters.csv")

    chicago_datacenters = chicago_datacenters[chicago_datacenters["scraped_city"] == "Chicago"].copy()

    chicago_datacenters["first_permit"] = ""

    # Creating a standardized street key:
    chicago_datacenters["street_standard"] = chicago_datacenters["street"].apply(standard_street)

    # Counting how many rows share the same standardized street:
    chicago_datacenters["address_count"] = (chicago_datacenters.groupby("street_standard")["street_standard"].transform("size"))

    # Dropping duplicates by standardized street and keeping first:
    chicago_datacenters = chicago_datacenters.drop_duplicates(subset=["street_standard"], keep="first")

    chicago_datacenters.to_csv("data/chicago_data_centers.csv", index=False)

    return chicago_datacenters

# Function to cleand datacenter merged dataset:
def clean_datacenter_housing_data():

    # Loading merged dataset:
    chicago_datacenters_2:  pd.DataFrame = pd.read_csv("data/housing_and_data_centers_data/datacenters_housing_merged.csv")

    # Keeping only the required columns:
    columns = [
        "Operator",
        "Address",
        "Zipcode",
        "County_Name",
        "year",
        "hval",
        "hval_yrbefore",
        "hval_yrafter"]

    chicago_datacenters_2 = chicago_datacenters_2[columns]

    # Renaming columns:
    chicago_datacenters_2 = chicago_datacenters_2.rename(columns={ "County_Name": "County", 
                            "year": "First_Operation_Permit", 
                            "hval": "Housing_Avg_Price", 
                            "hval_yrbefore": "Housing_Avg_Price_Before_Permit",
                            "hval_yrafter": "Housing_Avg_Price_After_Permit"})

    # Creating DataCenter_Code column:
    chicago_datacenters_2.insert(0, "DataCenter_Code", ["DC" + str(i).zfill(2) for i in range(1, len(chicago_datacenters_2) + 1)])

    # Saving cleaned dataset:
    chicago_datacenters_2.to_csv("data/chicago_data_centers_2.csv", index=False)

    return chicago_datacenters_2

# Function to clean household costs dataset:
def clean_monthHHC():
    # Loading dataset:
    housing_cost_data = pd.read_csv("data/sinas_data/monthHHC_cleaned.csv")

    # Keeping Chicago datacenters zipcodes:
    zipcodes = [ 46320, 60005, 60007, 60010, 60016, 60018, 60056, 60115, 
                     60131, 60143, 60148, 60164, 60191, 60502, 60523, 60532, 
                     60605, 60607, 60608, 60616, 60617, 60632]

    # Keeping only rows with those ZIPs
    housing_cost_data  = housing_cost_data [housing_cost_data ["ZCTA5A"].isin(zipcodes)].copy()

    # Keep only the needed columns:
    housing_cost_data  =  housing_cost_data[["ZCTA5A", "HHCScore", "start_year", "end_year"]].copy()

    # Renaming columns:
    housing_cost_data  = housing_cost_data .rename(columns={
        "ZCTA5A": "Zipcode",
        "HHCScore": "Housing_Costs_Score"})

    # Saving cleaned file (same folder):
    housing_cost_data .to_csv("data/housing_cost_data.csv", index=False)

    return housing_cost_data