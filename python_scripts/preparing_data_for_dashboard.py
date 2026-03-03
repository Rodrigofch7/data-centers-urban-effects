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

INPUT_PATH        = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/zillow_yearly_estimates_chicago_metro.csv'
MAP_PATH          = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/spatial_data/cities/ChicagoMetroArea.parquet'
DC_INPUT_PATH     = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/data/spatial_data/centers/DataCentersChicagoMetroArea.parquet'
ENERGY_WATER_PATH = 'data/energy and water data/nhgis_energy_water_wide.csv'
OUTPUT_CITIES     = 'shiny_app/Data/Chicago.gpkg'
OUTPUT_CENTERS    = 'shiny_app/Data/ChicagoDataCenters.gpkg'

YEAR_COLS = [str(year) for year in range(2000, 2027)]

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

# ── MASTER RENAME DICTIONARY ──────────────────────────────────────────────────
# Built from the exact column names confirmed by inspect_columns.py

def _ew_renames():
    elec_base = {
        'elec_total':           'Electricity: Total Housing Units',
        'elec_not_charged':     'Electricity: Not Charged or Included in Fees',
        'elec_charged':         'Electricity: Units Charged',
        'elec_lt_50':           'Electricity: Under $50/month',
        'elec_50_99':           'Electricity: $50-$99/month',
        'elec_100_149':         'Electricity: $100-$149/month',
        'elec_150_199':         'Electricity: $150-$199/month',
        'elec_200_249':         'Electricity: $200-$249/month',
        'elec_250_plus':        'Electricity: $250+/month',
        'elec_total_moe':       'Electricity: Total (Margin of Error)',
        'elec_not_charged_moe': 'Electricity: Not Charged (Margin of Error)',
        'elec_charged_moe':     'Electricity: Units Charged (Margin of Error)',
        'elec_lt_50_moe':       'Electricity: Under $50/month (Margin of Error)',
        'elec_50_99_moe':       'Electricity: $50-$99/month (Margin of Error)',
        'elec_100_149_moe':     'Electricity: $100-$149/month (Margin of Error)',
        'elec_150_199_moe':     'Electricity: $150-$199/month (Margin of Error)',
        'elec_200_249_moe':     'Electricity: $200-$249/month (Margin of Error)',
        'elec_250_plus_moe':    'Electricity: $250+/month (Margin of Error)',
    }
    water_base = {
        'water_total':           'Water & Sewer: Total Housing Units',
        'water_not_charged':     'Water & Sewer: Not Charged or Included in Fees',
        'water_charged':         'Water & Sewer: Units Charged',
        'water_lt_125':          'Water & Sewer: Under $125/year',
        'water_125_249':         'Water & Sewer: $125-$249/year',
        'water_250_499':         'Water & Sewer: $250-$499/year',
        'water_500_749':         'Water & Sewer: $500-$749/year',
        'water_750_999':         'Water & Sewer: $750-$999/year',
        'water_1000_plus':       'Water & Sewer: $1,000+/year',
        'water_total_moe':       'Water & Sewer: Total (Margin of Error)',
        'water_not_charged_moe': 'Water & Sewer: Not Charged (Margin of Error)',
        'water_charged_moe':     'Water & Sewer: Units Charged (Margin of Error)',
        'water_lt_125_moe':      'Water & Sewer: Under $125/year (Margin of Error)',
        'water_125_249_moe':     'Water & Sewer: $125-$249/year (Margin of Error)',
        'water_250_499_moe':     'Water & Sewer: $250-$499/year (Margin of Error)',
        'water_500_749_moe':     'Water & Sewer: $500-$749/year (Margin of Error)',
        'water_750_999_moe':     'Water & Sewer: $750-$999/year (Margin of Error)',
        'water_1000_plus_moe':   'Water & Sewer: $1,000+/year (Margin of Error)',
    }
    renames = {}
    for year in [2021, 2022, 2023, 2024]:
        for k, v in {**elec_base, **water_base}.items():
            renames[f'{k}_{year}'] = f'{v} ({year} ACS)'
    return renames

