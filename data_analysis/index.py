import pandas as pd

# Data Analysis
# We will create index as an indicator of affordability. Zip codes with
# more data centers, higher average electricity and water prices, and 
# home prices will have a higher index, and thus be less affordable and more
# at risk of pricing out residents of the region

# Importing our MOCK DATA as a pandas dataframe

data_centers = pd.read_csv("/home/lburton12/capp30122/data_centers_next_door/project-datacenter-urban-effects/data_analysis/top_10_us_cities_datacenters_augmented_mock.csv")

# Calculating the unique counts of data centers by zip codes
unique_data_centers = data_centers.groupby("zip_code")["facility"].nunique().reset_index().rename(columns = {"facility":"facility_count"})

# Left joining this onto data_centers dataset
data_centers = pd.merge(data_centers,unique_data_centers,on = "zip_code")
print(data_centers.head())

# NOTE: PROBABLY WANT TO NORMALIZE THIS FACILITY SCORE BY PER CAPITA, SO AS TO 
# NOT OVERINFLATE. WE COULD PROBABLY ALSO USE POPULATION TO SEE HOW MANY PEOPLE
# WILL BE AFFECTED BY AN ADDITION OF A DATA CENTER

# Index creation
def score_creation(variable):
    """
    Takes a variable and calculates a "ranking" based on its decile value
    
    Inputs:
           dataset: a pandas dataframe
           varaible: the variable by which we are calculating scores for
    """
    score_name = f"{variable}_score"

    data_centers[score_name] = pd.qcut(data_centers[variable],
                                       q = 10,
                                       labels = False)
    
score_creation("avg_electricity_cost_usd_per_kwh")
score_creation("avg_home_price_usd")
score_creation("avg_water_cost_usd_monthly")

print(data_centers.head())

# Creating the index score based on weights. The weights MUST add to 1!
def weights(facility_weight,home_weight,electricity_weight,water_weight):

    if facility_weight + home_weight + electricity_weight + water_weight != 1:
        raise ValueError("Weights must add up 100")
    
    weights = {"facility_weight": facility_weight,
               "home_price_weight": home_weight,
               "electricity_price_weight": electricity_weight,
               "water_price_weight": water_weight}
    
    





