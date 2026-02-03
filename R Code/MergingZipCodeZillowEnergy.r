library(tidyverse)
library(sf)
library(languageserver)

zillow = read.csv('/mnt/c/Users/rodri/Desktop/UChicago/2.SecondQuarter/Computer Science with Applications 2/Project/ZillowData/zillow_data_zip_code.csv')

head(zillow)

# Run the pivot
zillow_long <- zillow %>%
  pivot_longer(
    cols = starts_with("X"), 
    names_to = "date_raw", 
    values_to = "price"
  )

# Check the intermediate result
head(zillow_long) 

zillow_clean <- zillow_long %>%
  mutate(
    # format = "X%Y.%m.%d" tells R to look for the X, 
    # then 4-digit Year, then dot, then Month, dot, then Day
    date = as.Date(date_raw, format = "X%Y.%m.%d"),
    year = as.numeric(format(date, "%Y"))
  )

# Verify it worked
head(zillow_clean)


zillow_annual <- zillow_clean %>%
  # Group by Zip Code and Year
  group_by(RegionName, year) %>%
  summarize(avg_price = mean(price, na.rm = TRUE), .groups = "drop") %>%
  # Group by Zip Code only to calculate the change over time
  group_by(RegionName) %>%
  arrange(year) %>%
  mutate(
    price_change = avg_price - lag(avg_price),
    pct_change = (price_change / lag(avg_price)) * 100
  )

# View your final project-ready data
head(zillow_annual)


write_csv(zillow_annual, "zillow_annual_summary.csv")
