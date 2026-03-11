import pandas as pd
from pathlib import Path
import re

#--Helper Functions--
def rename_dfcols(col, prefix_map: dict, code_map: dict, match_pattern):
    """
    Renames column of dataframe for column names in this format:\n
        {prefix}{code} -> {Elec/Water}{range}\n 
        (e.g. APCXE004 -> Elec 0-50)\n
    Variables given in IPUMS are poorly coded (e.g. APCXE004 represents Elec 0-50 column).
    This function is necessary to recode them to be understandable.
    """
    match = re.match(match_pattern, col)
    if match:
        prefix, code = match.groups()
        if prefix in prefix_map:
            mapped_prefix = prefix_map[prefix]
            return f"{mapped_prefix} {code_map[code]}"
    return col

def calculate_elecScore(df):
    """
    Constructs score by factorizing each electricity price range into 1-6, and 
    multiplying each of those categories by their proportion of respondents 
    (effectively a weighted average).
    """
    eleclst = df[
        [
        "Elec 0-50",
        "Elec 50-99",
        "Elec 100-149",
        "Elec 150-199",
        "Elec 200-249",
        "Elec 250+",
        ]]
    denom = df["totalElec"].replace(0, pd.NA)
    return eleclst.mul([1, 2, 3, 4, 5, 6], axis=1).sum(axis=1) / denom

def calculate_waterScore(df):
    """
    Constructs score by factorizing each water/sewage price range into 1-6, and 
    multiplying each of those categories by their proportion of respondents 
    (effectively a weighted average).
    """
    waterlst = df[
    [
        "Water 0-125",
        "Water 125-249",
        "Water 250-499",
        "Water 500-749",
        "Water 750-999",
        "Water 1000+",
    ]]
    denom = df["totalWater"].replace(0, pd.NA)
    return waterlst.mul([1, 2, 3, 4, 5, 6], axis=1).sum(axis=1) / denom

def calculate_hhcscore(df):
    """
    Constructs score by factorizing each household cost price range into 1-13, and 
    multiplying each of those categories by their proportion of respondents 
    (effectively a weighted average).
    """
    hhclst = df[
            [
                "HHC 0-100",
                "HHC 100-200",
                "HHC 200-300",
                "HHC 300-400",
                "HHC 400-500",
                "HHC 500-600",
                "HHC 600-700",
                "HHC 700-800",
                "HHC 800-900",
                "HHC 900-1000",
                "HHC 1000-1500",
                "HHC 1500-2000",
                "HHC 2000+",
            ]
        ]
    denom = df["HHC Total"].replace(0, pd.NA)
    return  (hhclst.mul([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], axis=1).sum(axis=1)
            / denom)

def consolidate_hhc_2000_plus(df):
    """
    Combines high-end HHC bucket columns into a single 'HHC 2000+' column.
    Handles inconsistency across ACS survey years where the 2000+ range is split
    differently (e.g. 2000-2500, 2500-3000, 3000+ in some years).
    """
    cols_to_combine = []
    for col in df.columns:
        match = re.match(r"^HHC\s([\d\-\+]+)", col)
        if match:
            code = match.group(1)
            if re.match(r"^(2|3)\d{3}-(2|3)\d{3}", code) or re.match(r"^(2|3)\d{3}\+", code):
                cols_to_combine.append(col)
    df["HHC 2000+"] = df[cols_to_combine].sum(axis=1)
    return df


