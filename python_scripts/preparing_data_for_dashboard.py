import geopandas as gpd
import pandas as pd
import numpy as np
import os
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler
from census import Census
from shapely import wkb

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY = "fda60e79b0da81a8ac6472ff4250f47daa8c527b"
ACS_YEAR = 2022

INPUT_PATH     = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/zillow_yearly_estimates_cook_county.csv'
MAP_PATH       = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/spatial_data/cities/chicago.geojson'
DC_INPUT_PATH  = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/spatial_data/centers/ChicagoDataCentersWithConstructionDate.parquet'
OUTPUT_CITIES  = 'shiny_app/Data/Chicago.gpkg'
OUTPUT_CENTERS = 'shiny_app/Data/ChicagoDataCenters.gpkg'

YEAR_COLS = [str(year) for year in range(2000, 2026)]

ACS_VARS_CLEAN = {
    "B01003_001E": "Total Population",
    "B01002_001E": "Median Age",
    "B19013_001E": "Median Household Income",
    "B25077_001E": "Median Home Value",
    "B25003_002E": "Owner Occupied Units",
    "B25003_003E": "Renter Occupied Units",
    "B28002_004E": "Broadband Subscribers",
    "B11001_001E": "Total Households",
    "B17001_002E": "Population Below Poverty",
    "B19083_001E": "Gini Index",
    "B23025_005E": "Unemployed Population",
    "B23025_002E": "Labor Force Population",
    "B02001_003E": "Black Population",
    "B02001_005E": "Asian Population",
    "B03003_003E": "Hispanic Population",
}

def to_title_case(df):
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].astype(str).str.title()
    return df

# =============================================================================
# STEP 1 — Data Centers
# =============================================================================
print("STEP 1: Processing Data Centers...")
dc_df = pd.read_parquet(DC_INPUT_PATH)
dc_df['geometry'] = dc_df['geometry'].apply(lambda x: wkb.loads(x) if isinstance(x, bytes) else x)
dc_gdf = gpd.GeoDataFrame(dc_df, geometry='geometry', crs="EPSG:4326")

def extract_point(geom):
    if geom is None:
        return geom
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)[0]
    return geom

dc_gdf['geometry'] = dc_gdf['geometry'].apply(extract_point)
dc_gdf = dc_gdf[dc_gdf.geometry.geom_type == "Point"].reset_index(drop=True)

dc_gdf['_lon'] = dc_gdf.geometry.x.round(4)
dc_gdf['_lat'] = dc_gdf.geometry.y.round(4)
dc_gdf = dc_gdf.drop_duplicates(subset=['_lon', '_lat']).drop(columns=['_lon', '_lat'])
dc_gdf = dc_gdf.reset_index(drop=True)
print(f"  → {len(dc_gdf)} unique data center locations after deduplication")

dc_gdf = to_title_case(dc_gdf)
os.makedirs(os.path.dirname(OUTPUT_CENTERS), exist_ok=True)
dc_gdf.to_file(OUTPUT_CENTERS, driver="GPKG")

# =============================================================================
# STEP 2 — Count Data Centers per ZIP (using deduplicated dc_gdf)
# =============================================================================
print("STEP 2: Counting data centers per ZIP...")
map_gdf = gpd.read_file(MAP_PATH)
map_gdf['ZCTA5CE20'] = map_gdf['ZCTA5CE20'].astype(str).str.zfill(5)

counts_per_zip = (
    dc_gdf.groupby('ZCTA5CE20')
    .size()
    .reset_index(name='Total Data Centers')
)
counts_per_zip['ZCTA5CE20'] = counts_per_zip['ZCTA5CE20'].astype(str).str.zfill(5)

print("  → Top ZIP codes by data center count:")
print(counts_per_zip.sort_values('Total Data Centers', ascending=False).head(10).to_string(index=False))

map_gdf = map_gdf.merge(counts_per_zip, on='ZCTA5CE20', how='left')
map_gdf['Total Data Centers'] = map_gdf['Total Data Centers'].fillna(0).astype(int)

# =============================================================================
# STEP 3 — Merge Zillow & Impute
# =============================================================================
print("STEP 3: Merging Zillow and Imputing Price Data...")
zillow_df = pd.read_csv(INPUT_PATH)
zillow_df['ZipCode'] = zillow_df['ZipCode'].astype(str).str.zfill(5)

zillow_rename = {
    'RegionID': 'Region ID', 'SizeRank': 'Size Rank', 'ZipCode': 'Zip Code Key',
    'RegionType': 'Region Type', 'StateName': 'State Name', 'CountyName': 'County Name'
}
zillow_df = zillow_df.rename(columns=zillow_rename)
zillow_df = to_title_case(zillow_df)

gdf = map_gdf.merge(zillow_df, left_on="ZCTA5CE20", right_on="Zip Code Key", how="inner")

for col in YEAR_COLS:
    gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

scaler, imputer = StandardScaler(), KNNImputer(n_neighbors=5)
scaled  = scaler.fit_transform(gdf[YEAR_COLS])
imputed = imputer.fit_transform(scaled)
gdf[YEAR_COLS] = scaler.inverse_transform(imputed)

# =============================================================================
# STEP 4 — Census Data
# =============================================================================
print("STEP 4: Fetching Census data...")
c = Census(API_KEY, year=ACS_YEAR)
results = c.acs5.get(["NAME"] + list(ACS_VARS_CLEAN.keys()), {"for": "zip code tabulation area:*"})
census_df = pd.DataFrame(results).rename(columns={"zip code tabulation area": "census_zip"}).rename(columns=ACS_VARS_CLEAN)

for col in ACS_VARS_CLEAN.values():
    census_df[col] = pd.to_numeric(census_df[col], errors="coerce")

census_df["Broadband %"]         = (census_df["Broadband Subscribers"] / census_df["Total Households"] * 100).round(2)
census_df["Poverty %"]           = (census_df["Population Below Poverty"] / census_df["Total Population"] * 100).round(2)
census_df["Unemployment Rate %"] = (census_df["Unemployed Population"] / census_df["Labor Force Population"] * 100).round(2)
census_df["Renter %"]            = (census_df["Renter Occupied Units"] / (census_df["Owner Occupied Units"] + census_df["Renter Occupied Units"]) * 100).round(2)

census_df["census_zip"] = census_df["census_zip"].astype(str).str.zfill(5)
gdf = gdf.merge(census_df, left_on="ZCTA5CE20", right_on="census_zip", how="left")

# =============================================================================
# STEP 5 — Export & Cleanup
# =============================================================================
cols_to_drop = ['Zip Code Key', 'census_zip', 'NAME', 'AFFGEOID20', 'GEOID20', 'LSAD20']
gdf = gdf.drop(columns=[c for c in cols_to_drop if c in gdf.columns])
gdf = gdf.loc[:, ~gdf.columns.duplicated()]
gdf = gdf.rename(columns={'ZCTA5CE20': 'Zip Code'})

gdf.to_file(OUTPUT_CITIES, driver="GPKG")
print("✅ Success!")