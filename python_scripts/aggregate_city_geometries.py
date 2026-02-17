import geopandas as gpd
import pandas as pd
import glob
import os

# 1. Setup paths
input_folder = "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/"
output_path = os.path.join(input_folder, "combined_cities.shp")

# 2. Find all GeoJSON files in that directory
# This ensures we don't miss any of the 15 cities
files = glob.glob(os.path.join(input_folder, "*.geojson"))

if not files:
    print("No GeoJSON files found. Please check the directory path.")
else:
    print(f"Found {len(files)} files. Merging now...")

    gdfs = []
    for file in files:
        try:
            gdf = gpd.read_file(file)
            
            # Add a source column to identify the city after merging
            gdf['city_label'] = os.path.basename(file).replace('.geojson', '')
            
            # Ensure all files are in the same coordinate system (WGS84)
            gdf = gdf.to_crs(epsg=4326)
            
            gdfs.append(gdf)
        except Exception as e:
            print(f"Skipping {file} due to error: {e}")

    # 3. Combine everything
    # ignore_index=True prevents index duplication
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True, sort=False))

    # 4. Save to the specific location
    combined_gdf.to_file(output_path)

    print("--- Success! ---")
    print(f"Final file saved at: {output_path}")
    print(f"Total rows: {len(combined_gdf)}")
    print(f"Cities included: {combined_gdf['city_label'].unique()}")