FRIENDLY_NAMES = {
    # ── Spatial anchor ────────────────────────────────────────────────────────
    'ZCTA5CE20':   'Zip Code',
    'GEOID20':     'Geographic ID',
    'CLASSFP20':   'Class Code',
    'MTFCC20':     'Feature Class Code',
    'FUNCSTAT20':  'Functional Status',
    'ALAND20':     'Land Area (sq meters)',
    'AWATER20':    'Water Area (sq meters)',
    'INTPTLAT20':  'Internal Point Latitude',
    'INTPTLON20':  'Internal Point Longitude',

    # ── Data Centers ──────────────────────────────────────────────────────────
    'Total Data Centers': 'Total Data Centers',
    'scraped_ci':  'Scraped City',
    'state':       'State',
    'facility':    'Facility Name',
    'operator':    'Operator',
    'street':      'Street Address',
    'zip_code':    'Data Center ZIP Code',
    'city_in_de':  'City',
    'match_meth':  'Match Method',
    'latitude':    'Latitude',
    'longitude':   'Longitude',
    'used_fallb':  'Used Fallback Geocoding',
    'MetroRegio':  'Metro Region',

    # ── Zillow metadata ───────────────────────────────────────────────────────
    'RegionID':    'Zillow Region ID',
    'SizeRank':    'Zillow Size Rank',
    'RegionType':  'Region Type',
    'StateName':   'State Name',
    'State':       'State Code',
    'City':        'City',
    'Metro':       'Metro Area',
    'CountyName':  'County',

    # ── Zillow year columns (2000–2026) ───────────────────────────────────────
    **{str(y): f'Median Home Value ({y})' for y in range(2000, 2027)},

    # ── Energy & Water (all 4 ACS years) ─────────────────────────────────────
    **_ew_renames(),

    # ── Census raw counts ─────────────────────────────────────────────────────
    'Total Population':         'Total Population',
    'Median Age':               'Median Age',
    'Median Household Income':  'Median Household Income',
    'Median Home Value':        'Median Home Value (Census ACS)',
    'Owner Occupied Units':     'Owner-Occupied Housing Units',
    'Renter Occupied Units':    'Renter-Occupied Housing Units',
    'Broadband Subscribers':    'Broadband Subscribers',
    'Total Households':         'Total Households',
    'Population Below Poverty': 'Population Below Poverty Line',
    'Gini Index':               'Gini Inequality Index',
    'Unemployed Population':    'Unemployed Population',
    'Labor Force Population':   'Labor Force Population',
    'Black Population':         'Black or African American Population',
    'Asian Population':         'Asian Population',
    'Hispanic Population':      'Hispanic or Latino Population',

    # ── Census derived rates ──────────────────────────────────────────────────
    'Broadband %':         'Broadband Adoption Rate (%)',
    'Poverty %':           'Poverty Rate (%)',
    'Unemployment Rate %': 'Unemployment Rate (%)',
    'Renter %':            'Renter-Occupied Share (%)',
}


def to_title_case(df):
    for col in df.select_dtypes(include=['object', 'str']):
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
print(f"  -> {len(dc_gdf)} unique data center locations after deduplication")

dc_gdf = to_title_case(dc_gdf)
os.makedirs(os.path.dirname(OUTPUT_CENTERS), exist_ok=True)
dc_gdf.to_file(OUTPUT_CENTERS, driver="GPKG")

# =============================================================================
# STEP 2 — Load spatial anchor & count Data Centers per ZIP via spatial join
# =============================================================================
print("STEP 2: Loading spatial file and counting data centers per ZIP...")
map_gdf = gpd.read_parquet(MAP_PATH)
map_gdf['ZCTA5CE20'] = map_gdf['ZCTA5CE20'].astype(str).str.zfill(5)
print(f"  -> Spatial anchor: {len(map_gdf):,} ZIP codes")

# Spatially join data centers to ZIP polygons to assign each a ZCTA5CE20
dc_gdf_proj = dc_gdf.to_crs(map_gdf.crs)
dc_with_zip = gpd.sjoin(dc_gdf_proj, map_gdf[['ZCTA5CE20', 'geometry']], how='left', predicate='within')
dc_with_zip['ZCTA5CE20'] = dc_with_zip['ZCTA5CE20'].astype(str).str.zfill(5)

unmatched = dc_with_zip['ZCTA5CE20'].isna().sum()
if unmatched:
    print(f"  -> Warning: {unmatched} data center(s) did not fall within any ZIP polygon")

counts_per_zip = (
    dc_with_zip.dropna(subset=['ZCTA5CE20'])
    .groupby('ZCTA5CE20')
    .size()
    .reset_index(name='Total Data Centers')
)

print("  -> Top ZIP codes by data center count:")
print(counts_per_zip.sort_values('Total Data Centers', ascending=False).head(10).to_string(index=False))

map_gdf = map_gdf.merge(counts_per_zip, on='ZCTA5CE20', how='left')
map_gdf['Total Data Centers'] = map_gdf['Total Data Centers'].fillna(0).astype(int)

# =============================================================================
# STEP 3 — Merge Zillow
# =============================================================================
print("STEP 3: Merging Zillow data...")
zillow_df = pd.read_csv(INPUT_PATH, dtype={'ZCTA5CE20': str})
zillow_df['ZCTA5CE20'] = zillow_df['ZCTA5CE20'].astype(str).str.zfill(5)

# Drop columns already in map_gdf to avoid duplicates
zillow_drop = ['GEOID20', 'CLASSFP20', 'MTFCC20', 'FUNCSTAT20',
               'ALAND20', 'AWATER20', 'INTPTLAT20', 'INTPTLON20']
zillow_df = zillow_df.drop(columns=[c for c in zillow_drop if c in zillow_df.columns])

