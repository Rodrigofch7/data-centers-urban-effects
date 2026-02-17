import geopandas as gpd
import pandas as pd
import numpy as np
import os
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler
from census import Census

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY = "fda60e79b0da81a8ac6472ff4250f47daa8c527b"
ACS_YEAR = 2022

INPUT_PATH      = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'
DC_INPUT_PATH   = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/centers/DataCenters.shp'
OUTPUT_CITIES   = 'shiny_app/Data/cities_clean_imputed.gpkg'
OUTPUT_CENTERS  = 'shiny_app/Data/DataCenters_clean.gpkg'
SIZE_LIMIT_MB   = 100
# ─────────────────────────────────────────────────────────────────────────────

ENERGY_COLUMNS = [
    'avg_price_2021', 'avg_price_2022', 'avg_price_2023', 'avg_price_2024',
    'comm_rate_2021', 'comm_rate_2022', 'comm_rate_2023', 'comm_rate_2024',
    'ind_rate_2021',  'ind_rate_2022',  'ind_rate_2023',  'ind_rate_2024',
    'pct_change_2021','pct_change_2022','pct_change_2023','pct_change_2024',
    'res_rate_2021',  'res_rate_2022',  'res_rate_2023',  'res_rate_2024',
]

ACS_VARIABLES = {
    "B01003_001E": "pop_total",
    "B01002_001E": "median_age",
    "B19013_001E": "median_hh_income",
    "B25077_001E": "median_home_value",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    "B28002_004E": "broadband_subs",
    "B11001_001E": "total_households",
    "B17001_002E": "pop_below_poverty",
    "B19083_001E": "gini_index",
    "B23025_005E": "unemployed",
    "B23025_002E": "labor_force",
    "B02001_003E": "pop_black",
    "B02001_005E": "pop_asian",
    "B03003_003E": "pop_hispanic",
}

# =============================================================================
# STEP 1 — Load & clean energy/price data
# =============================================================================
print("=" * 60)
print("STEP 1: Loading source GeoJSON")
print("=" * 60)
gdf = gpd.read_file(INPUT_PATH)
gdf = gdf.replace("", pd.NA)

for col in ENERGY_COLUMNS:
    gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

# =============================================================================
# STEP 2 — Drop cities with >20% missing
# =============================================================================
print("\nSTEP 2: Dropping cities with >20% missing data")
missing_pct = (
    gdf.groupby("city_label")[ENERGY_COLUMNS]
    .apply(lambda x: x.isna().mean() * 100)
)
cities_to_drop = missing_pct[(missing_pct > 20).any(axis=1)].index
print(f"  Dropping: {cities_to_drop.tolist()}")
gdf_clean = gdf[~gdf["city_label"].isin(cities_to_drop)].copy()

# =============================================================================
# STEP 3 — KNN imputation with StandardScaler
# =============================================================================
print("\nSTEP 3: KNN imputation (scaled)")
scaler  = StandardScaler()
imputer = KNNImputer(n_neighbors=5)
scaled          = scaler.fit_transform(gdf_clean[ENERGY_COLUMNS])
imputed_scaled  = imputer.fit_transform(scaled)
gdf_clean[ENERGY_COLUMNS] = scaler.inverse_transform(imputed_scaled)

# =============================================================================
# STEP 4 — Normalize city names
# =============================================================================
gdf_clean["city_label"] = (
    gdf_clean["city_label"]
    .str.lower().str.strip()
    .str.replace("_", " ", regex=False)
)

# =============================================================================
# STEP 5 — Fetch ACS5 census data and merge
# =============================================================================
print("\nSTEP 4: Fetching ACS5 census data")
c = Census(API_KEY, year=ACS_YEAR)
results = c.acs5.get(
    ["NAME"] + list(ACS_VARIABLES.keys()),
    {"for": "zip code tabulation area:*"}
)
census_df = (
    pd.DataFrame(results)
    .rename(columns={"zip code tabulation area": "ZCTA5CE20"})
    .rename(columns=ACS_VARIABLES)
    .drop(columns=["NAME"], errors="ignore")
)
for col in ACS_VARIABLES.values():
    census_df[col] = pd.to_numeric(census_df[col], errors="coerce")

