import pandas as pd
import random
import pytest
from pathlib import Path
from faker import Faker
from index import scoring

OUTPATH = Path(__file__).parent / "tests_index_dummy_data.csv"
SEED = 2006


# Setting fixture dataset
def make_data(n):
    # Setting the seed
    Faker.seed(SEED)
    random.seed(SEED)

    # Settign Minimum Bounds
    MIN_HOME_PRICE = 100000
    MIN_COL_PRICE = 100

    # Setting Maximum Bounds
    MAX_HOME_PRICE = 1000000
    MIN_HOME_PRICE = 10000

    # Setting fake dataset
    dummy_data = Faker(["en_US"])
    names = [dummy_data.company() for _ in range(n)]
    zipcodes = [dummy_data.zipcode() for _ in range(n)]
    home_price_change = [
        random.randint(MIN_HOME_PRICE, MAX_HOME_PRICE) for _ in range(n)
    ]
    cost_of_living_change = [
        random.randint(MIN_COL_PRICE, MAX_HOME_PRICE) for _ in range(n)
    ]

    testing_data = pd.DataFrame(
        {
            "Name": names,
            "Zip Code": zipcodes,
            "Home Price Change": home_price_change,
            "Cost of Living Change": cost_of_living_change,
        }
    )

    return testing_data


# dummy_set = make_data(20)
# dummy_set.to_csv(OUTPATH)

# Testing the composite method
def test_scoring_composite():

    # Creating Dataset
    dummy_set = make_data(20)

    # Testing scores for Home Price Changes
    scoring(dummy_set, "Home Price Change")

    assert dummy_set.iloc[0]["Home Price Change_score"] == 6
    assert dummy_set.iloc[1]["Home Price Change_score"] == 5
    assert dummy_set.iloc[4]["Home Price Change_score"] == 10
    assert dummy_set.iloc[11]["Home Price Change_score"] == 8

    # Testing scores for Cost of Living Changes
    scoring(dummy_set, "Cost of Living Change")

    assert dummy_set.iloc[0]["Cost of Living Change_score"] == 7
    assert dummy_set.iloc[1]["Cost of Living Change_score"] == 3
    assert dummy_set.iloc[6]["Cost of Living Change_score"] == 6
    assert dummy_set.iloc[19]["Cost of Living Change_score"] == 2

def test_scoring_z():

    # Creating Dataset 
    dummy_set = make_data(20)

    # Testing z-scores for Home Price Changes
    scoring(dummy_set, "Home Price Change",method = "z-score")
    
    assert dummy_set.iloc[0]["Home Price Change_z_score"] == pytest.approx(0.521080127,abs=1e-6)
    assert dummy_set.iloc[2]["Home Price Change_z_score"] == pytest.approx(-1.384384169,abs=1e-6)
    assert dummy_set.iloc[9]["Home Price Change_z_score"] == pytest.approx(0.900714387,abs=1e-6)
    assert dummy_set.iloc[18]["Home Price Change_z_score"] == pytest.approx(0.546306918,abs=1e-6)

    # Testing z-scores for Cost of Living Changes
    scoring(dummy_set, "Cost of Living Change",method = "z-score")

    # Testing z-scores for Cost of Living Changes
    assert dummy_set.iloc[0]["Cost of Living Change_z_score"] == pytest.approx(0.103753224,abs=1e-6)
    assert dummy_set.iloc[10]["Cost of Living Change_z_score"] == pytest.approx(2.049777643,abs=1e-6)
    assert dummy_set.iloc[11]["Cost of Living Change_z_score"] == pytest.approx(-0.490012321,abs=1e-6)
    assert dummy_set.iloc[17]["Cost of Living Change_z_score"] == pytest.approx(1.500362168,abs=1e-6)
