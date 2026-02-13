import geopandas as gpd
import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer

# 1. Load data (keep geometry!)
gdf = gpd.read_file(
    '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'
)

gdf = gdf.replace("", pd.NA)

selected_columns = [
    'avg_price_2021', 'avg_price_2022', 'avg_price_2023', 'avg_price_2024',
    'comm_rate_2021', 'comm_rate_2022', 'comm_rate_2023', 'comm_rate_2024',
    'ind_rate_2021', 'ind_rate_2022', 'ind_rate_2023', 'ind_rate_2024',
    'pct_change_2021', 'pct_change_2022', 'pct_change_2023', 'pct_change_2024',
    'res_rate_2021', 'res_rate_2022', 'res_rate_2023', 'res_rate_2024'
]

# Create working subset WITHOUT dropping geometry from original gdf
gdf_subset = gdf[["city_label"] + selected_columns].copy()

# ---------------------------------------------------
# 2. DROP cities with ANY column > 20% missing
# ---------------------------------------------------

missing_pct = (
    gdf_subset
    .groupby("city_label")
    .apply(lambda x: x.isna().mean() * 100)
)

cities_to_drop = missing_pct[
    (missing_pct > 20).any(axis=1)
].index

print("Dropping these cities due to >20% missing:")
print(cities_to_drop.tolist())

gdf_clean = gdf_subset[
    ~gdf_subset["city_label"].isin(cities_to_drop)
].copy()

# ---------------------------------------------------
# 3. KNN IMPUTATION
# ---------------------------------------------------

imputer = KNNImputer(n_neighbors=5)

numeric_data = gdf_clean[selected_columns]
imputed_array = imputer.fit_transform(numeric_data)

gdf_clean[selected_columns] = imputed_array

print("\nRemaining missing values:")
print(gdf_clean[selected_columns].isna().sum())

# ---------------------------------------------------
# 4. MERGE BACK INTO ORIGINAL GEODATAFRAME
# ---------------------------------------------------

gdf_final = gdf[
    ~gdf["city_label"].isin(cities_to_drop)
].copy()

gdf_final = gdf_final.drop(columns=selected_columns)

gdf_final = gdf_final.merge(
    gdf_clean,
    on="city_label",
    how="left"
)

# ---------------------------------------------------
# 5. SAVE FILE
# ---------------------------------------------------

gdf_final.to_file(
    "spatial_data/cities_clean_imputed.gpkg",
    driver="GPKG"
)

print("Saved as spatial_data/cities_clean_imputed.gpkg")


# ---------------------------------------------------
# 6. FILTER DATA CENTERS TO MATCH CLEAN CITIES
# ---------------------------------------------------

# Load data centers shapefile
data_centers = gpd.read_file(
    "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/centers/DataCenters.shp"
)

# Keep only cities that survived cleaning
valid_cities = gdf_final["city_label"].unique()

# IMPORTANT:
# Make sure the column in DataCenters that identifies the city
# is named correctly. Replace 'city_label' below if needed.

data_centers_filtered = data_centers[
    data_centers["city_in_de"].isin(valid_cities)
].copy()

# ---------------------------------------------------
# 7. SAVE AS GEOPACKAGE
# ---------------------------------------------------

data_centers_filtered.to_file(
    "spatial_data/DataCenters_clean.gpkg",
    driver="GPKG"
)

print("Saved filtered DataCenters_clean.gpkg")
