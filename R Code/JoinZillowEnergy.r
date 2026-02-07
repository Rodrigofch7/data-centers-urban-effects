library(tidyverse)
library(sf)
library(stringr)



zillow <- read.csv("data/zillow_annual_summary.csv")


zillow <- zillow %>% 
  filter(year >= 2021 & year < 2025)


folder_path <- "C:/Users/rodri/Downloads/EnergyData/"
files <- list.files(path = folder_path, pattern = "*.csv", full.names = TRUE)

energy <- read_csv(files, id = "file_source")

energy <- energy %>%
  mutate(year = as.numeric(str_extract(file_source, "\\d{4}"))) %>%
  # Standardize zip to character to avoid leading zero issues (e.g., 02108)
  mutate(zip = as.character(zip))



zillow <- zillow %>%
  mutate(
    RegionName = as.character(RegionName),
    year = as.numeric(year)
  )


final_df <- inner_join(zillow, energy, 
                       by = c("RegionName" = "zip", "year" = "year"))



write.csv(final_df, row.names = FALSE, col.names = FALSE, "C:/Users/rodri/Desktop/UChicago/2.SecondQuarter/Computer Science with Applications 2/Project/ZillowEnergy.csv")
