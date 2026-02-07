library(tidyverse)
library(sf)
library(stringr)

# Use relative paths so your teammates can run this too!
zillow <- read.csv("data/zillow_annual_summary.csv")

zillow <- zillow %>% 
  filter(year >= 2021 & year < 2025)

# If the energy files are inside your repo's data folder:
folder_path <- "data/" 
# OR if you must point to your Windows Downloads folder from WSL:
# folder_path <- "/mnt/c/Users/rodri/Downloads/EnergyData/"

files <- list.files(path = folder_path, pattern = "iou_zipcodes_\\d{4}\\.csv", full.names = TRUE)

energy <- read_csv(files, id = "file_source")

energy <- energy %>%
  mutate(year = as.numeric(str_extract(file_source, "\\d{4}")),
         zip = as.character(zip))

zillow <- zillow %>%
  mutate(
    RegionName = as.character(RegionName),
    year = as.numeric(year)
  )

final_df <- inner_join(zillow, energy, 
                       by = c("RegionName" = "zip", "year" = "year"))

# Saving to the project data folder instead of a local Desktop path
write.csv(final_df, "data/ZillowEnergy.csv", row.names = FALSE)
