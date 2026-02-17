library(tidyverse)
library(tigris)
library(sf)

# 1. Setup folder
if (!dir.exists("spatial_data")) dir.create("spatial_data")

# 2. Define your cities (using a named vector for easier iteration)
cities_list <- list(
  "New York" = "NY", "Los Angeles" = "CA", "Chicago" = "IL", 
  "Houston" = "TX", "Phoenix" = "AZ", "Philadelphia" = "PA", 
  "San Antonio" = "TX", "San Diego" = "CA", "Dallas" = "TX", 
  "Jacksonville" = "FL", "Miami" = "FL", "Boston" = "MA", 
  "Atlanta" = "GA", "Santa Clara" = "CA", "Denver" = "CO"
)

# 3. Load ZCTAs (Doing this once saves a lot of time)
# cb = TRUE keeps the file size manageable
all_zips <- zctas(cb = TRUE, year = 2020)

# 4. Loop through cities to extract and save
for (city_name in names(cities_list)) {
  state_abbr <- cities_list[[city_name]]
  
  # Get the city boundary
  city_boundary <- places(state = state_abbr, cb = TRUE) %>%
    filter(NAME == city_name)
  
  # Find ZCTAs that intersect with the city boundary
  # We use [city_boundary, ] as a spatial subset
  city_zips <- all_zips[city_boundary, ]
  
  # Create a clean filename
  file_path <- paste0("spatial_data/cities", gsub(" ", "_", tolower(city_name)), ".geojson")
  
  # Save the file
  st_write(city_zips, file_path, delete_dsn = TRUE)
  
  message(paste("Saved:", city_name))
}
