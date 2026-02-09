import pandas as pd
import geopandas as gpd

# ─────────────────────────────────────────────
# 1. Load data
# ─────────────────────────────────────────────
data = pd.read_csv("data/ZillowEnergy.csv")
cities = gpd.read_file(
    "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/combined_cities.shp"
)

# ─────────────────────────────────────────────
# 2. Standardize join keys (ONCE)
#    Strip whitespace + remove leading zeros only
# ─────────────────────────────────────────────
data["zip"] = (
    data["zip"]
    .astype(str)
    .str.strip()
    .str.lstrip("0")
)

cities["NAME20"] = (
    cities["NAME20"]
    .astype(str)
    .str.strip()
    .str.lstrip("0")
)

# ─────────────────────────────────────────────
# 3. Pivot numeric data
# ─────────────────────────────────────────────
df_pivoted = data.pivot_table(
    index="zip",
    columns="year",
    values=["avg_price", "pct_change", "comm_rate", "ind_rate", "res_rate"],
    aggfunc="mean"
)

# Flatten multi-index columns
df_pivoted.columns = [
    f"{metric}_{int(year)}" for metric, year in df_pivoted.columns
]

# ─────────────────────────────────────────────
# 4. Extract metadata (one row per ZIP)
# ─────────────────────────────────────────────
metadata = (
    data.groupby("zip", as_index=False)
    .agg({
        "state": "first",
        "utility_name": "first",
        "ownership": "first",
        "service_type": "first"
    })
)

# ─────────────────────────────────────────────
# 5. Combine metadata + pivoted data
# ─────────────────────────────────────────────
df_final = metadata.merge(df_pivoted, on="zip", how="inner")

# ─────────────────────────────────────────────
# 6. Master merge (cities on the left)
# ─────────────────────────────────────────────
merged_gdf = cities.merge(
    df_final,
    left_on="NAME20",
    right_on="zip",
    how="left"
)

# ─────────────────────────────────────────────
# 7. Cleanup duplicated columns & index
# ─────────────────────────────────────────────
merged_gdf = merged_gdf.loc[:, ~merged_gdf.columns.duplicated()]

merged_gdf.set_index("city_label", inplace=True)

merged_gdf.drop(columns=["zip"], errors="ignore", inplace=True)

# ─────────────────────────────────────────────
# 8. Save
# ─────────────────────────────────────────────
output_path = (
    "/home/rodrigofrancachaves/capp30122/"
    "group_project/project-datacenter-urban-effects/"
    "spatial_data/cities/cities_with_energy_home_prices.geojson"
)

merged_gdf.to_file(output_path, driver="GeoJSON")

print("Process complete.")
print("No duplicated columns. Index set to 'city_label'.")
