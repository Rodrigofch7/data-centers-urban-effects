import geopandas as gpd
import pandas as pd
import numpy as np
import os
from sklearn.impute import KNNImputer

# 1. Load data (keep geometry!)
input_path = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'
gdf = gpd.read_file(input_path)

# Replace empty strings with NA
gdf = gdf.replace("", pd.NA)

# Numeric columns you actually need in the app
selected_columns = [
    'avg_price_2021', 'avg_price_2022', 'avg_price_2023', 'avg_price_2024',
    'comm_rate_2021', 'comm_rate_2022', 'comm_rate_2023', 'comm_rate_2024',
    'ind_rate_2021', 'ind_rate_2022', 'ind_rate_2023', 'ind_rate_2024',
    'pct_change_2021', 'pct_change_2022', 'pct_change_2023', 'pct_change_2024',
    'res_rate_2021', 'res_rate_2022', 'res_rate_2023', 'res_rate_2024'
]

# Work only with city_label + numeric columns
gdf_subset = gdf[["city_label"] + selected_columns].copy()

# ---------------------------------------------------
# 2. DROP cities with ANY column > 20% missing
# ---------------------------------------------------
missing_pct = (
    gdf_subset
    .groupby("city_label")
    .apply(lambda x: x.isna().mean() * 100)
)

cities_to_drop = missing_pct[(missing_pct > 20).any(axis=1)].index

print("Dropping these cities due to >20% missing:")
print(cities_to_drop.tolist())

gdf_clean = gdf_subset[~gdf_subset["city_label"].isin(cities_to_drop)].copy()

# ---------------------------------------------------
# 3. KNN IMPUTATION
# ---------------------------------------------------
imputer = KNNImputer(n_neighbors=5)
numeric_data = gdf_clean[selected_columns]
imputed_array = imputer.fit_transform(numeric_data)
gdf_clean[selected_columns] = imputed_array

# ---------------------------------------------------
# 4. MERGE BACK (but then drop non‑essentials)
# ---------------------------------------------------
gdf_final = gdf[~gdf["city_label"].isin(cities_to_drop)].copy()

# Drop original numeric columns to avoid duplication
gdf_final = gdf_final.drop(columns=selected_columns, errors="ignore")

# Merge imputed numeric columns back
gdf_final = gdf_final.merge(gdf_clean, on="city_label", how="left")

# Normalize city names
gdf_final["city_label"] = (
    gdf_final["city_label"]
    .str.lower()
    .str.strip()
    .str.replace("_", " ", regex=False)
)

# ---------------------------------------------------
# 5. STRIP MOST ATTRIBUTES + SIMPLIFY GEOMETRY
# ---------------------------------------------------
print("\nSimplifying geometry to reduce file size...")
original_crs = gdf_final.crs

# Project to meters to use meter-based tolerance
gdf_final = gdf_final.to_crs(epsg=3857)

# Increase tolerance to simplify more (adjust if too coarse)
gdf_final["geometry"] = gdf_final.simplify(tolerance=200, preserve_topology=True)

# Project back
gdf_final = gdf_final.to_crs(original_crs)

# Keep only essential columns for app & joins
essential_columns = [
    "city_label",
    "geometry",
    "avg_price_2021", "avg_price_2022", "avg_price_2023", "avg_price_2024",
    "comm_rate_2021", "comm_rate_2022", "comm_rate_2023", "comm_rate_2024",
    "ind_rate_2021", "ind_rate_2022", "ind_rate_2023", "ind_rate_2024",
    "pct_change_2021", "pct_change_2022", "pct_change_2023", "pct_change_2024",
    "res_rate_2021", "res_rate_2022", "res_rate_2023", "res_rate_2024",
]
existing_cols = [c for c in essential_columns if c in gdf_final.columns]
gdf_final = gdf_final[existing_cols]

# Save and check size
os.makedirs("shiny_app/Data", exist_ok=True)
output_city_path = "shiny_app/Data/cities_clean_imputed_simpler.gpkg"
gdf_final.to_file(output_city_path, driver="GPKG")

final_size = os.path.getsize(output_city_path) / (1024 * 1024)
print(f"Success! Final city file size: {final_size:.2f} MB")

# ---------------------------------------------------
# 6. FILTER & MINIMIZE DATA CENTERS
# ---------------------------------------------------
data_centers = gpd.read_file(
    "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/centers/DataCenters.shp"
)

# Keep only minimal fields (adjust list as needed)
keep_dc_cols = [
    col for col in ["id", "name", "city_in_de", "geometry"] if col in data_centers.columns
]
data_centers = data_centers[keep_dc_cols]

# Normalize names to match city_label
data_centers["city_in_de"] = data_centers["city_in_de"].str.lower().str.strip()

valid_cities = gdf_final["city_label"].unique()
data_centers_filtered = data_centers[data_centers["city_in_de"].isin(valid_cities)].copy()

# Save minimal DataCenters file
output_dc_path = "shiny_app/Data/DataCenters_clean_minimal.gpkg"
data_centers_filtered.to_file(output_dc_path, driver="GPKG")

print(f"Saved filtered DataCenters: {len(data_centers_filtered)} records remaining.")
