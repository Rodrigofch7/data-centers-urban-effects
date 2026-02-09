library(tidyverse)
library(sf)
library(stringr)

# ─────────────────────────────────────────────
# 1. Load cities shapefile → ZIPs only, no geometry, remove leading zeros
# ─────────────────────────────────────────────
cities <- read_sf(
  "/home/rodrigofrancachaves/capp30122/group_project/project-datacenter-urban-effects/spatial_data/cities/combined_cities.shp"
) %>%
  st_drop_geometry() %>%
  transmute(
    zip = NAME20 %>%
      as.character() %>%
      str_trim() %>%
      str_replace("^0+", "")
  ) %>%
  distinct()

# ─────────────────────────────────────────────
# 2. Load Zillow data (remove leading zeros)
# ─────────────────────────────────────────────
zillow <- read_csv("data/zillow_annual_summary.csv") %>%
  filter(year >= 2021 & year < 2025) %>%
  mutate(
    RegionName = RegionName %>%
      as.character() %>%
      str_trim() %>%
      str_replace("^0+", ""),
    year = as.numeric(year)
  )

# ─────────────────────────────────────────────
# 3. Load Energy data (remove leading zeros)
# ─────────────────────────────────────────────
files <- list.files(
  path = "data/",
  pattern = "iou_zipcodes_\\d{4}\\.csv",
  full.names = TRUE
)

energy <- read_csv(files, id = "file_source") %>%
  mutate(
    year = as.numeric(str_extract(file_source, "\\d{4}")),
    zip = zip %>%
      as.character() %>%
      str_trim() %>%
      str_replace("^0+", "")
  )

# ─────────────────────────────────────────────
# 4. Ensure all shapefile ZIPs exist for all years
# ─────────────────────────────────────────────
zip_year_grid <- expand_grid(
  zip  = cities$zip,
  year = sort(unique(zillow$year))
)

# ─────────────────────────────────────────────
# 5. Join (nothing gets dropped)
# ─────────────────────────────────────────────
final_df <- zip_year_grid %>%
  left_join(zillow, by = c("zip" = "RegionName", "year" = "year")) %>%
  left_join(energy,  by = c("zip" = "zip",        "year" = "year")) %>%
  select(-file_source)



# ─────────────────────────────────────────────
# 6. Nearest Neighboor
# ─────────────────────────────────────────────
vars_to_impute <- c(
  "avg_price", "price_change", "pct_change",
  "comm_rate", "ind_rate", "res_rate"
)

zip_nn_impute <- function(df, var, k = 10) {

  if (mean(is.na(df[[var]])) > 0.5) return(df)

  df <- df %>% mutate(zip_num = as.numeric(zip))

  missing_idx  <- which(is.na(df[[var]]))
  observed_idx <- which(!is.na(df[[var]]))

  if (length(observed_idx) == 0) return(df)

  for (i in missing_idx) {
    distances <- abs(df$zip_num[observed_idx] - df$zip_num[i])
    nearest <- observed_idx[order(distances)][1:min(k, length(observed_idx))]
    df[[var]][i] <- mean(df[[var]][nearest], na.rm = TRUE)
  }

  df %>% select(-zip_num)
}

final_imputed <- final_df

for (v in vars_to_impute) {
  final_imputed <- final_imputed %>%
    group_by(City, year) %>%
    group_modify(~ zip_nn_impute(.x, v, k = 5)) %>%
    ungroup()
}

# ─────────────────────────────────────────────
# 6. Save
# ─────────────────────────────────────────────
write_csv(final_imputed, "data/ZillowEnergy.csv")













