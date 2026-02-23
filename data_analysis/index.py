import pandas as pd
from pathlib import Path

# NOTE: THE METHODOLOGY AND INPUTS ARE SUBJECT TO CHANGE AS DATA BECOMES CLEANER

# Data Analysis
# We will create index as an indicator of affordability. Zip codes with
# more data centers, higher average electricity and water prices, and
# home prices will have a higher index, and thus be less affordable and more
# at risk of pricing out residents of the region

# Importing our MOCK DATA as a pandas dataframe

FILEPATH = Path(__file__).parent / "top_10_us_cities_datacenters_augmented_mock.csv"
OUTPATH = Path(__file__).parent / "top_10_us_cities_datacenters_scores_mock.csv"


print(FILEPATH)

data_centers = pd.read_csv(FILEPATH)

# Calculating the unique counts of data centers by zip codes
unique_data_centers = (
    data_centers.groupby("zip_code")["facility"]
    .nunique()
    .reset_index()
    .rename(columns={"facility": "facility_count"})
)

# Left joining this onto data_centers dataset
data_centers = pd.merge(data_centers, unique_data_centers, on="zip_code")

# SCORING 
def scoring(variable,method = "composite"):
    """
    Takes a variable and calculates a "ranking" based on its decile value or its
    corresponding z-score. Each method has their distinct advantages and disadvantages
    and be adjust as such. Default method will be the composite/quantile method

    Inputs:
           variable: a pandas dataframe variable by which we are calculating scores for
    """
    if method == "composite":
        score_name = f"{variable}_score"

        data_centers[score_name] = pd.qcut(data_centers[variable], q=10, labels=False)

    elif method == "z-score":
        z_score_name = f"{variable}_z_score"

        data_centers[z_score_name] = (data_centers[variable] - data_centers[variable].mean()) / data_centers[variable].std()
    
    else:
        raise ValueError("Method must be 'composite' or 'z-score'!")

# Composite Scoring Method
scoring("avg_electricity_cost_usd_per_kwh", method = "composite")
scoring("avg_home_price_usd",method = "composite")
scoring("avg_water_cost_usd_monthly",method = "composite")

# Z-Scoring Method
scoring("avg_electricity_cost_usd_per_kwh",method = "z-score")
scoring("avg_home_price_usd",method = "z-score")
scoring("avg_water_cost_usd_monthly",method = "z-score")

print(data_centers.head())

# Creating the index score based on weights. The weights MUST add to 1!
def index(
    facility_weight=0.25, home_weight=0.25, electricity_weight=0.25, water_weight=0.25
,method = "composite"):
    """
    Creates a composite index score for a zip code based on selected weights

    Inputs:
           facility_weight: The weight assigned to number of data center facilities
           home_weight: The weight assigned to the ranking of average housing costs
           electricity_weight: The weight assigned to the ranking of electricity costs
           water_weight: The weight assigned to the ranking of water usage costs
    """
    if facility_weight + home_weight + electricity_weight + water_weight != 1:
        raise ValueError("Weights must add up 1")

    weights = {
        "facility_weight": facility_weight,
        "home_price_weight": home_weight,
        "electricity_price_weight": electricity_weight,
        "water_price_weight": water_weight,
    }

    if method == "composite":
        data_centers["index_score"] = (
            (data_centers["facility_count"] * weights["facility_weight"])
            + (
                data_centers["avg_electricity_cost_usd_per_kwh_score"]
                * weights["electricity_price_weight"]
            )
            + (data_centers["avg_home_price_usd_score"] * weights["home_price_weight"])
            + (
                data_centers["avg_water_cost_usd_monthly_score"]
                * weights["water_price_weight"]
            )
        )
    elif method == "z-score":
                data_centers["z_index_score"] = (
            (data_centers["facility_count"] * weights["facility_weight"])
            + (
                data_centers["avg_electricity_cost_usd_per_kwh_z_score"]
                * weights["electricity_price_weight"]
            )
            + (data_centers["avg_home_price_usd_z_score"] * weights["home_price_weight"])
            + (
                data_centers["avg_water_cost_usd_monthly_z_score"]
                * weights["water_price_weight"]
            )
        )

# Running index:
index()

#Exporting analysis onto .csv file
#Composite Index mock output
data_centers.to_csv(OUTPATH)