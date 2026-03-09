import pytest
import pandas as pd
from pathlib import Path

@pytest.fixture
def loading_data():
    elec_water = pd.read_csv(Path("elec_water_cleaned.csv"), dtype={'ZCTA5A': str})
    monthHHC = pd.read_csv(Path("monthHHC_cleaned.csv"), dtype={'ZCTA5A': str})
    chicago_zips = pd.read_csv(Path("chicago_metro_zips.csv"), dtype={'ZCTA5A': str})

    return {
        "elec_water": elec_water,
        "monthHHC": monthHHC,
        "chicago_zips": chicago_zips
    }

def test_ziplen(loading_data):
    """Test case for if zip codes are all 5 digits"""
    assert loading_data["elec_water"]["ZCTA5A"].str.len().eq(5).all()
    assert loading_data["monthHHC"]["ZCTA5A"].str.len().eq(5).all()

def test_elecwater_zipunique(loading_data):
    """Test case for number of rows per unique zip codes (should be 4 for all zip codes)"""
    counts = loading_data["elec_water"].groupby("ZCTA5A").size()
    bad = counts[counts != 4]
    assert bad.empty, f"Unexpected counts: {bad.to_dict()}"

#No test case for monthHHC because there are many, many zip codes that don't have all
#14 years.

# def test_monthHHC_zipunique():
#     """Test case for number of rows per unique zip codes (should be at least 10 for all zip codes)"""
#     counts = loading_data()["monthHHC"].groupby("ZCTA5A").size()
#     bad = counts[counts < 10]
#     assert bad.empty, f"Unexpected counts: {bad.to_dict()}"



def test_shape(loading_data):
    """Test case for correct num of rows"""
    assert loading_data["elec_water"].shape[0] == 135088
    assert loading_data["monthHHC"].shape[0] == 466292

def test_chicagometro_zips_present_elecwater(loading_data):
    """Tests if all zip codes in Chicago metro area are present in elec_water_cleaned.csv"""
    missing_zips = set(loading_data["chicago_zips"]["unique(chicagometro_housing$ZCTA5CE20)"]) - set(loading_data["elec_water"]["ZCTA5A"])
    assert not missing_zips, f"Zips not present: {missing_zips}"

def test_chicagometro_zips_present_monthHHC(loading_data):
    """Tests if all zip codes in Chicago metro area are present in monthHHC_cleaned.csv"""
    missing_zips = set(loading_data["chicago_zips"]["unique(chicagometro_housing$ZCTA5CE20)"]) - set(loading_data["monthHHC"]["ZCTA5A"])
    assert not missing_zips, f"Zips not present: {missing_zips}"