gdf = map_gdf.merge(zillow_df, on="ZCTA5CE20", how="left")
print(f"  -> {gdf['ZCTA5CE20'].nunique():,} unique ZIPs after Zillow merge")

for col in YEAR_COLS:
    if col in gdf.columns:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

# =============================================================================
# STEP 4 — Energy & Water Data
# =============================================================================
print("STEP 4: Merging Energy and Water data...")
ew_df = pd.read_csv(ENERGY_WATER_PATH, dtype={"ZCTA5A": str})
ew_df['ZCTA5A'] = ew_df['ZCTA5A'].astype(str).str.zfill(5)

# Drop context cols already present in gdf
ew_df = ew_df.drop(columns=[c for c in ['GISJOIN', 'STUSAB', 'NAME_E'] if c in ew_df.columns])

gdf = gdf.merge(ew_df, left_on="ZCTA5CE20", right_on="ZCTA5A", how="left")
gdf = gdf.drop(columns=["ZCTA5A"], errors="ignore")
print(f"  -> {len([c for c in ew_df.columns if c != 'ZCTA5A'])} energy/water columns added")

# =============================================================================
# STEP 5 — Census Data
# =============================================================================
print("STEP 5: Fetching Census data...")
c = Census(API_KEY, year=ACS_YEAR)
results = c.acs5.get(["NAME"] + list(ACS_VARS_CLEAN.keys()), {"for": "zip code tabulation area:*"})
census_df = (
    pd.DataFrame(results)
    .rename(columns={"zip code tabulation area": "census_zip"})
    .rename(columns=ACS_VARS_CLEAN)
)

for col in ACS_VARS_CLEAN.values():
    census_df[col] = pd.to_numeric(census_df[col], errors="coerce")

census_df["Broadband %"]         = (census_df["Broadband Subscribers"] / census_df["Total Households"] * 100).round(2)
census_df["Poverty %"]           = (census_df["Population Below Poverty"] / census_df["Total Population"] * 100).round(2)
census_df["Unemployment Rate %"] = (census_df["Unemployed Population"] / census_df["Labor Force Population"] * 100).round(2)
census_df["Renter %"]            = (census_df["Renter Occupied Units"] / (census_df["Owner Occupied Units"] + census_df["Renter Occupied Units"]) * 100).round(2)

census_df["census_zip"] = census_df["census_zip"].astype(str).str.zfill(5)
gdf = gdf.merge(census_df, left_on="ZCTA5CE20", right_on="census_zip", how="left")

# =============================================================================
# STEP 6 — KNN Imputation across ALL numeric columns
# =============================================================================
print("STEP 6: Running KNN imputation across all numeric columns...")

non_impute = {'Total Data Centers', 'geometry'}
numeric_cols = [
    col for col in gdf.select_dtypes(include=[np.number]).columns
    if col not in non_impute
]

before_missing = gdf[numeric_cols].isna().sum().sum()
print(f"  -> {len(numeric_cols)} numeric columns to impute")
print(f"  -> {before_missing:,} total missing values before imputation")

scaler  = StandardScaler()
imputer = KNNImputer(n_neighbors=5)

scaled  = scaler.fit_transform(gdf[numeric_cols])
imputed = imputer.fit_transform(scaled)
gdf[numeric_cols] = scaler.inverse_transform(imputed)

after_missing = gdf[numeric_cols].isna().sum().sum()
print(f"  -> {after_missing:,} missing values after imputation")

# =============================================================================
# STEP 7 — Validate row count never drifted from spatial anchor
# =============================================================================
print("STEP 7: Validating row count...")
assert len(gdf) == len(map_gdf), (
    f"ERROR: row count changed! Started with {len(map_gdf)} ZIPs, ended with {len(gdf)}"
)
assert gdf["ZCTA5CE20"].nunique() == len(gdf), "ERROR: duplicate ZCTAs detected!"
print(f"  -> All {len(gdf):,} parquet ZIPs present in final output")

# =============================================================================
# STEP 8 — Drop internal columns, rename to friendly names, export
# =============================================================================
print("STEP 8: Renaming columns and exporting...")

cols_to_drop = ['census_zip', 'NAME']
gdf = gdf.drop(columns=[c for c in cols_to_drop if c in gdf.columns])
gdf = gdf.loc[:, ~gdf.columns.duplicated()]

# Apply friendly names — only renames columns present in the map; others kept as-is
gdf = gdf.rename(columns=FRIENDLY_NAMES)

# Report any columns not covered by the rename map (excluding geometry)
unnamed = [c for c in gdf.columns if c not in FRIENDLY_NAMES.values() and c != 'geometry']
if unnamed:
    print(f"  -> Note: {len(unnamed)} columns not in rename map (kept as-is): {unnamed}")

print(f"\nFinal column list ({len(gdf.columns)} columns):")
for col in gdf.columns:
    print(f"  {col}")

os.makedirs(os.path.dirname(OUTPUT_CITIES), exist_ok=True)
gdf.to_file(OUTPUT_CITIES, driver="GPKG")
print("\nSuccess!")