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
df = pd.read_csv('data/housing_and_data_centers_data/il_in_wi_datacenters.csv')

IL_IN_WI_CITIES = [
    # Illinois
    "Chicago", "Aurora", "Bloomington", "Peoria", "Champaign",
    "Springfield", "Rockford", "Edwardsville", "Rantoul",
    # Indiana
    "Columbus", "Hammond", "Indianapolis", "South Bend", "Fort Wayne",
    "Gary", "Evansville", "La Porte", "Jeffersonville", "Noblesville", "Portage",
    # Wisconsin
    "Appleton", "Eau Claire", "Green Bay", "Kenosha", "Madison",
    "Marshfield", "Milwaukee", "Wausau", "Wisconsin Rapids",
]

df = df[df["city_in_desc"].isin(IL_IN_WI_CITIES)].copy()

# --- 2. Deduplicate by Address BEFORE Geocoding ---
before = len(df)

# Normalize street for comparison: lowercase, strip whitespace
df["street_normalized"] = df["street"].str.lower().str.strip()

# Drop rows where the same street + city combo appears more than once
df = df.drop_duplicates(subset=["street_normalized", "city_in_desc"]).copy()

# Drop the helper column — no longer needed
df.drop(columns=["street_normalized"], inplace=True)

after = len(df)
print(f"Removed {before - after} duplicate address rows ({before} → {after} records)")

# --- 3. Initialize Geocoders ---
geolocator = Nominatim(user_agent="datacenters_geocoder_v2")
_geocode_osm = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

arcgis_geolocator = ArcGIS()
_geocode_arcgis = RateLimiter(arcgis_geolocator.geocode, min_delay_seconds=0.2)

# --- 4. Helper Functions ---
def clean_address(street):
    """Removes Suite, Floor, and extra noise that confuses Nominatim."""
    if not street or pd.isna(street):
        return ""
    s = re.split(r'#|Suite|Ste|Floor|Fl|Unit|,', street, flags=re.IGNORECASE)[0]
    return s.strip()

def geocode_robust(street, city, state, max_retries=3):
    """
    Waterfall Logic:
    1. OSM Structured (strict)
    2. OSM Cleaned Street
    3. ArcGIS Fallback
    4. OSM Street Only (last resort)
    """
    full_query = {"street": street, "city": city, "state": state, "country": "USA"}
    cleaned_street = clean_address(street)

    for attempt in range(max_retries):
        try:
            # Tier 1: Nominatim Strict
            loc = _geocode_osm(full_query)
            if loc:
                return loc, "osm_strict"

            # Tier 2: Nominatim Cleaned
            if cleaned_street != street:
                loc = _geocode_osm({"street": cleaned_street, "city": city, "state": state, "country": "USA"})
                if loc:
                    return loc, "osm_cleaned"

            # Tier 3: ArcGIS Fallback
            arcgis_query = f"{cleaned_street}, {city}, {state}, USA"
            loc = _geocode_arcgis(arcgis_query)
            if loc:
                return loc, "arcgis_fallback"

            # Tier 4: Street Only (OSM)
            street_only = ' '.join(cleaned_street.split()[1:]) if len(cleaned_street.split()) > 1 else None
            if street_only:
                loc = _geocode_osm({"street": street_only, "city": city, "state": state, "country": "USA"})
                if loc:
                    return loc, "osm_street_only"

            return None, "failed"

        except (GeocoderTimedOut, GeocoderUnavailable):
            time.sleep(2 ** attempt)

    return None, "timeout"

# --- 5. Geocode ---
print("Starting robust geocoding...")

results_list = []
for _, row in tqdm(df.iterrows(), total=len(df)):
    loc, method = geocode_robust(row["street"], row["city_in_desc"], row["state"])
    results_list.append({
        "location_obj": loc,
        "match_method": method,
        "latitude":  loc.latitude  if loc else None,
        "longitude": loc.longitude if loc else None,
    })

results_df = pd.DataFrame(results_list)
df = pd.concat([df.reset_index(drop=True), results_df], axis=1)

df["used_fallback"] = df["match_method"].apply(lambda x: x not in ["osm_strict", "failed"])
df.drop(columns=["location_obj"], inplace=True)

# --- 6. Secondary Deduplicate by Geocoded Coordinates ---
# Catches cases where two different address strings resolved to the same lat/lon
# (e.g. "350 E Cermak Rd" vs "350 East Cermak Road")
before_coord = len(df)
df = df.dropna(subset=["latitude", "longitude"])
df = df.drop_duplicates(subset=["latitude", "longitude"]).copy()
after_coord = len(df)
print(f"Removed {before_coord - after_coord} coordinate-level duplicates after geocoding ({before_coord} → {after_coord} records)")

# --- 7. Save Results ---
df_clean = df.copy()

gdf = gpd.GeoDataFrame(
    df_clean,
    geometry=gpd.points_from_xy(df_clean.longitude, df_clean.latitude),
    crs="EPSG:4326"
)

if not os.path.exists("spatial_data/centers"):
    os.makedirs("spatial_data/centers")

gdf.to_file("data/spatial_data/centers/ChicagoMetroDataCenters.shp", driver="ESRI Shapefile")

print(f"\nFinished! {len(df_clean)} unique datacenter locations saved.")
print(df["match_method"].value_counts())