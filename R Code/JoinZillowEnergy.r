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



vars_to_impute <- c("avg_price","price_change","pct_change", "comm_rate", "ind_rate", "res_rate")

city_quality <- final_df %>%
  group_by(City, year) %>%
  summarise(
    across(all_of(vars_to_impute),
           ~ mean(is.na(.x)),
           .names = "missing_{.col}"),
    .groups = "drop"
  )


zip_nn_impute <- function(df, var, k = 3) {

  # Check missing share
  if (mean(is.na(df[[var]])) > 0.5) return(df)

  df <- df %>%
    mutate(zip_num = as.numeric(RegionName))

  missing_idx <- which(is.na(df[[var]]))
  observed_idx <- which(!is.na(df[[var]]))

  if (length(observed_idx) == 0) return(df)

  for (i in missing_idx) {
    distances <- abs(df$zip_num[observed_idx] - df$zip_num[i])

    nearest <- observed_idx[order(distances)][1:min(k, length(observed_idx))]

    df[[var]][i] <- mean(df[[var]][nearest], na.rm = TRUE)
  }

  df
}


final_imputed <- final_df

for (v in vars_to_impute) {
  final_imputed <- final_imputed %>%
    group_by(City, year) %>%
    group_modify(~ zip_nn_impute(.x, v, k = 5)) %>%
    ungroup()
}


final_imputed <- final_imputed %>%
  mutate(across(all_of(vars_to_impute),
                ~ ifelse(is.na(final_df[[cur_column()]]), "imputed", "observed"),
                .names = "{.col}_flag"))


final_imputed %>%
  summarise(across(all_of(vars_to_impute), ~ mean(is.na(.x))))



# Save
write_csv(final_imputed, "data/ZillowEnergy.csv")
