import pandas as pd
import random
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

    #Settign Minimum Bounds
    MIN_HOME_PRICE = 100000
    MIN_COL_PRICE = 100

    #Setting Maximum Bounds
    MAX_HOME_PRICE = 1000000
    MIN_MAX_PRICE = 10000

    #Setting fake dataset 
    dummy_data = Faker(["en_US"])
    names = [dummy_data.company() for _ in range(n)]
    zipcodes = [dummy_data.zipcode() for _ in range(n)]
    home_price_change = [random.randint(MIN_HOME_PRICE,MAX_HOME_PRICE) for _ in range(n)]
    cost_of_living_change = [random.randint(MIN_COL_PRICE,MAX_HOME_PRICE) for _ in range(n)]

    testing_data = pd.DataFrame({"Name":names,
                                 "Zip Code":zipcodes,
                                 "Home Price Change":home_price_change,
                                 "Cost of Living Change":cost_of_living_change})

    return testing_data

dummy_set = make_data(20)
# dummy_set.to_csv(OUTPATH)

# Testing scoring()
def test_scoring_composite():

    #Creating Dataset
    dummy_set = make_data(20)
    
    #Scoring
    scoring(dummy_set,"Home Price Change")

    #Testing scores for Home Price Changes
    assert dummy_set.iloc[0]["Home Price Change_score"] == 7
    assert dummy_set.iloc[1]["Home Price Change_score"] == 5
    assert dummy_set.iloc[4]["Home Price Change_score"] == 1
    assert dummy_set.iloc[19]["Home Price Change_score"] == 6

    #Testing scores for Cost of Living Changes
    scoring(dummy_set,"Cost of Living Change")

test_scoring_composite()







    