#--Main functions (cleaning the data)--
def cleaning_elec_water():
    """
    Cleaning electricity and water/sewage data by zip code from IPUMS NGHIS.\n
    Raw Data: counts of people that fall into price buckets (e.g. 0-50$, $50-100, etc.)\n
    Output: Cleaned csv of electricity/water price score for each zip code in each 5 year 
    period between 2017-2021 to 2020-2024.\n
    Raw data needs to be renamed since it contains variable names that can only be 
    understood with the codebook that IPUMS NHGIS provides
    """
    # Importing and loading data
    d2017t2021 = pd.read_csv(Path("data/energy and water data/nhgis0003_ds255_20215_zcta.csv"),dtype={'ZCTA5A': str})
    d2018t2022 = pd.read_csv(Path("data/energy and water data/nhgis0003_ds263_20225_zcta.csv"),dtype={'ZCTA5A': str})
    d2019t2023 = pd.read_csv(Path("data/energy and water data/nhgis0003_ds268_20235_zcta.csv"),dtype={'ZCTA5A': str})
    d2020t2024 = pd.read_csv(Path("data/energy and water data/nhgis0003_ds273_20245_zcta.csv"),dtype={'ZCTA5A': str})

    # Mappings for renaming
    prefix_map = {
        # 2017
        "APCXE": "Elec",
        "APCZE": "Water",
        # 2018
        "AREAE": "Elec",
        "ARECE": "Water",
        # 2019
        "ATE7E": "Elec",
        "ATE9E": "Water",
        # 2020
        "AVGIE": "Elec",
        "AVGKE": "Water",
    }
    elec_map = {
        "001": "fakeTotal",
        "002": "Not charged",
        "003": "Charged",
        "004": "0-50",
        "005": "50-99",
        "006": "100-149",
        "007": "150-199",
        "008": "200-249",
        "009": "250+",
    }
    water_map = {
        "001": "fakeTotal",
        "002": "Not charged",
        "003": "Charged",
        "004": "0-125",
        "005": "125-249",
        "006": "250-499",
        "007": "500-749",
        "008": "750-999",
        "009": "1000+",
    }
    # Renaming column names, defining column totals, and building scores
    for df in [d2017t2021, d2018t2022, d2019t2023, d2020t2024]:
        # Col name change using list comprehension
        df.columns = [
            rename_dfcols(col, prefix_map, elec_map, r"^(\w{5})(\d{3})")
            if re.match(r"^(APCXE|AREAE|ATE7E|AVGIE)(\d{3})", col)
            else rename_dfcols(col, prefix_map, water_map, r"^(\w{5})(\d{3})")
            if re.match(r"^(APCZE|ARECE|ATE9E|AVGKE)(\d{3})", col)
            else col
            for col in df.columns
        ]

        # Defining column totals
        df["totalElec"] = (
            df["Elec 0-50"]
            + df["Elec 50-99"]
            + df["Elec 100-149"]
            + df["Elec 150-199"]
            + df["Elec 200-249"]
            + df["Elec 250+"]
        )
        df["totalWater"] = (
            df["Water 0-125"]
            + df["Water 125-249"]
            + df["Water 250-499"]
            + df["Water 500-749"]
            + df["Water 750-999"]
            + df["Water 1000+"]
        )
        # Creating scores
        df["elecScore"] = calculate_elecScore(df)
        df["waterScore"] = calculate_waterScore(df)
        

    # Merging dataframes by isolating the columns they have in common, merging (by rowstacking)
    # off of that
    common_cols = set(d2017t2021.columns)
    for df in [d2018t2022, d2019t2023, d2020t2024]:
        common_cols = common_cols.intersection(df.columns)
    common_cols = list(common_cols)

    dfs = [
        d2017t2021[common_cols],
        d2018t2022[common_cols],
        d2019t2023[common_cols],
        d2020t2024[common_cols],
    ]

    combined_df = pd.concat(dfs, axis=0, ignore_index=True)
    # Eliminating extraneous vars
    combined_df = combined_df[
        [
            "ZCTA5A",
            "YEAR",
            "COUNTYA",
            "Elec 0-50",
            "Elec 50-99",
            "Elec 100-149",
            "Elec 150-199",
            "Elec 200-249",
            "Elec 250+",
            "Water 0-125",
            "Water 125-249",
            "Water 250-499",
            "Water 500-749",
            "Water 750-999",
            "Water 1000+",
            "totalElec",
            "totalWater",
            "elecScore",
            "waterScore",
        ]
    ]

    # Finally, splitting up year into beginning and final year variables
    combined_df[["start_year", "end_year"]] = (
        combined_df["YEAR"].str.split("-", expand=True).astype(int)
    )
    combined_df.to_csv(Path("data/clean_elecwater_hc_scores/elec_water_cleaned.csv"), index=False)


