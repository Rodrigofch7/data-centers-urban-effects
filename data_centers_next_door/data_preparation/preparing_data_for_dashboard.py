import geopandas as gpd
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler
from census import Census
from shapely import wkb
from shapely.validation import make_valid
from shapely.ops import unary_union
import pgeocode
import warnings

# ── CONFIG ────────────────────────────────────────────────────────────────────
load_dotenv('/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/.env')
API_KEY = os.environ.get("CENSUS_API_KEY")
if not API_KEY:
    raise ValueError("CENSUS_API_KEY not found. Make sure your .env file exists and contains CENSUS_API_KEY=...")

ACS_YEAR = 2022

INPUT_PATH        = 'data/housing_and_data_centers_data/zillow_yearly_estimates_chicago_metro.csv'
MAP_PATH          = 'data/spatial_data/cities/ChicagoMetroArea.parquet'
DC_INPUT_PATH     = 'data/spatial_data/centers/DataCentersChicagoMetroArea.parquet'
ENERGY_WATER_PATH = 'data/energy and water data/nhgis_energy_water_wide.csv'
HHC_PATH          = 'data/clean_elecwater_hc_scores/pivoted_HHCScores.csv'
OUTPUT_CITIES     = 'shiny_app/Data/Chicago.gpkg'
OUTPUT_CENTERS    = 'shiny_app/Data/ChicagoDataCenters.gpkg'

# Only keep 3 Zillow snapshot years
YEAR_COLS = ['2010', '2019', '2024']

# Only the ACS variables we actually need
ACS_VARS_CLEAN = {
    "B01003_001E": "Total Population",
    "B19013_001E": "Median Household Income",
    "B25003_002E": "Owner Occupied Units",
    "B25003_003E": "Renter Occupied Units",
    "B28002_004E": "Broadband Subscribers",
    "B11001_001E": "Total Households",
    "B17001_002E": "Population Below Poverty",
    "B23025_005E": "Unemployed Population",
    "B23025_002E": "Labor Force Population",
}

# Energy/water columns needed for threshold calculations (2022 ACS only)
EW_COLS_NEEDED = [
    'elec_charged_2022',
    'elec_150_199_2022', 'elec_200_249_2022', 'elec_250_plus_2022',
    'elec_50_99_2022', 'elec_100_149_2022', 'elec_lt_50_2022',
    'water_charged_2022',
    'water_lt_125_2022',
    'water_125_249_2022', 'water_250_499_2022',
    'water_500_749_2022', 'water_750_999_2022', 'water_1000_plus_2022',
]

