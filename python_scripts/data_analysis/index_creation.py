import pandas as pd
from pathlib import Path
from index import scoring, index

FILEPATH = Path(__file__).parent / "chicago_data_centers_final.csv"
OUTPATH = Path(__file__).parent / "chicag_data_centers_impact_scores.csv"

variables = ["Housing_Change", "HC_Score_Change"]

# Importing dataset of Chicagoland Data Centers
chicago_data_centers = pd.read_csv(FILEPATH)

for variable in variables:
    # Composite Scoring Method
    scoring(chicago_data_centers, variable, method="composite")
    # Z-Scoring Method
    scoring(chicago_data_centers, variable, method="z-score")

# Creating impact index
mask = chicago_data_centers["Complete"] == 1

chicago_data_centers.loc[mask, "impact_score"] = index(
    chicago_data_centers[mask].copy(), method="composite"
)
chicago_data_centers.loc[mask, "impact_z_score"] = index(
    chicago_data_centers[mask].copy(), method="z-score"
)

# Exporting
chicago_data_centers.to_csv(OUTPATH)
