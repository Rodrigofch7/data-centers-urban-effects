import pathlib
import pandas as pd


def merging():
    """
    Taking data center that Carlos found (which unlike Rodrigo's data center data,
    has years of construction) and merges it with housing data found by Rodrigo
    """

    housing_path = pathlib.Path("data/housing_and_data_centers_data/zillow_yearly_estimates_chicago_metro.csv")
    datacenters_path = pathlib.Path("data/housing_and_data_centers_data/chicago_data_centers_match (first_permit).csv")

    # Loading data
    housing = pd.read_csv(housing_path)
    datacenters = pd.read_csv(datacenters_path)

    # HOUSING CLEANING
    # Converting housing data to the "long/panel" format for merging, where years are one column
    year_cols = housing.filter(regex=r"^\d{4}").columns

    housing_long = housing.melt(
        id_vars=[col for col in housing.columns if col not in year_cols],
        value_vars=year_cols,
        var_name="year",
        value_name="hval",
    )

    # Adding leading/lagging columns to data (1 year before, 1 year after year of data center construction)
    housing_long = housing_long.sort_values(["ZCTA5CE20", "year"])
    housing_long["hval_yrbefore"] = housing_long.groupby("ZCTA5CE20")["hval"].shift(1)
    housing_long["hval_yrafter"] = housing_long.groupby("ZCTA5CE20")["hval"].shift(-1)

    # DATACENTER CLEANING
    # Removing 'NOTFOUND' rows in construction date column
    datacenters = datacenters[datacenters["first_permit"] != "NOTFOUND"]

    # MERGING DATA
    # Since data centers can exist in the same zip code, this is a left join onto data center data (many to one)
    merged = datacenters.merge(
        housing_long,
        left_on=["Zipcode", "first_permit"],
        right_on=["ZCTA5CE20", "year"],
        how="left",
    )

    # Removing duplicate columns and rearranging
    merged = merged.drop(columns=["ZCTA5CE20", "first_permit", "StateName"])
    merged = merged.sort_values(["Zipcode", "year"])

    # Writing csv
    merged.to_csv("data/housing_and_data_centers_data/datacenters_housing_merged.csv", index=False)

if __name__ == "__main__":
    merging()
  
