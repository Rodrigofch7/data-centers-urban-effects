library(tidyverse)
library(lubridate)

# 1. Load data - using read_csv
zillow <- read_csv('/mnt/c/Users/rodri/Desktop/UChicago/2.SecondQuarter/Computer Science with Applications 2/Project/ZillowData/zillow_data_zip_code.csv')

# 2. Pivot & Clean
zillow_annual <- zillow %>%
  # UPDATED: Since your columns are named "2000-01-31", we select 
  # columns that start with a digit (2) instead of "X"
  pivot_longer(
    cols = matches("^\\d"), 
    names_to = "date_raw", 
    values_to = "price"
  ) %>%
  mutate(
    # ymd() handles "2000-01-31" perfectly without needing gsub
    date = ymd(date_raw),
    year = year(date),
    # Ensure Zip Codes are 5-digit strings to prevent join errors later
    RegionName = str_pad(as.character(RegionName), width = 5, side = "left", pad = "0")
  ) %>%
  filter(!is.na(price)) %>%
  
  # 3. Aggregate - Keeping City and other metadata
  group_by(RegionName, City, State, CountyName, year) %>%
  summarize(
    avg_price = mean(price, na.rm = TRUE), 
    .groups = "drop"
  ) %>%
  
  # 4. Calculate Growth Metrics (handling the Lags properly)
  group_by(RegionName) %>%
  arrange(year) %>%
  mutate(
    price_change = avg_price - lag(avg_price),
    pct_change = (price_change / lag(avg_price)) * 100
  ) %>%
  ungroup()

# 5. Save results
# Creating the data directory if it doesn't exist
if(!dir.exists("data")) dir.create("data")
write_csv(zillow_annual, "data/zillow_annual_summary.csv")

# Quick check to make sure City is there
head(zillow_annual)