FRIENDLY_NAMES = {
    # Spatial
    'ZCTA5CE20':  'Zip Code',
    'ALAND20':    'Land Area (sq meters)',

    # Location
    'City':   'City',
    'County': 'County',
    'State':  'State',

    # Data centers
    'Total Data Centers':              'Total Data Centers',
    'Data Centers per 100k Residents': 'Data Centers per 100,000 Residents',

    # Zillow snapshots
    '2010': 'Median Home Value (2010)',
    '2019': 'Median Home Value (2019)',
    '2024': 'Median Home Value (2024)',

    # Census derived rates
    'Median Household Income':  'Median Household Income',
    'Population Density':       'Population Density (per sq km)',
    'Broadband %':              'Broadband Adoption Rate (%)',
    'Poverty %':                'Poverty Rate (%)',
    'Unemployment Rate %':      'Unemployment Rate (%)',
    'Renter %':                 'Renter-Occupied Share (%)',

    # Electricity thresholds
    'Elec % Above $50/month':   'Electricity: % Paying Above $50/month',
    'Elec % Above $150/month':  'Electricity: % Paying Above $150/month',
    'Elec % Above $250/month':  'Electricity: % Paying $250+/month',

    # Water thresholds
    'Water % Above $125/year':  'Water & Sewer: % Paying Above $125/year',
    'Water % Above $500/year':  'Water & Sewer: % Paying Above $500/year',
    'Water % Above $1000/year': 'Water & Sewer: % Paying $1,000+/year',

    # Data center point attributes
    'facility':   'Facility Name',
    'operator':   'Operator',
    'street':     'Street Address',
    'zip_code':   'Data Center ZIP Code',
    'city_in_de': 'City',
    'latitude':   'Latitude',
    'longitude':  'Longitude',

    # Housing Costs
    'HHC Score (2007-2011)': 'Household Cost Score (2007–2011)',
    'HHC Score (2019-2023)': 'Household Cost Score (2019–2023)',
    'HHC Score (2020-2024)': 'Household Cost Score (2020–2024)',
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
# STEP 2 — Spatial anchor & count Data Centers per ZIP
# =============================================================================
print("STEP 2: Loading spatial file and counting data centers per ZIP...")
map_gdf = gpd.read_parquet(MAP_PATH)
map_gdf['ZCTA5CE20'] = map_gdf['ZCTA5CE20'].astype(str).str.zfill(5)
print(f"  -> Spatial anchor: {len(map_gdf):,} ZIP codes")

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

map_gdf = map_gdf.merge(counts_per_zip, on='ZCTA5CE20', how='left')
map_gdf['Total Data Centers'] = map_gdf['Total Data Centers'].fillna(0).astype(int)

# =============================================================================
# STEP 2.5 — Clean geometries
# =============================================================================
print("STEP 2.5: Cleaning geometries...")

map_gdf['geometry'] = map_gdf['geometry'].apply(
    lambda g: make_valid(g) if g is not None and not g.is_valid else g
)

def fill_small_holes(geom, min_hole_area_m2=500_000):
    from shapely.geometry import Polygon, MultiPolygon
    def fill_poly(poly):
        if poly is None:
            return poly
        new_interiors = [
            ring for ring in poly.interiors
            if Polygon(ring).area > min_hole_area_m2
        ]
        return Polygon(poly.exterior, new_interiors)
    if geom.geom_type == 'Polygon':
        return fill_poly(geom)
    elif geom.geom_type == 'MultiPolygon':
        return MultiPolygon([fill_poly(p) for p in geom.geoms])
    return geom

map_gdf = map_gdf.to_crs(epsg=3857)
map_gdf['geometry'] = map_gdf['geometry'].apply(fill_small_holes)
map_gdf = map_gdf.to_crs(epsg=4326)

def keep_largest_parts(geom, min_area_fraction=0.01):
    from shapely.geometry import MultiPolygon
    if geom.geom_type == 'MultiPolygon':
        total = geom.area
        parts = [p for p in geom.geoms if p.area / total >= min_area_fraction]
        if len(parts) == 1:
            return parts[0]
        return MultiPolygon(parts) if parts else geom
    return geom

map_gdf['geometry'] = map_gdf['geometry'].apply(keep_largest_parts)
map_gdf['geometry'] = map_gdf['geometry'].simplify(tolerance=0.0001, preserve_topology=True)
map_gdf['geometry'] = map_gdf['geometry'].buffer(0.00001).buffer(-0.00001)

invalid = (~map_gdf.geometry.is_valid).sum()
empty   = map_gdf.geometry.is_empty.sum()
print(f"  -> Invalid geometries remaining: {invalid}")
print(f"  -> Empty geometries: {empty}")
print(f"  -> All geometries cleaned ✓")

# =============================================================================
# STEP 3 — Zillow (3 snapshot years only)
# =============================================================================
print("STEP 3: Merging Zillow snapshot years (2010, 2019, 2024)...")
zillow_df = pd.read_csv(INPUT_PATH, dtype={'ZCTA5CE20': str})
zillow_df['ZCTA5CE20'] = zillow_df['ZCTA5CE20'].astype(str).str.zfill(5)

available_years = [y for y in YEAR_COLS if y in zillow_df.columns]
zillow_df = zillow_df[['ZCTA5CE20'] + available_years]
for col in available_years:
    zillow_df[col] = pd.to_numeric(zillow_df[col], errors='coerce')

gdf = map_gdf.merge(zillow_df, on='ZCTA5CE20', how='left')
print(f"  -> {gdf['ZCTA5CE20'].nunique():,} unique ZIPs after Zillow merge")

# =============================================================================
# STEP 4 — Energy & Water
# =============================================================================
print("STEP 4: Merging Energy & Water data and computing cost thresholds...")
ew_df = pd.read_csv(ENERGY_WATER_PATH, dtype={"ZCTA5A": str})
ew_df['ZCTA5A'] = ew_df['ZCTA5A'].astype(str).str.zfill(5)

keep_ew = ['ZCTA5A'] + [c for c in EW_COLS_NEEDED if c in ew_df.columns]
ew_df = ew_df[keep_ew]
for col in keep_ew[1:]:
    ew_df[col] = pd.to_numeric(ew_df[col], errors='coerce')

gdf = gdf.merge(ew_df, left_on='ZCTA5CE20', right_on='ZCTA5A', how='left')
gdf = gdf.drop(columns=['ZCTA5A'], errors='ignore')

def safe_pct(numerator, denominator):
    return np.where(denominator > 0, (numerator / denominator * 100).round(2), np.nan)

if 'elec_charged_2022' in gdf.columns:
    charged_e = gdf['elec_charged_2022']
    gdf['Elec % Above $50/month']  = safe_pct(charged_e - gdf.get('elec_lt_50_2022', 0), charged_e)
    gdf['Elec % Above $150/month'] = safe_pct(
        gdf.get('elec_150_199_2022', 0) + gdf.get('elec_200_249_2022', 0) + gdf.get('elec_250_plus_2022', 0),
        charged_e)
    gdf['Elec % Above $250/month'] = safe_pct(gdf.get('elec_250_plus_2022', 0), charged_e)

if 'water_charged_2022' in gdf.columns:
    charged_w = gdf['water_charged_2022']
    gdf['Water % Above $125/year']  = safe_pct(charged_w - gdf.get('water_lt_125_2022', 0), charged_w)
    gdf['Water % Above $500/year']  = safe_pct(
        gdf.get('water_500_749_2022', 0) + gdf.get('water_750_999_2022', 0) + gdf.get('water_1000_plus_2022', 0),
        charged_w)
    gdf['Water % Above $1000/year'] = safe_pct(gdf.get('water_1000_plus_2022', 0), charged_w)

gdf = gdf.drop(columns=[c for c in EW_COLS_NEEDED if c in gdf.columns])
print("  -> Raw energy/water columns dropped; 6 threshold columns retained")

# =============================================================================
# STEP 4.5 — Household Cost Scores
# =============================================================================
print("STEP 4.5: Merging Household Cost Scores...")
hhc_df = pd.read_csv(HHC_PATH, dtype={'ZCTA5A': str})
hhc_df['ZCTA5A'] = hhc_df['ZCTA5A'].astype(str).str.zfill(5)

hhc_keep_cols = ['2007-2011', '2019-2023', '2020-2024']
available_hhc = [c for c in hhc_keep_cols if c in hhc_df.columns]
hhc_df = hhc_df[['ZCTA5A'] + available_hhc].rename(
    columns={c: f'HHC Score ({c})' for c in available_hhc}
)
for col in hhc_df.columns[1:]:
    hhc_df[col] = pd.to_numeric(hhc_df[col], errors='coerce')

gdf = gdf.merge(hhc_df, left_on='ZCTA5CE20', right_on='ZCTA5A', how='left')
gdf = gdf.drop(columns=['ZCTA5A'], errors='ignore')
print(f"  -> HHC score columns added: {[c for c in gdf.columns if 'HHC' in c]}")

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
    census_df[col] = pd.to_numeric(census_df[col], errors='coerce')

census_df['Broadband %']         = (census_df['Broadband Subscribers'] / census_df['Total Households'] * 100).round(2)
census_df['Poverty %']           = (census_df['Population Below Poverty'] / census_df['Total Population'] * 100).round(2)
census_df['Unemployment Rate %'] = (census_df['Unemployed Population'] / census_df['Labor Force Population'] * 100).round(2)
census_df['Renter %']            = (census_df['Renter Occupied Units'] / (census_df['Owner Occupied Units'] + census_df['Renter Occupied Units']) * 100).round(2)

census_keep = ['census_zip', 'Total Population', 'Median Household Income',
               'Broadband %', 'Poverty %', 'Unemployment Rate %', 'Renter %']
census_df = census_df[census_keep]
census_df['census_zip'] = census_df['census_zip'].astype(str).str.zfill(5)

gdf = gdf.merge(census_df, left_on='ZCTA5CE20', right_on='census_zip', how='left')
gdf = gdf.drop(columns=['census_zip', 'NAME'], errors='ignore')

# =============================================================================
# STEP 5.5 — City / County / State lookup
# =============================================================================
print("STEP 5.5: Adding City, County, State via pgeocode...")

nomi = pgeocode.Nominatim('us')

def get_zip_info(zipcode):
    result = nomi.query_postal_code(str(zipcode))
    if result is not None and pd.notna(result.get('place_name')):
        return pd.Series({
            'City':   result.get('place_name', '—'),
            'County': result.get('county_name', '—'),
            'State':  result.get('state_name',  '—'),
        })
    return pd.Series({'City': '—', 'County': '—', 'State': '—'})

zip_info = gdf['ZCTA5CE20'].apply(get_zip_info)
gdf = pd.concat([gdf.reset_index(drop=True), zip_info], axis=1)
matched = zip_info['City'].ne('—').sum()
print(f"  -> City/County/State resolved for {matched}/{len(gdf)} ZIPs")

# =============================================================================
# STEP 6 — Derived spatial variables
# =============================================================================
print("STEP 6: Computing population density and data centers per 100k residents...")

gdf['Population Density'] = (
    gdf['Total Population'] / (gdf['ALAND20'] / 1_000_000)
).round(2)

gdf['Data Centers per 100k Residents'] = np.where(
    gdf['Total Population'] > 0,
    (gdf['Total Data Centers'] / gdf['Total Population'] * 100_000).round(4),
    np.nan
)

# =============================================================================
# STEP 7 — KNN Imputation across numeric columns
# =============================================================================
print("STEP 7: Running KNN imputation...")

non_impute = {'Total Data Centers', 'geometry'}
numeric_cols = [
    col for col in gdf.select_dtypes(include=[np.number]).columns
    if col not in non_impute
]

impute_df = gdf[numeric_cols].copy()

before_missing = impute_df.isna().sum().sum()
print(f"  -> {len(numeric_cols)} numeric columns | {before_missing:,} missing values before imputation")

scaler  = StandardScaler()
imputer = KNNImputer(n_neighbors=5)

scaled   = scaler.fit_transform(impute_df)
imputed  = imputer.fit_transform(scaled)
restored = scaler.inverse_transform(imputed)

result_df = pd.DataFrame(restored, columns=numeric_cols, index=gdf.index)

for col in numeric_cols:
    observed_min = impute_df[col].dropna().quantile(0.01)
    observed_max = impute_df[col].dropna().quantile(0.99)
    result_df[col] = result_df[col].clip(lower=max(0, observed_min), upper=observed_max)

gdf[numeric_cols] = result_df

after_missing = gdf[numeric_cols].isna().sum().sum()
print(f"  -> {after_missing:,} missing values after imputation")

print("  -> Post-imputation value ranges:")
for col in numeric_cols:
    print(f"     {col:<45} min={gdf[col].min():>12.2f}  max={gdf[col].max():>12.2f}")

# =============================================================================
# STEP 8 — Validate
# =============================================================================
print("STEP 8: Validating row count...")
assert len(gdf) == len(map_gdf), (
    f"ERROR: row count changed! Started with {len(map_gdf)} ZIPs, ended with {len(gdf)}"
)
assert gdf['ZCTA5CE20'].nunique() == len(gdf), "ERROR: duplicate ZCTAs detected!"
print(f"  -> All {len(gdf):,} parquet ZIPs present in final output")

# =============================================================================
# STEP 9 — Rename to friendly names & export
# =============================================================================
print("STEP 9: Renaming columns and exporting...")

gdf = gdf.loc[:, ~gdf.columns.duplicated()]
gdf = gdf.rename(columns=FRIENDLY_NAMES)

unnamed = [c for c in gdf.columns if c not in FRIENDLY_NAMES.values() and c != 'geometry']
if unnamed:
    print(f"  -> Columns not in rename map (kept as-is): {unnamed}")

print(f"\nFinal column list ({len(gdf.columns)} columns):")
for col in gdf.columns:
    print(f"  {col}")

os.makedirs(os.path.dirname(OUTPUT_CITIES), exist_ok=True)
gdf.to_file(OUTPUT_CITIES, driver="GPKG")
print("\nDone!")