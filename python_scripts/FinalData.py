import geopandas as gpd
import pandas as pd
import numpy as np
import os
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler

# 1. Load data
input_path = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'
gdf = gpd.read_file(input_path)

gdf = gdf.replace("", pd.NA)

selected_columns = [
    'avg_price_2021', 'avg_price_2022', 'avg_price_2023', 'avg_price_2024',
    'comm_rate_2021', 'comm_rate_2022', 'comm_rate_2023', 'comm_rate_2024',
    'ind_rate_2021',  'ind_rate_2022',  'ind_rate_2023',  'ind_rate_2024',
    'pct_change_2021','pct_change_2022','pct_change_2023','pct_change_2024',
    'res_rate_2021',  'res_rate_2022',  'res_rate_2023',  'res_rate_2024',
]

for col in selected_columns:
    gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

# ---------------------------------------------------
# 2. DROP cities with ANY column > 20% missing
# ---------------------------------------------------
missing_pct = (
    gdf
    .groupby("city_label")[selected_columns]
    .apply(lambda x: x.isna().mean() * 100)
)

cities_to_drop = missing_pct[(missing_pct > 20).any(axis=1)].index
print("Dropping cities due to >20% missing:")
print(cities_to_drop.tolist())

gdf_clean = gdf[~gdf["city_label"].isin(cities_to_drop)].copy()

# ---------------------------------------------------
# 3. KNN IMPUTATION — row-level + feature scaling
#
#    BUG 1 (fixed earlier): subsetting to city_label + numerics
#    then merging back on city_label flattened all ZIP variation.
#
#    BUG 2 (fixed here): running KNN on raw unscaled values means
#    avg_price (100,000s) completely dominates neighbor selection
#    over rates (single digits). The imputer ignores rate columns
#    when finding neighbors, so imputed rate values collapse to
#    near-identical numbers across all ZIPs.
#
#    FIX: StandardScaler before imputing so every column
#    contributes equally to neighbor distance calculation.
#    Inverse transform restores original units afterward.
# ---------------------------------------------------
scaler = StandardScaler()
scaled = scaler.fit_transform(gdf_clean[selected_columns])

imputer = KNNImputer(n_neighbors=5)
imputed_scaled = imputer.fit_transform(scaled)

# Restore original units
gdf_clean[selected_columns] = scaler.inverse_transform(imputed_scaled)

# ---------------------------------------------------
# 4. Normalize city names
# ---------------------------------------------------
gdf_clean["city_label"] = (
    gdf_clean["city_label"]
    .str.lower()
    .str.strip()
    .str.replace("_", " ", regex=False)
)

# ---------------------------------------------------
# 5. SIMPLIFY GEOMETRY
# ---------------------------------------------------
print("\nSimplifying geometry...")
original_crs = gdf_clean.crs
gdf_clean = gdf_clean.to_crs(epsg=3857)
gdf_clean["geometry"] = gdf_clean.simplify(tolerance=200, preserve_topology=True)
gdf_clean = gdf_clean.to_crs(original_crs)

# ---------------------------------------------------
# 6. KEEP ONLY ESSENTIAL COLUMNS
# ---------------------------------------------------
essential_columns = [
    "city_label", "ZCTA5CE20", "geometry",
    "avg_price_2021", "avg_price_2022", "avg_price_2023", "avg_price_2024",
    "comm_rate_2021", "comm_rate_2022", "comm_rate_2023", "comm_rate_2024",
    "ind_rate_2021",  "ind_rate_2022",  "ind_rate_2023",  "ind_rate_2024",
    "pct_change_2021","pct_change_2022","pct_change_2023","pct_change_2024",
    "res_rate_2021",  "res_rate_2022",  "res_rate_2023",  "res_rate_2024",
]
existing_cols = [c for c in essential_columns if c in gdf_clean.columns]
gdf_clean = gdf_clean[existing_cols]

# ---------------------------------------------------
# Sanity check — confirm variation is preserved
# ---------------------------------------------------
print("\n--- Sanity check (atlanta) ---")
atl = gdf_clean[gdf_clean["city_label"] == "atlanta"]
for col in ["avg_price_2021", "comm_rate_2021", "res_rate_2021"]:
    if col in atl.columns:
        print(f"  {col}: {atl[col].nunique()} unique vals | "
              f"min={atl[col].min():.4f} max={atl[col].max():.4f}")

os.makedirs("shiny_app/Data", exist_ok=True)
output_path = "shiny_app/Data/cities_clean_imputed.gpkg"
gdf_clean.to_file(output_path, driver="GPKG")

final_size = os.path.getsize(output_path) / (1024 * 1024)
print(f"\nSaved to {output_path} ({final_size:.2f} MB)")

# ---------------------------------------------------
# 7. FILTER & SAVE DATA CENTERS
# ---------------------------------------------------
data_centers = gpd.read_file(
    "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/centers/DataCenters.shp"
)

keep_dc_cols = [col for col in ["id", "name", "city_in_de", "geometry"] if col in data_centers.columns]
data_centers = data_centers[keep_dc_cols]
data_centers["city_in_de"] = data_centers["city_in_de"].str.lower().str.strip()

valid_cities = gdf_clean["city_label"].unique()
data_centers_filtered = data_centers[data_centers["city_in_de"].isin(valid_cities)].copy()

output_dc_path = "shiny_app/Data/DataCenters_clean.gpkg"
data_centers_filtered.to_file(output_dc_path, driver="GPKG")
print(f"Saved DataCenters: {len(data_centers_filtered)} records")
