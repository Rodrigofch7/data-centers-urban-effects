import pandas as pd
import random
import pytest
from pathlib import Path
from faker import Faker
from data_centers_next_door.data_analysis.index import scoring,index

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
            "Housing_Change": home_price_change,
            "HC_Score_Change": cost_of_living_change,
        }
    )

    return testing_data

# Testing the composite method
def test_scoring_composite():

    # Creating Dataset
    dummy_set = make_data(20)

    # Testing scores for Home Price Changes
    scoring(dummy_set, "Housing_Change")

    assert dummy_set.iloc[0]["Housing_Change_score"] == 6
    assert dummy_set.iloc[1]["Housing_Change_score"] == 5
    assert dummy_set.iloc[4]["Housing_Change_score"] == 10
    assert dummy_set.iloc[11]["Housing_Change_score"] == 8

    # Testing scores for Cost of Living Changes
    scoring(dummy_set, "HC_Score_Change")

    assert dummy_set.iloc[0]["HC_Score_Change_score"] == 7
    assert dummy_set.iloc[1]["HC_Score_Change_score"] == 3
    assert dummy_set.iloc[6]["HC_Score_Change_score"] == 6
    assert dummy_set.iloc[19]["HC_Score_Change_score"] == 2

def test_scoring_z():

    # Creating Dataset 
    dummy_set = make_data(20)

    # Testing z-scores for Home Price Changes
    scoring(dummy_set, "Housing_Change",method = "z-score")
    
    assert dummy_set.iloc[0]["Housing_Change_z_score"] == pytest.approx(0.521080127,abs=1e-6)
    assert dummy_set.iloc[2]["Housing_Change_z_score"] == pytest.approx(-1.384384169,abs=1e-6)
    assert dummy_set.iloc[9]["Housing_Change_z_score"] == pytest.approx(0.900714387,abs=1e-6)
    assert dummy_set.iloc[18]["Housing_Change_z_score"] == pytest.approx(0.546306918,abs=1e-6)

    # Testing z-scores for Cost of Living Changes
    scoring(dummy_set, "HC_Score_Change",method = "z-score")

    # Testing z-scores for Cost of Living Changes
    assert dummy_set.iloc[0]["HC_Score_Change_z_score"] == pytest.approx(0.103753224,abs=1e-6)
    assert dummy_set.iloc[10]["HC_Score_Change_z_score"] == pytest.approx(2.049777643,abs=1e-6)
    assert dummy_set.iloc[11]["HC_Score_Change_z_score"] == pytest.approx(-0.490012321,abs=1e-6)
    assert dummy_set.iloc[17]["HC_Score_Change_z_score"] == pytest.approx(1.500362168,abs=1e-6)

def test_index_score_50_50_comp():

    # Creating Dataset and getting scores
    dummy_set = make_data(20)
    scoring(dummy_set, "Housing_Change")
    scoring(dummy_set, "HC_Score_Change")

    # Getting index 
    dummy_set["impact_score"] = index(dummy_set, method="composite")

    assert dummy_set.iloc[0]["impact_score"] == 6.5
    assert dummy_set.iloc[2]["impact_score"] == 6
    assert dummy_set.iloc[10]["impact_score"] == 5.5
    assert dummy_set.iloc[16]["impact_score"] == 2

def test_index_score_50_50_z():

    # Creating Dataset and getting scores
    dummy_set = make_data(20)
    scoring(dummy_set, "Housing_Change", method="z-score")
    scoring(dummy_set, "HC_Score_Change",method="z-score")

    # Getting index 
    dummy_set["impact_score"] = index(dummy_set, method="z-score")

    assert dummy_set.iloc[0]["impact_score"] == pytest.approx(0.312416676,abs=1e-6)
    assert dummy_set.iloc[6]["impact_score"] == pytest.approx(-0.242809051,abs=1e-6)
    assert dummy_set.iloc[8]["impact_score"] == pytest.approx(0.510302467,abs=1e-6)
    assert dummy_set.iloc[16]["impact_score"] == pytest.approx(-0.995862921,abs=1e-6)

def test_index_score_70_30_comp():

    # Creating Dataset and getting scores
    dummy_set = make_data(20)
    scoring(dummy_set, "Housing_Change")
    scoring(dummy_set, "HC_Score_Change")

    # Getting index 
    dummy_set["impact_score"] = index(dummy_set,
                                      housing_weight=.70,
                                      HC_weight=.30,
                                      method="composite")

    assert dummy_set.iloc[0]["impact_score"] == pytest.approx(6.3,abs=1e-6)
    assert dummy_set.iloc[2]["impact_score"] == pytest.approx(4.4,abs=1e-6)
    assert dummy_set.iloc[10]["impact_score"] == pytest.approx(3.7,abs=1e-6)
    assert dummy_set.iloc[16]["impact_score"] == pytest.approx(2,abs=1e-6)