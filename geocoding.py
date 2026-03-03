from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import re
import pandas as pd
from tqdm.auto import tqdm
import geopandas as gpd
from shapely.geometry import Point


df = pd.read_csv("top_10_us_cities_datacenters.csv")


geolocator = Nominatim(user_agent="chicago_datacenters_geocoder")
_geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)


def geocode_address(addr):
    return _geocode(addr)


def clean_address(addr):
    return re.sub(r"\b([NSEW])\.\b", r"\1", addr)


df["full_address"] = (
    df["street"].str.strip()
    + ", "
    + df["city"].fillna("Chicago").str.strip()
    + ", IL, USA"
)

df["full_address_clean"] = df["full_address"].apply(clean_address)

# ✅ tqdm loop (robust)
locations = []
for addr in tqdm(df["full_address_clean"], total=len(df)):
    locations.append(geocode_address(addr))

df["location"] = locations

df["latitude"] = df["location"].apply(lambda loc: loc.latitude if loc else None)
df["longitude"] = df["location"].apply(lambda loc: loc.longitude if loc else None)

df.drop(columns=["location"], inplace=True)


# Create geometry column (lon, lat!)
gdf["geometry"] = [Point(xy) for xy in zip(gdf["longitude"], gdf["latitude"])]

# Create GeoDataFrame in WGS84
gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")

gdf = gdf.to_crs(epsg=4326)  # US NAD83

# Save shapefile
gdf.to_file("ChicagoDataCenters.shp", driver="ESRI Shapefile")
