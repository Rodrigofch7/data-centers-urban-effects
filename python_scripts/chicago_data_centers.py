import pandas as pd

# Loading the dataset:
datacenters = pd.read_csv("data/top_us_cities_datacenters.csv")

# Filtering only rows where scraped_city is Chicago:
chicago_dc = datacenters[datacenters["scraped_city"] == "Chicago"].copy()

# Addding a new column called "first_permit":
chicago_dc["first_permit"] = ""

# Saving to a new CSV file
chicago_dc.to_csv("data/chicago_data_centers.csv", index=False)

# Printing result:
print(chicago_dc.head())