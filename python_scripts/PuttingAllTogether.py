import pandas as pd
import geopandas as gpd

# 1. Load data
data = pd.read_csv("data/ZillowEnergy.csv")
cities = gpd.read_file('/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/combined_cities.shp')

# 2. Filter data for your cities
data["RegionName"] = data["RegionName"].astype(str)
cities["NAME20"] = cities["NAME20"].astype(str)
zip_codes_in_cities = cities["NAME20"].unique()
filtered_data = data[data["RegionName"].isin(zip_codes_in_cities)]

# 3. Pivot EVERYTHING
# We add all your rate columns to the 'values' list
df_pivoted = filtered_data.pivot_table(
    index='RegionName', 
    columns='year', 
    values=['avg_price', 'pct_change', 'comm_rate', 'ind_rate', 'res_rate'],
    aggfunc='mean'
)

# 4. Flatten the columns 
# This creates names like 'res_rate_2023', 'ind_rate_2023', etc.
df_pivoted.columns = [f'{metric}_{int(year)}' for metric, year in df_pivoted.columns]

# 5. Handle the metadata (State, Utility Name, Ownership)
# Since these are usually the same for a RegionName across years, 
# we grab the 'first' instance so they stay in your final file.
metadata = filtered_data.groupby('RegionName').agg({
    'state': 'first',
    'utility_name': 'first',
    'ownership': 'first',
    'service_type': 'first'
}).reset_index()

# 6. Merge Metadata + Pivoted Rates
df_final = metadata.merge(df_pivoted, on='RegionName')

# 7. Save
df_final.to_csv("data/ZillowEnergyFiltered.csv", index=False)

print(f"Done! Created {len(df_final.columns)} columns.")




# 1. Perform the merge
# We merge the pivoted data (df_final) into the GeoDataFrame (cities)
# cities is the 'left' table to preserve the geometry
merged_gdf = cities.merge(
    df_final, 
    left_on='NAME20', 
    right_on='RegionName', 
    how='left'
)

# 2. Cleanup (Optional but recommended)
# Since you have both 'NAME20' and 'RegionName', you can drop the duplicate ID column
if 'RegionName' in merged_gdf.columns:
    merged_gdf = merged_gdf.drop(columns=['RegionName'])

# 3. Save the result
# Save as a GeoPackage (.gpkg) or GeoJSON if the column names are long.
# Note: Standard Shapefiles (.shp) have a 10-character limit for column names!
output_path = '/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/cities_with_energy_home_prices.geojson'

merged_gdf.to_file(output_path, driver='GeoJSON')

print(f"Successfully saved merged spatial data to: {output_path}")