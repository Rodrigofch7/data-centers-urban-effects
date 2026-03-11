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

def clean_scraped_datacenters():
    
    chicago_datacenters:  pd.DataFrame = pd.read_csv("data/housing_and_data_centers_data/top_us_cities_datacenters.csv")

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

def clean_datacenter_housing_data():

    # Loading merged dataset:
    chicago_datacenters_2:  pd.DataFrame = pd.read_csv("data/housing_and_data_centers_data/datacenters_housing_merged.csv")

    # Keeping only the required columns:
    columns = [
        "Operator",
        "Address",
        "Zipcode",
        "CountyName",
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
    codes = []

    # Looping over the number of rows in the dataframe:
    for i in range(1, len(chicago_datacenters_2) + 1):

        # Convert the number to string:
        number = str(i)

        # Add leading zero if needed:
        zero_number = number.zfill(2)

        # Build the data center code:
        code = "DC" + zero_number

        # Add the code to the list:
        codes.append(code)

    # Insert the new column as the first column:
    chicago_datacenters_2.insert(0, "DataCenter_Code", codes)

    # Saving cleaned dataset:
    chicago_datacenters_2.to_csv("data/chicago_data_centers_2.csv", index=False)

    return chicago_datacenters_2

def clean_monthHHC():
    # Loading dataset:
    housing_cost_data = pd.read_csv("data/sinans_data/monthHHC_cleaned.csv")

    # Keeping Chicago datacenters zipcodes:
    zipcodes = [ 46320, 60005, 60007, 60010, 60016, 60018, 60056, 60115, 
                     60131, 60143, 60148, 60164, 60191, 60502, 60523, 60532, 
                     60605, 60607, 60608, 60616, 60617, 60632]

    # Keeping only rows with those zipcodes:
    housing_cost_data  = housing_cost_data [housing_cost_data ["ZCTA5A"].isin(zipcodes)].copy()

    # Keeping only the needed columns:
    housing_cost_data  =  housing_cost_data[["ZCTA5A", "HHCScore", "start_year", "end_year"]].copy()

    # Renaming columns:
    housing_cost_data  = housing_cost_data .rename(columns={
        "ZCTA5A": "Zipcode",
        "HHCScore": "Housing_Costs_Score"})

    # Saving cleaned file (same folder):
    housing_cost_data .to_csv("data/housing_cost_data.csv", index=False)

    return housing_cost_data

def add_housing_cost_scores():
    # Loading files:
    dc = pd.read_csv("data/chicago_data_centers_2.csv")
    hc = pd.read_csv("data/housing_cost_data.csv")

    # Ensuring consistent types:
    dc["Zipcode"] = dc["Zipcode"].astype(int)
    dc["First_Operation_Permit"] = dc["First_Operation_Permit"].astype(int)

    hc["Zipcode"] = hc["Zipcode"].astype(int)
    hc["end_year"] = hc["end_year"].astype(int)

    # Defining years to lookup:
    dc["year_before"] = dc["First_Operation_Permit"] - 1
    dc["year_after"]  = dc["First_Operation_Permit"]

    # Keeping only what we need from housing cost data:
    hc_lookup = hc[["Zipcode", "end_year", "Housing_Costs_Score"]].copy()

    # Merging the before column:
    dc = dc.merge(hc_lookup, left_on=["Zipcode", "year_before"], right_on=["Zipcode", "end_year"],
        how="left").rename(columns={"Housing_Costs_Score": "HC_Score_Before"}).drop(columns=["end_year"])

    # Merging the before column:
    dc = dc.merge(hc_lookup, left_on=["Zipcode", "year_after"], right_on=["Zipcode", "end_year"],
        how="left").rename(columns={"Housing_Costs_Score": "HC_Score_After"}).drop(columns=["end_year"])

    # Dropping helper columns:
    dc = dc.drop(columns=["year_before", "year_after"])

    # Saving the file:
    out_path = "data/chicago_data_centers_final.csv"
    dc.to_csv(out_path, index=False)

    return dc

# Running cleaning pipeline:
if __name__ == "__main__":
    print("Cleaning scraped data center dataset...")
    clean_scraped_datacenters()

    print("Cleaning merged housing + data center dataset...")
    clean_datacenter_housing_data()

    print("Cleaning household housing cost dataset...")
    clean_monthHHC()

    print("Adding housing cost scores...")
    add_housing_cost_scores()

    print("All cleaned datasets created successfully.")