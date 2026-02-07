import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim, ArcGIS
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from tqdm.auto import tqdm
import os
import time
import re

# --- 1. Load and Filter Data ---
df = pd.read_csv("data/top_10_us_cities_datacenters.csv")

cities = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "Jacksonville",
    "Miami", "Boston", "Atlanta", "Santa Clara", "Denver",
]

df = df[df["city_in_desc"].isin(cities)].copy()

# --- 2. Initialize Geocoders ---
# Nominatim (OSM) - Strict but free
geolocator = Nominatim(user_agent="datacenters_geocoder_v2")
_geocode_osm = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

# ArcGIS - More "fuzzy" and forgiving
arcgis_geolocator = ArcGIS()
_geocode_arcgis = RateLimiter(arcgis_geolocator.geocode, min_delay_seconds=0.2)

# --- 3. Helper Functions ---
def clean_address(street):
    """Removes Suite, Floor, and extra noise that confuses Nominatim."""
    if not street or pd.isna(street): return ""
    # Split by common delimiters and take the first part
    s = re.split(r'#|Suite|Ste|Floor|Fl|Unit|,', street, flags=re.IGNORECASE)[0]
    return s.strip()

def geocode_robust(street, city, state, max_retries=3):
    """
    Waterfall Logic:
    1. OSM (Structured)
    2. OSM (Cleaned Street)
    3. ArcGIS (High Reliability Fallback)
    4. OSM (Street Only - Last Resort)
    """
    full_query = {"street": street, "city": city, "state": state, "country": "USA"}
    cleaned_street = clean_address(street)
    
    for attempt in range(max_retries):
        try:
            # Tier 1: Nominatim Strict
            loc = _geocode_osm(full_query)
            if loc: return loc, "osm_strict"

            # Tier 2: Nominatim Cleaned
            if cleaned_street != street:
                loc = _geocode_osm({"street": cleaned_street, "city": city, "state": state, "country": "USA"})
                if loc: return loc, "osm_cleaned"

            # Tier 3: ArcGIS Fallback (Great at handling messy strings)
            # We use a single string here as ArcGIS handles it better
            arcgis_query = f"{cleaned_street}, {city}, {state}, USA"
            loc = _geocode_arcgis(arcgis_query)
            if loc: return loc, "arcgis_fallback"

            # Tier 4: Street Only (OSM)
            street_only = ' '.join(cleaned_street.split()[1:]) if len(cleaned_street.split()) > 1 else None
            if street_only:
                loc = _geocode_osm({"street": street_only, "city": city, "state": state, "country": "USA"})
                if loc: return loc, "osm_street_only"

            return None, "failed"

        except (GeocoderTimedOut, GeocoderUnavailable):
            time.sleep(2 ** attempt)
            
    return None, "timeout"

# --- 4. Execution ---
print("Starting robust geocoding...")

results_list = []
for _, row in tqdm(df.iterrows(), total=len(df)):
    loc, method = geocode_robust(row['street'], row['city_in_desc'], row['state'])
    results_list.append({
        'location_obj': loc, 
        'match_method': method,
        'latitude': loc.latitude if loc else None,
        'longitude': loc.longitude if loc else None
    })

# Merge results back to main dataframe
results_df = pd.DataFrame(results_list)
df = pd.concat([df.reset_index(drop=True), results_df], axis=1)

# used_fallback is True if it didn't match on the first try (osm_strict)
df["used_fallback"] = df["match_method"].apply(lambda x: x not in ["osm_strict", "failed"])

# Clean up
df.drop(columns=["location_obj"], inplace=True)

# --- 5. Save Results ---
# Remove rows that failed completely before making GeoDataFrame
df_clean = df.dropna(subset=["latitude", "longitude"]).copy()

gdf = gpd.GeoDataFrame(
    df_clean, 
    geometry=gpd.points_from_xy(df_clean.longitude, df_clean.latitude), 
    crs="EPSG:4326"
)

if not os.path.exists("spatial_data/centers"):
    os.makedirs("spatial_data/centers")

gdf.to_file("spatial_data/centers/DataCenters.shp", driver="ESRI Shapefile")

print(f"Finished! Successfully geocoded {len(df_clean)} of {len(df)} records.")
print(df["match_method"].value_counts())