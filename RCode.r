library(tidyverse)
library(tigris)
library(sf)

df <- read.csv("/mnt/c/Users/rodri/Downloads/zillow_data.csv")

df


# Download all US Zip Codes (ZCTAs) for 2020
# Note: This is a large file!
zips <- zctas(cb = TRUE, year = 2020)

# If you only want specific Zip Codes (e.g., Chicago area)
chicago_zips <- zctas(cb = TRUE, starts_with = c("606", "607", "608"), year = 2020)

# View the map to confirm
plot(st_geometry(chicago_zips))


# Assuming your Zillow data has a column named 'zip'
final_map_data <- chicago_zips %>%
  left_join(df, by = c("ZCTA5CE20" = "zip"))

# Simple visualization
library(ggplot2)
ggplot(final_map_data) +
  geom_sf(aes(fill = price)) + # Replace 'price' with your actual column name
  theme_minimal()