def cleaning_hhcosts():
    """
    Cleaning household cost data by zip code from IPUMS NGHIS (multiple 5-year ACS data).\n
    Raw Data: counts of people that fall into price buckets (e.g. 0-100$, $100-200, etc.)\n
    Output: Cleaned csv of household cost score for each zip code in each 5 year period between
    2007-2011 to 2020-2024.
    """

    # Importing data for household costs (hhc) 
    hhc2007t2011 = pd.read_csv(Path("data/hhc/nhgis0007_ds185_20115_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2008t2012 = pd.read_csv(Path("data/hhc/nhgis0007_ds192_20125_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2009t2013 = pd.read_csv(Path("data/hhc/nhgis0007_ds202_20135_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2010t2014 = pd.read_csv(Path("data/hhc/nhgis0007_ds207_20145_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2011t2015 = pd.read_csv(Path("data/hhc/nhgis0007_ds216_20155_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2012t2016 = pd.read_csv(Path("data/hhc/nhgis0007_ds226_20165_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2013t2017 = pd.read_csv(Path("data/hhc/nhgis0007_ds234_20175_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2014t2018 = pd.read_csv(Path("data/hhc/nhgis0007_ds240_20185_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2015t2019 = pd.read_csv(Path("data/hhc/nhgis0007_ds245_20195_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2016t2020 = pd.read_csv(Path("data/hhc/nhgis0007_ds250_20205_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2017t2021 = pd.read_csv(Path("data/hhc/nhgis0007_ds255_20215_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2018t2022 = pd.read_csv(Path("data/hhc/nhgis0007_ds263_20225_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2019t2023 = pd.read_csv(Path("data/hhc/nhgis0007_ds268_20235_zcta.csv"),dtype={'ZCTA5A': str})
    hhc2020t2024 = pd.read_csv(Path("data/hhc/nhgis0007_ds273_20245_zcta.csv"),dtype={'ZCTA5A': str})

    #Defining maps for renaming column names
    prefix_map = {}

    suffix_map = {
        "001": "fakeTotal",
        "002": "0-100",
        "003": "100-200",
        "004": "200-300",
        "005": "300-400",
        "006": "400-500",
        "007": "500-600",
        "008": "600-700",
        "009": "700-800",
        "010": "800-900",
        "011": "900-1000",
        "012": "1000-1500",
        "013": "1500-2000",
        "014": "2000-2500",
        "015": "2500-3000",
        "016": "3000+",
        "017": "No cash rent",
    }

    # Renaming column names and defining column totals
    for df in [
        hhc2007t2011,
        hhc2008t2012,
        hhc2009t2013,
        hhc2010t2014,
        hhc2011t2015,
        hhc2012t2016,
        hhc2013t2017,
        hhc2014t2018,
        hhc2015t2019,
        hhc2016t2020,
        hhc2017t2021,
        hhc2018t2022,
        hhc2019t2023,
        hhc2020t2024,
    ]:
        # Extracting relevant columns for renaming
        for col in df.columns:
            match = re.match(r"^([\w\d]+)E(\d{3})", col)
            if match:
                prefix, code = match.groups()
                prefix_map[prefix] = "HHC"
        # Col name change using list comprehension
        df.columns = [
            rename_dfcols(col, prefix_map, suffix_map, r"^([\w\d]+)E(\d{3})")
            if re.match(r"^([\w\d]+)E(\d{3})", col)
            else col
            for col in df.columns
        ]

        # Combining 2000+ columns into one column for consistency between dataframes
        consolidate_hhc_2000_plus(df)
        # Getting column totals
        df["HHC Total"] = df.filter(regex=r"^HHC\s[\w\d\+\-]+").sum(axis=1)
        # Making household cost score
        
        df["HHCScore"] = calculate_hhcscore(df)


    # Merging dataframes by isolating the columns they have in common, merging (by rowstacking)
    # off of that
    common_cols = set(hhc2007t2011.columns)
    dflst = [
        hhc2007t2011,
        hhc2008t2012,
        hhc2009t2013,
        hhc2010t2014,
        hhc2011t2015,
        hhc2012t2016,
        hhc2013t2017,
        hhc2014t2018,
        hhc2015t2019,
        hhc2016t2020,
        hhc2017t2021,
        hhc2018t2022,
        hhc2019t2023,
        hhc2020t2024,
    ]

    for df in [
        hhc2008t2012,
        hhc2009t2013,
        hhc2010t2014,
        hhc2011t2015,
        hhc2012t2016,
        hhc2013t2017,
        hhc2014t2018,
        hhc2015t2019,
        hhc2016t2020,
        hhc2017t2021,
        hhc2018t2022,
        hhc2019t2023,
        hhc2020t2024,
    ]:
        common_cols = common_cols.intersection(df.columns)
    common_cols = list(common_cols)
    dfs = [df1[common_cols] for df1 in dflst]
    combined_df = pd.concat(dfs, axis=0, ignore_index=True)

    # Eliminating extraneous vars
    combined_df = combined_df[
        [
            "ZCTA5A",
            "YEAR",
            "COUNTYA",
            "HHC 0-100",
            "HHC 100-200",
            "HHC 200-300",
            "HHC 300-400",
            "HHC 400-500",
            "HHC 500-600",
            "HHC 600-700",
            "HHC 700-800",
            "HHC 800-900",
            "HHC 900-1000",
            "HHC 1000-1500",
            "HHC 1500-2000",
            "HHC 2000+",
            "HHC Total",
            "HHCScore",
        ]
    ]

    # Finally, splitting up year into beginning and final year for period
    combined_df[["start_year", "end_year"]] = (
        combined_df["YEAR"].str.split("-", expand=True).astype(int)
    )

    combined_df.to_csv(Path("data/clean_elecwater_hc_scores/monthHHC_cleaned.csv"), index=False)

def filter_and_pivot():
    """
    Takes household cost data, filters for Chicago metro area zip codes,
    and converts it into wide format for dashboard visualization
    """
    all_us_df = pd.read_csv(Path("data/clean_elecwater_hc_scores/monthHHC_cleaned.csv"),dtype={"ZCTA5A": str})
    #String of Chicago Metro Area Zip codes, split this into list
    chicago_metro_zips = pd.read_csv("data/chicago_metro_zips.csv", 
                                     dtype={"unique(chicagometro_housing$ZCTA5CE20)": str})
    
    #Filtering for U.S. zip codes in chicago_metro_zips
    chicago_metro_df = all_us_df.merge(
    chicago_metro_zips,
    left_on="ZCTA5A",
    right_on="unique(chicagometro_housing$ZCTA5CE20)",
    how="inner"
    )
    #Pivoting HHC score to wide format 
    chicago_pivoted = chicago_metro_df.pivot(index = "ZCTA5A",
                                             columns="YEAR", 
                                             values="HHCScore")

    chicago_pivoted.to_csv(Path("data/clean_elecwater_hc_scores/pivoted_HHCScores.csv"))

if __name__ == "__main__":
    cleaning_elec_water()
    cleaning_hhcosts()
    filter_and_pivot()