# Derived variables
census_df["pct_broadband"]     = (census_df["broadband_subs"]   / census_df["total_households"] * 100).round(2)
census_df["pct_below_poverty"] = (census_df["pop_below_poverty"] / census_df["pop_total"]        * 100).round(2)
census_df["unemployment_rate"] = (census_df["unemployed"]        / census_df["labor_force"]      * 100).round(2)
census_df["pct_renters"]       = (census_df["renter_occupied"]   / (census_df["owner_occupied"] + census_df["renter_occupied"]) * 100).round(2)
census_df["pct_black"]         = (census_df["pop_black"]    / census_df["pop_total"] * 100).round(2)
census_df["pct_asian"]         = (census_df["pop_asian"]    / census_df["pop_total"] * 100).round(2)
census_df["pct_hispanic"]      = (census_df["pop_hispanic"] / census_df["pop_total"] * 100).round(2)

census_keep = [
    "ZCTA5CE20",
    "pop_total", "median_age", "median_hh_income", "median_home_value",
    "gini_index", "pct_broadband", "pct_below_poverty",
    "unemployment_rate", "pct_renters",
    "pct_black", "pct_asian", "pct_hispanic",
]
census_df = census_df[census_keep]
census_df["ZCTA5CE20"] = census_df["ZCTA5CE20"].astype(str).str.zfill(5)

gdf_clean["ZCTA5CE20"] = gdf_clean["ZCTA5CE20"].astype(str).str.zfill(5)
gdf_clean = gdf_clean.merge(census_df, on="ZCTA5CE20", how="left")
matched = gdf_clean["pop_total"].notna().sum()
print(f"  Fetched {len(census_df)} ZCTAs — {matched}/{len(gdf_clean)} rows matched")

# =============================================================================
# STEP 6 — Keep only essential columns
# =============================================================================
essential_columns = (
    ["city_label", "ZCTA5CE20", "geometry"]
    + ENERGY_COLUMNS
    + census_keep[1:]   # census vars minus ZCTA5CE20 (already in list)
)
existing_cols = [c for c in essential_columns if c in gdf_clean.columns]
gdf_clean = gdf_clean[existing_cols]

# =============================================================================
# STEP 7 — Simplify geometry, auto-tune tolerance to stay under 100 MB
# =============================================================================
print("\nSTEP 6: Simplifying geometry (auto-tuning tolerance)")
original_crs  = gdf_clean.crs
gdf_projected = gdf_clean.to_crs(epsg=3857)
os.makedirs("shiny_app/Data", exist_ok=True)

for tol in [10, 20, 30, 50, 75, 100, 150, 200]:
    test = gdf_projected.copy()
    test["geometry"] = test.geometry.simplify(tolerance=tol, preserve_topology=True)
    test = test.to_crs(original_crs)
    test.to_file(OUTPUT_CITIES, driver="GPKG")
    size_mb = os.path.getsize(OUTPUT_CITIES) / (1024 * 1024)
    print(f"  tolerance={tol:>4}m  →  {size_mb:.2f} MB")
    if size_mb <= SIZE_LIMIT_MB:
        gdf_clean = test
        print(f"  ✓ Keeping tolerance={tol}m ({size_mb:.2f} MB)")
        break
else:
    print("  ⚠ Could not reach <100 MB — using tolerance=200m as fallback")

# =============================================================================
# STEP 8 — Sanity check
# =============================================================================
print("\n--- Sanity check (atlanta) ---")
atl = gdf_clean[gdf_clean["city_label"] == "atlanta"]
for col in ["avg_price_2021", "comm_rate_2021", "res_rate_2021",
            "median_hh_income", "pct_broadband", "gini_index"]:
    if col in atl.columns:
        print(f"  {col}: {atl[col].nunique()} unique | "
              f"min={atl[col].min():.4f}  max={atl[col].max():.4f}")

size_mb = os.path.getsize(OUTPUT_CITIES) / (1024 * 1024)
print(f"\nSaved cities → {OUTPUT_CITIES} ({size_mb:.2f} MB)")

# =============================================================================
# STEP 9 — Filter & save data centers
# =============================================================================
print("\nSTEP 8: Saving data centers")
data_centers = gpd.read_file(DC_INPUT_PATH)
keep_dc_cols = [c for c in ["id", "name", "city_in_de", "geometry"] if c in data_centers.columns]
data_centers = data_centers[keep_dc_cols]
data_centers["city_in_de"] = data_centers["city_in_de"].str.lower().str.strip()

valid_cities = gdf_clean["city_label"].unique()
data_centers_filtered = data_centers[data_centers["city_in_de"].isin(valid_cities)].copy()
data_centers_filtered.to_file(OUTPUT_CENTERS, driver="GPKG")
print(f"  Saved {len(data_centers_filtered)} data center records → {OUTPUT_CENTERS}")

print("\n✓ All done.")