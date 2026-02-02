import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from tqdm.auto import tqdm
import os

# Load data
df = pd.read_csv('top_10_us_cities_datacenters.csv')

# Initialize Geocoder
geolocator = Nominatim(user_agent="datacenters_geocoder")
_geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

def geocode_address(street, state, city):
    # Using a structured query guarantees the result stays in the correct state
    return _geocode({
        "street": street,
        "city": city,
        "state": state,
        "country": "USA"
    })

# --- Geocoding Execution ---
print("Starting geocoding...")
locations = []
for street, state, city in tqdm(zip(df["street"], df["state"], df["city_in_desc"]), total=len(df)):
    locations.append(geocode_address(street, state, city))

# Assign results
df["location"] = locations
df["latitude"] = df["location"].apply(lambda loc: loc.latitude if loc else None)
df["longitude"] = df["location"].apply(lambda loc: loc.longitude if loc else None)

# Drop the raw location object before saving
df.drop(columns=["location"], inplace=True)

# --- GeoDataFrame Creation ---
# Create GeoDataFrame in WGS84 (lat/lon)
gdf = gpd.GeoDataFrame(
    df, 
    geometry=gpd.points_from_xy(df.longitude, df.latitude),
    crs="EPSG:4326"
)

# Ensure the output directory exists
if not os.path.exists("spatial_data"):
    os.makedirs("spatial_data")

# Save shapefile
gdf.to_file(
    "spatial_data/centers/DataCenters.shp",
    driver="ESRI Shapefile"
)
