import pandas as pd
from pathlib import Path


# Data Analysis
# We will create index as the impact on housing and cost of living prices
# following building of a datacenter within the zipcode. The index will
# be constructed using the change in housing prices and cost of living
# prices pre-data center permit and post-data center permitting.


# SCORING
def scoring(dataset, variable, method="composite"):
    """
    Takes a variable and calculates a "ranking" based on its decile value or its
    corresponding z-score. Each method has their distinct advantages and disadvantages
    and be adjust as such. Default method will be the composite/quantile method

    Inputs:
           variable: a pandas dataframe variable by which we are calculating scores for
    """
    if method not in {"composite", "z-score"}:
        raise ValueError("Method must be 'composite' or 'z-score'!")

    if method == "composite":
        score_name = f"{variable}_score"

        dataset[score_name] = pd.qcut(dataset[variable], q=10, labels=False) + 1

    elif method == "z-score":
        z_score_name = f"{variable}_z_score"

        dataset[z_score_name] = (dataset[variable] - dataset[variable].mean()) / dataset[
            variable
        ].std()


# Creating the index score based on weights. The weights MUST add to 1!
def index(dataset, housing_weight=0.50, HC_weight=0.50, method="composite"):
    """
    Creates a composite index score for a zip code based on selected weights

    Inputs:
           facility_weight: The weight assigned to number of data center facilities
           home_weight: The weight assigned to the ranking of average housing costs
           electricity_weight: The weight assigned to the ranking of electricity costs
           water_weight: The weight assigned to the ranking of water usage costs
    """
    if housing_weight + HC_weight != 1:
        raise ValueError("Weights must add up 1")

    weights = {"housing weight": housing_weight, "cost of living weight": HC_weight}

    if method == "composite":
        return (dataset["HC_Score_Change_score"] * weights["cost of living weight"]) + (
            dataset["Housing_Change_score"] * weights["housing weight"]
        )

    elif method == "z-score":
        return (dataset["HC_Score_Change_z_score"] * weights["cost of living weight"]) + (
            dataset["Housing_Change_z_score"] * weights["housing weight"]
        )
