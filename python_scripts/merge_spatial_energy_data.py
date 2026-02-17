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
# 2. Standardize join keys
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
# 3. Pivot numeric data — one row per ZIP × year
#    combination, keeping ALL utility rows intact.
#
#    OLD BUG: aggfunc="mean" collapsed all utilities
#    into a single average per ZIP, destroying the
#    per-utility rate variation before the spatial join.
#
#    FIX: pivot on zip + utility_name so each utility
#    keeps its own row, then spread years into columns.
# ─────────────────────────────────────────────
df_pivoted = data.pivot_table(
    index=["zip", "utility_name", "state", "ownership", "service_type"],
    columns="year",
    values=["avg_price", "pct_change", "comm_rate", "ind_rate", "res_rate"],
    aggfunc="first",   # one value per zip × utility × year — no averaging
)

# Flatten multi-index columns
df_pivoted.columns = [
    f"{metric}_{int(year)}" for metric, year in df_pivoted.columns
]
df_pivoted = df_pivoted.reset_index()

# ─────────────────────────────────────────────
# 4. Master merge — cities geometry on the left,
#    all utility rows on the right (many-to-one on ZIP)
# ─────────────────────────────────────────────
merged_gdf = cities.merge(
    df_pivoted,
    left_on="NAME20",
    right_on="zip",
    how="left"
)

# ─────────────────────────────────────────────
# 5. Cleanup
# ─────────────────────────────────────────────
merged_gdf = merged_gdf.loc[:, ~merged_gdf.columns.duplicated()]
merged_gdf.drop(columns=["zip"], errors="ignore", inplace=True)

# Sanity check before saving
print(f"Total rows in output : {len(merged_gdf)}")
atl = merged_gdf[merged_gdf["city_label"].str.lower().str.strip() == "atlanta"]
print(f"Atlanta rows         : {len(atl)}")
for col in ["comm_rate_2021", "res_rate_2021", "avg_price_2021"]:
    if col in atl.columns:
        vals = pd.to_numeric(atl[col], errors="coerce")
        print(f"  {col}: {vals.nunique()} unique | min={vals.min():.4f} max={vals.max():.4f}")

# ─────────────────────────────────────────────
# 6. Save
# ─────────────────────────────────────────────
output_path = (
    "/home/rodrigofrancachaves/capp30122/"
    "group_project/project-datacenter-urban-effects/"
    "spatial_data/cities/cities_with_energy_home_prices.geojson"
)

merged_gdf.to_file(output_path, driver="GeoJSON")
print("\nDone. Saved to", output_path)
