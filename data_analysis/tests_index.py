import pandas as pd
import random
from pathlib import Path
from faker import Faker
from index import scoring

# Setting the seed
Faker.seed(2026)

# Setting fixture dataset
def test_data(n):

    #Settign Minimum Bounds
    MIN_HOME_PRICE = 100000
    MIN_WATER_PRICE = 1
    MIN_ELECTRICITY_PRICE = 1

    #Setting Maximum Bounds
    MAX_HOME_PRICE = 1000000
    MAX_WATER_PRICE = 4
    MAX_ELECTRICITY_PRICE = 4   

    #Setting fake dataset 
    dummy_data = Faker(["en_US"])
    names = [dummy_data.company() for _ in range(n)]
    zipcodes = [dummy_data.zipcode() for _ in range(n)]
    avg_home_price_usd = [random.randint(MIN_HOME_PRICE,MAX_HOME_PRICE) for _ in range(n)]
    electricity_change = [random.randint(MIN_ELECTRICITY_PRICE,MAX_ELECTRICITY_PRICE) for _ in range(n)]
    water_change = [random.randint(MIN_WATER_PRICE,MAX_WATER_PRICE) for _ in range(n)] 

    testing_data = pd.DataFrame({"Name":names,
                                 "Zip Code":zipcodes,
                                 "Home Prices": avg_home_price_usd,
                                 "Electricity Change":electricity_change,
                                 "Water Change":water_change})

    return testing_data

dummy_set = test_data(20)
print(dummy_set)    





    
