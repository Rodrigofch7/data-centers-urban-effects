library(tidyverse)
library(sf)
library(stringr)

# 1. Load Zillow Data
zillow <- read_csv("data/zillow_annual_summary.csv") %>%
  filter(year >= 2021 & year < 2025) %>%
  mutate(
    # Pad with leading zeros to 5 digits to ensure matching works
    RegionName = str_pad(as.character(RegionName), width = 5, side = "left", pad = "0"),
    year = as.numeric(year)
  )

# 2. Load Energy Data
folder_path <- "data/" 
files <- list.files(path = folder_path, pattern = "iou_zipcodes_\\d{4}\\.csv", full.names = TRUE)

# read_csv is faster and handles column types better than read.csv
energy <- read_csv(files, id = "file_source") %>%
  mutate(
    year = as.numeric(str_extract(file_source, "\\d{4}")),
    # Pad energy zips to match Zillow format
    zip = str_pad(as.character(zip), width = 5, side = "left", pad = "0")
  )

# 3. Join - Use left_join to keep Zillow rows even if Energy data is missing
# This prevents "dropping" rows and instead preserves them with NA values
final_df <- left_join(zillow, energy, 
                       by = c("RegionName" = "zip", "year" = "year"))

# 4. Final Clean
# Optional: remove the 'file_source' column to keep the CSV clean
final_df <- final_df %>% select(-file_source)

# Save
write_csv(final_df, "data/ZillowEnergy.csv")
