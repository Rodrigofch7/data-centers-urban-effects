import pandas as pd
import geopandas as gpd
import numpy as np

# 1. Load data
data = pd.read_csv("data/ZillowEnergy.csv")
cities = gpd.read_file('/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/combined_cities.shp')

# 2. Standardize Join Keys
# (Ensure city_label exists in 'cities' before proceeding)
data["RegionName"] = data["RegionName"].astype(str).str.strip()
cities["NAME20"] = cities["NAME20"].astype(str).str.strip()



# Remove leading zeros from ZIP codes (e.g. '02108' -> '2108')
data["RegionName"] = (
    data["RegionName"]
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



# 3. Pivot the Energy Data (Only columns from the CSV)
df_pivoted = data.pivot_table(
    index='RegionName', 
    columns='year', 
    values=['avg_price', 'pct_change', 'comm_rate', 'ind_rate', 'res_rate'],
    aggfunc='mean'
)

# 4. Flatten the columns
df_pivoted.columns = [f'{metric}_{int(year)}' for metric, year in df_pivoted.columns]

# 5. Extract Metadata from CSV (Excluding city_label since it's in the Shapefile)
metadata = data.groupby('RegionName').agg({
    'state': 'first',
    'utility_name': 'first',
    'ownership': 'first',
    'service_type': 'first'
}).reset_index()


set(data["RegionName"]).intersection(set(cities["NAME20"]))


# 6. Combine CSV Metadata and Pivoted Rates
df_final = metadata.merge(df_pivoted, on='RegionName', how='inner')

# 7. THE MASTER MERGE (Left Join)
# 'cities' is on the left, so 'city_label' is preserved
merged_gdf = cities.merge(
    df_final, 
    left_on='NAME20', 
    right_on='RegionName', 
    how='left'
)

# 8. Set the index to city_label (which came from the Shapefile)
merged_gdf.set_index('city_label', inplace=True)

# 9. Cleanup
if 'RegionName' in merged_gdf.columns:
    merged_gdf = merged_gdf.drop(columns=['RegionName'])

# 10. Save as GeoJSON
output_path = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'
merged_gdf.to_file(output_path, driver='GeoJSON')

print(f"Process complete.")
print(f"Index successfully set to native 'city_label' from the Shapefile.")