## 🚀 Live Dashboard
**[View Interactive Dashboard →](https://rodrigofrancac.shinyapps.io/project-datacenter-urban-effects/)**

# Data Centers Next Door: How Cloud Infrastructure Shapes Housing and Local Resource Costs.

> A computational and data-driven analysis of the impact of cloud infrastructure development on housing prices in Chicago.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Data Sources](#data-sources)
- [Data Processing & Reconcilitation](#data-processing-&-reconcilitation)
- [Data Analysis](#data-analysis)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

This project investigates the relationship between large-scale cloud infrastructure development and housing price dynamics in Chicago between 2000 and 2025. Specifically, we analyze whether the construction and operation of data centers are associated with measurable changes in local housing costs.

We collected and cleaned data center location data and constructed a curated dataset of confirmed facilities with a first_permit variable approximating when each data center began development or operations. We then integrate this dataset with historical housing price data at the ZIP code level to explore spatial and temporal patterns.

The project combines data cleaning, record linkage, and geospatial visualization techniques to generate an index trend, heat map, and other visual tools that help describe potential correlations between data center expansion and housing price changes. Our goal is not to claim causation, but to provide a data-driven foundation for understanding how digital infrastructure may interact with urban housing markets.

---

## Features

- **Data Cleaning & Deduplication** — Consolidates and cleans raw data center and housing records, removing duplicates and unmatched entries.
- **Chicago-Focused Dataset** — Filters national data to construct a curated dataset of confirmed Chicago data centers and housing prices.
- **First Permit Construction** — Builds a first_permit variable to approximate when each data center began development or operations.
- **Housing Market and Utility Data Integration** — Merges data center data with ZIP code–level housing price data and utility/household cost data (2000–2025).
- **Spatial & Temporal Visualization** — Generates trend index, heat map, and other visualizations to explore correlations between infrastructure expansion and housing prices.

---

## Data Sources
| Source | Description |
|---|---|
| [Data Center Map](https://www.datacentermap.com/usa/illinois/chicago/) | A publicly accessible directory of data center facilities in the Chicago metropolitan area, listing sites with basic location and provider information. The database aggregates facility listings from operators and external sources to provide insight into the presence and distribution of data infrastructure in Chicago. |
| [Zillow](https://www.zillow.com/research/data/) | A comprehensive public repository from Zillow that provides historical and current data on U.S. housing markets. The site offers downloadable datasets such as the Zillow Home Value Index (ZHVI), which tracks home prices across regions and over time, making it useful for analyzing housing price trends. |
| [IPUMS NHGIS](https://www.nhgis.org/) | The National Historical Geographic Information System, maintained by IPUMS, provides free online access to summary statistics and GIS boundary files for U.S. census data across time. Used here to obtain geographic, demographic, utility, and household cost data at the ZIP code and tract level for the Chicago metro area. |
| [U.S. Census Bureau API](https://www.census.gov/data/developers/data-sets.html) | The official Census Bureau developer API, used to retrieve American Community Survey (ACS) estimates including demographic, economic, and housing characteristics at the ZIP code tabulation area (ZCTA) level. |
| [TIGRIS (R package)](https://github.com/walkerke/tigris) | An R package that provides programmatic access to U.S. Census Bureau TIGER/Line shapefiles, including boundaries for ZIP code tabulation areas, counties, and other geographies. Used to retrieve spatial boundary files for mapping and spatial joins. |
---

## Data Processing & Reconciliation

This project integrates infrastructure, housing, and demographic data from multiple sources. Data center locations were scraped and geocoded for spatial analysis. Housing price data (Zillow) was aggregated from monthly to annual values to align with socioeconomic indicators retrieved via the Census API (ACS 5-year estimates). Utility and housing cost consumer expenditure data were downloaded from IPUMS NHGIS database. All datasets were reconciled using geographic identifiers (ZIP codes and Census tracts) to enable spatial and temporal analysis.

**Utility and Household Cost Cleaning**
The raw data for both were separate 5-year ACS estimates, meaning each csv was for data sampled over a 5-year period. For utility (electricity and water/sewage data), this only ranges from 2017-2021 to 2020-2024 5 year periods. Household cost data was included as an alternative data source because it ranges back to the 2007-2011 5-year period, and captures utility costs among other costs. According to the ACS 2024 [subject definitions](https://www2.census.gov/programs-surveys/acs/tech_docs/subject_definitions/2024_ACSSubjectDefinitions.pdf), "selected monthly owner costs are the sum of payments for mortgages, deeds of trust, contracts to purchase, or similar debts on the property (including payments for the first mortgage, second mortgages, home equity loans, and other junior mortgages); real estate taxes; fire, hazard, and flood insurance on the property; utilities (electricity, gas, and water and sewer); and fuels (oil, coal, kerosene, wood, etc.). It also includes, where appropriate, the monthly homeowners association (HOA) fee and/or condominium fee (Question 16) and mobile home costs (Question 24) (personal property
taxes, site rent, registration fees, and license fees)." 

The raw data sources take the form of price ranges/buckets (e.g. for a given zip code in a 5-year period, 50 people paid between \$0-50 for electricity, 20 paid \$50-100, and so on). This is the case for electricity, water/sewage, and household cost data. In order to numerically quantify the typical expenditure for these variables for a zip code in a 5-year period, a score was constructed by factorizing each bucket into a number. For example, 1 was assigned to \$0-50, 2 was assigned to \$50-100, up to how ever many buckets there were. Importantly, these price ranges are not the same between variables. This means that water/sewage had different price ranges (\$0-100, \$100-200, and so on) than electricity or household costs. After buckets were factorized to numbers, each zip code was assigned a score based on the weighted sum of each factor, as shown by the formula below:

$$
score_{zip,t} = \sum_{i=0}^Ni\frac{n_i}{n_{total}} = 1*\frac{n_1}{n_{total}}+2*\frac{n_2}{n_{total}}+\dots
$$

where $n_i$ represents the number of respondents for the $i$th bucket. So $n_1$ would be the number of people who indicated that they pay between \$0-50, and $\frac{n_1}{n_{total}}$ is the proportion of all respondents who indicated so. This scoring method was applied to electricity data, water/sewage data, and household cost data to get electricity cost scores, water/sewage cost scores, and household cost scores across all zip codes in all 5-year periods available.

---

## Data Analysis

We implement a composite index based the changes in housing prices and household costs (e.g. electricity and ultility costs) pre- and post-data center's first permitting. The allows us to see the relative impact of the data center on the neighborhood for a specfic timeframe.  

The calculation of the index begins with the assignment of a standardized score based on decile-based rankings using empirical quantiles. Each data center is assigned to one of ten equally sized bins, with lower deciles corresponding lower scores and higher deciles corresponding to higher scores. 

As an alternative specification, we also implement a z-score normalization approach, which standardizes variables by centering them around the mean and scaling by their standard deviation. This allows comparison across variables with different units of measurement and captures relative deviations rather than rank positions.

A higher index score suggests that the data center had more of a costly impact on housing prices and household expenses (and vice versa for a lower index score). Please note that the implementation of these indices are not causal in nature, but rather aim to capture assocations between data centers and housing costs/prices in an easier to digest manner. For a more causal analysis, we suggest a Differences-in-Differences regression model.   

For full technical documentation and mathematical formulation, see data_centers_next_door/data_analysis/DataMethodology.md￼.
---

## Getting Started

### Prerequisites

Before running the project, make sure you have:

- Python 3.10+
- git uv package manager
- Git
- R (for spatial processing scripts)

### General installation

```bash
# Clone the repository
git clone https://github.com/<YOUR-USERNAME>/project-datacenter-urban-effects.git

# Navigate into the project
cd project-datacenter-urban-effects
```

### Install Python dependencies

Using uv:

```bash
uv sync
```

### Configuration

1. Ensure all required datasets are located in the data/ directory.
2. Verify file paths inside Python scripts (e.g., data/top_us_cities_datacenters.csv) match your local structure.

---

## Usage

The project can be used in two main ways, you can reproduce the data pipeline or run the interactive dashboard

**Reproduce the Data Pipeline**

From the project root:

```bash
# Clean and filter Chicago data centers
uv run python_scripts/chicago_data_centers.py

# Process Zillow housing data
uv run python_scripts/zillow_data.py

# Prepare merged dataset for dashboard
uv run python_scripts/preparing_data_for_dashboard.py
```

This will:
1. Filter data centers to Chicago
2. Construct the first_permit variable
3. Merge housing and infrastructure datasets
4. Generate cleaned outputs in the data/ directory

**Run the Dashboard**

From the repo root:
```bash
uv run shiny run shiny_app.app
```
or
```bash
uv run shiny run shiny_app/app.py
```
This launches the interactive visualization environment.
---

## Project Structure

```
.
├── README.md
├── __pycache__
│   ├── cleaning_utilities.cpython-313.pyc
│   ├── conftest.cpython-313-pytest-9.0.2.pyc
│   ├── datacenters_housing_merge.cpython-313.pyc
│   └── datacentersvis.cpython-313.pyc
├── data
│   ├── Visualizations
│   │   ├── data_centers_over_time.html
│   │   ├── datacenters_vis_company.html
│   │   ├── datacenters_vis_zipcode.html
│   │   ├── housing_cost_dumbbell.html
│   │   ├── housing_price_dumbbell.html
│   │   └── impact_score_bar_chart.html
│   ├── chicago_data_centers.csv
│   ├── chicago_data_centers_2.csv
│   ├── chicago_data_centers_final.csv
│   ├── chicago_data_centers_final_w_changes.csv
│   ├── chicago_data_centers_impact_scores.csv
│   ├── chicago_metro_zips.csv
│   ├── clean_elecwater_hc_scores
│   │   ├── elec_water_cleaned.csv
│   │   ├── monthHHC_cleaned.csv
│   │   └── pivoted_HHCScores.csv
│   ├── energy and water data
│   │   ├── codebooks
│   │   │   ├── nhgis0003_ds255_20215_zcta_codebook.txt
│   │   │   ├── nhgis0003_ds263_20225_zcta_codebook.txt
│   │   │   ├── nhgis0003_ds268_20235_zcta_codebook.txt
│   │   │   └── nhgis0003_ds273_20245_zcta_codebook.txt
│   │   ├── nhgis0003_ds255_20215_zcta.csv
│   │   ├── nhgis0003_ds263_20225_zcta.csv
│   │   ├── nhgis0003_ds268_20235_zcta.csv
│   │   ├── nhgis0003_ds273_20245_zcta.csv
│   │   └── nhgis_energy_water_wide.csv
│   ├── hhc
│   │   ├── codebook
│   │   │   ├── nhgis0007_ds185_20115_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds192_20125_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds202_20135_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds207_20145_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds216_20155_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds226_20165_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds234_20175_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds240_20185_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds245_20195_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds250_20205_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds255_20215_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds263_20225_zcta_codebook.txt
│   │   │   ├── nhgis0007_ds268_20235_zcta_codebook.txt
│   │   │   └── nhgis0007_ds273_20245_zcta_codebook.txt
│   │   ├── nhgis0007_ds185_20115_zcta.csv
│   │   ├── nhgis0007_ds192_20125_zcta.csv
│   │   ├── nhgis0007_ds202_20135_zcta.csv
│   │   ├── nhgis0007_ds207_20145_zcta.csv
│   │   ├── nhgis0007_ds216_20155_zcta.csv
│   │   ├── nhgis0007_ds226_20165_zcta.csv
│   │   ├── nhgis0007_ds234_20175_zcta.csv
│   │   ├── nhgis0007_ds240_20185_zcta.csv
│   │   ├── nhgis0007_ds245_20195_zcta.csv
│   │   ├── nhgis0007_ds250_20205_zcta.csv
│   │   ├── nhgis0007_ds255_20215_zcta.csv
│   │   ├── nhgis0007_ds263_20225_zcta.csv
│   │   ├── nhgis0007_ds268_20235_zcta.csv
│   │   └── nhgis0007_ds273_20245_zcta.csv
│   ├── housing_and_data_centers_data
│   │   ├── chicago_data_centers.csv
│   │   ├── chicago_data_centers_match (first_permit).csv
│   │   ├── datacenters_housing_merged.csv
│   │   ├── il_in_wi_datacenters.csv
│   │   ├── top_us_cities_datacenters.csv
│   │   ├── zillow_chicago_metro_region.csv
│   │   └── zillow_yearly_estimates_chicago_metro.csv
│   ├── housing_cost_data.csv
│   ├── scratch_data
│   │   └── chicago_data_centers_2.csv
│   └── spatial_data
│       ├── centers
│       │   ├── ChicagoDataCentersWithConstructionDate.parquet
│       │   ├── ChicagoMetroDataCenters.cpg
│       │   ├── ChicagoMetroDataCenters.dbf
│       │   ├── ChicagoMetroDataCenters.prj
│       │   ├── ChicagoMetroDataCenters.shp
│       │   ├── ChicagoMetroDataCenters.shx
│       │   ├── DataCenters.cpg
│       │   ├── DataCenters.dbf
│       │   ├── DataCenters.prj
│       │   ├── DataCenters.shp
│       │   ├── DataCenters.shx
│       │   └── DataCentersChicagoMetroArea.parquet
│       └── cities
│           └── ChicagoMetroArea.parquet
├── data_centers_next_door
│   ├── __init__.py
│   ├── __pycache__
│   │   └── __init__.cpython-313.pyc
│   ├── data_analysis
│   │   ├── DataMethodology.md
│   │   ├── __pycache__
│   │   │   ├── index.cpython-313.pyc
│   │   │   └── index_creation.cpython-313.pyc
│   │   ├── index.py
│   │   ├── index_creation.py
│   │   └── tests_index_dummy_data.csv
│   ├── data_preparation
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-313.pyc
│   │   │   ├── chicago_dc_clean_merge.cpython-313.pyc
│   │   │   ├── datacenters_housing_merge.cpython-313.pyc
│   │   │   └── zillow_data.cpython-313.pyc
│   │   ├── chicago_dc_clean_merge.py
│   │   ├── datacenters_housing_merge.py
│   │   ├── preparing_data_for_dashboard.py
│   │   ├── processing_water_energy.py
│   │   └── zillow_data.py
│   ├── data_visualizations
│   │   ├── __pycache__
│   │   │   ├── datacenters_by_zipcomp.cpython-313.pyc
│   │   │   ├── hp_hc_dumbnell_plots.cpython-313.pyc
│   │   │   └── impact_score_bar_chart.cpython-313.pyc
│   │   ├── data_centers_over_time_viz.py
│   │   ├── datacenters_by_zipcomp.py
│   │   ├── hp_hc_dumbnell_plots.py
│   │   └── impact_score_bar_chart.py
│   ├── geocoding
│   │   ├── geocoding.py
│   │   └── geocoding_chicago_metro_area.py
│   ├── hc_and_utility_scores
│   │   ├── __pycache__
│   │   │   └── cleaning_utilities.cpython-313.pyc
│   │   └── cleaning_utilities.py
│   └── webscrapping
│       ├── __pycache__
│       │   ├── webscrapping_data_centers.cpython-313.pyc
│       │   └── webscrapping_data_centers_chicago_metro_region.cpython-313.pyc
│       ├── webscrapping_data_centers.py
│       └── webscrapping_data_centers_chicago_metro_region.py
├── milestones
│   ├── milestone1.md
│   ├── milestone1.md:Zone.Identifier
│   └── milestone2.md
├── pyproject.toml
├── requirements.txt
├── shiny_app
│   ├── Data
│   │   ├── Chicago.gpkg
│   │   ├── ChicagoDataCenters.gpkg
│   │   ├── chicag_data_centers_impact_scores.csv
│   │   ├── chicago_data_centers_final.csv
│   │   ├── chicagoproper.gpkg
│   │   ├── cook_county.gpkg
│   │   ├── datacenters_housing_merged.csv
│   │   ├── illinois.gpkg
│   │   └── uchicago_logo.png
│   ├── __pycache__
│   │   └── app.cpython-313.pyc
│   ├── app.py
│   ├── requirements.txt
│   └── rsconnect-python
│       └── shiny_app.json
├── tests
│   ├── __pycache__
│   │   ├── test_clean_merge.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_cleaning_utilities.cpython-312-pytest-7.4.4.pyc
│   │   ├── test_cleaning_utilities.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_dumbnell_bar_charts.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_index.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_webscrapping.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_webscrapping_data_centers_chicago_metro_region.cpython-313-pytest-9.0.2.pyc
│   │   ├── test_zillow.cpython-313-pytest-9.0.2.pyc
│   │   └── webscrapping_test.cpython-313-pytest-9.0.2.pyc
│   ├── test_clean_merge.py
│   ├── test_cleaning_utilities.py
│   ├── test_dumbnell_bar_charts.py
│   ├── test_index.py
│   ├── test_webscrapping.py
│   ├── test_webscrapping_data_centers_chicago_metro_region.py
│   └── test_zillow.py
└── uv.lock
```

---

## Contributing

We welcome contributions that expand and strengthen this project beyond the course timeline.

If you’re interested in contributing, please review the guidelines in CONTRIBUTING.md￼before submitting changes.

**Areas Where We Need Help**

1. Expanding Data Center Coverage:
- Identifying additional data centers in Chicagoland and Illinois.
- Identifying / Verifying operational start dates.
- Cross-referencing facilities across multiple public and private sources.
	
2.	Infrastructure Cost Data:
- Collecting historical and current data on:
    Electricity prices
    Water usage and water costs
- Linking infrastructure demand to local resource pricing.

3. Improved Record Linkage & Matching
- Enhancing data matching methods across datasets.

4.	Causal & Econometric Extensions
- Designing quasi-experimental approaches (e.g., difference-in-differences).
- Incorporating zoning, tax incentives, or development permits.
	
5.	Visualization & Dashboard Enhancements
- Improving spatial visualizations.
- Adding new metrics to the composite index.
- Enhancing dashboard interactivity.

**How to Contribute:**

1. Fork the repository.
2. Create a new feature branch.
3. Follow the contribution guidelines in CONTRIBUTING.md.
4. Submit a pull request with a clear description of changes.
5. Ensure all scripts run reproducibly before submitting.

---

## License

This project is released under an open-source license. 
See the LICENSE.md file for details.

---

## Contact

**Logan Burton** — [@loganburton](https://github.com/StLaurentMTL) — lburton12@uchicago.edu

**Rodrigo Chaves** — [@rchaves](https://github.com/Rodrigofch7) — rchaves@uchicago.edu

**Sinan Grehan** — [@sinangrehan](https://github.com/sinangrehan) — sinangrehan@uchicago.edu

**Carlos Eduardo Vargas** — [@cev2030](https://github.com/cev2030) — cev@uchicago.edu

Project Link: [https://github.com/uchicago-2026-capp30122/project-datacenter-urban-effects]
