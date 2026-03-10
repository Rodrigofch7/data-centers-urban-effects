import pytest
import pandas as pd
from pathlib import Path
from cleaning_utilities import rename_dfcols,calculate_elecScore,consolidate_hhc_2000_plus
@pytest.fixture
def loading_data():
    elec_water = pd.read_csv(Path("elec_water_cleaned.csv"), dtype={'ZCTA5A': str})
    monthHHC = pd.read_csv(Path("monthHHC_cleaned.csv"), dtype={'ZCTA5A': str})
    return {
        "elec_water": elec_water,
        "monthHHC": monthHHC,
    }

def make_elec_df(buckets):
    """Helper to build a minimal elec df from a list of 6 bucket counts."""
    cols = ["Elec 0-50","Elec 50-99","Elec 100-149","Elec 150-199","Elec 200-249","Elec 250+"]
    df = pd.DataFrame([buckets], columns=cols)
    df["totalElec"] = df[cols].sum(axis=1)
    return df

def test_elec_score_lowest_bucket():
    """All respondents in cheapest bucket means score is 1"""
    df = make_elec_df([100, 0, 0, 0, 0, 0])
    assert calculate_elecScore(df).iloc[0] == 1

def test_elec_score_highest_bucket():
    """All respondents in most expensive bucket means score is 6"""
    df = make_elec_df([0, 0, 0, 0, 0, 100])
    assert calculate_elecScore(df).iloc[0] == 6

def test_elec_score_in_bounds():
    """Score falls between 1 and 6"""
    df = make_elec_df([10, 20, 30, 25, 10, 5])
    score = calculate_elecScore(df).iloc[0]
    assert 1 <= score <= 6

prefix_map = {"APCXE": "Elec", "APCZE": "Water"}
elec_map = {"004": "0-50", "005": "50-99"}
pattern = r"^(\w{5})(\d{3})"

def test_rename_known_elec_col():
    assert rename_dfcols("APCXE004", prefix_map, elec_map, pattern) == "Elec 0-50"

def test_rename_unmatched_col_unchanged():
    """Columns like ZCTA5A that don't match the pattern should pass through untouched"""
    assert rename_dfcols("ZCTA5A", prefix_map, elec_map, pattern) == "ZCTA5A"

def test_consolidate_ranged_buckets():
    """2000-2500 and 2500-3000 type columns should be combined into HHC 2000+"""
    df = pd.DataFrame({"HHC 2000-2500": [10], "HHC 2500-3000": [20]})
    consolidate_hhc_2000_plus(df)
    assert df["HHC 2000+"].iloc[0] == 30

def test_ziplen(loading_data):
    """Test case for if zip codes are all 5 digits"""
    assert loading_data["elec_water"]["ZCTA5A"].str.len().eq(5).all()
    assert loading_data["monthHHC"]["ZCTA5A"].str.len().eq(5).all()

