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
- [Data Methodology](#data-methodology)
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
- **Housing Market Integration** — Merges data center data with ZIP code–level housing price data (2000–2025).
- **Spatial & Temporal Visualization** — Generates trend index, heat map, and other visualizations to explore correlations between infrastructure expansion and housing prices.

---

## Data Sources
| Source | Description |
|---|---|
| [Data Center Map](https://www.datacentermap.com/usa/illinois/chicago/) | A publicly accessible directory of data center facilities in the Chicago metropolitan area, listing sites with basic location and provider information. The database aggregates facility listings from operators and external sources to provide insight into the presence and distribution of data infrastructure in Chicago. |
| [Zillow](https://www.zillow.com/research/data/) | A comprehensive public repository from Zillow that provides historical and current data on U.S. housing markets. The site offers downloadable datasets such as the Zillow Home Value Index (ZHVI), which tracks home prices across regions and over time, making it useful for analyzing housing price trends. |
| [NHGIS](https://www.nhgis.org/) | The National Historical Geographic Information System, maintained by IPUMS, provides free online access to summary statistics and GIS boundary files for U.S. census data across time. Used here to obtain geographic and demographic data at the ZIP code and tract level for the Chicago metro area. |
| [U.S. Census Bureau API](https://www.census.gov/data/developers/data-sets.html) | The official Census Bureau developer API, used to retrieve American Community Survey (ACS) estimates including demographic, economic, and housing characteristics at the ZIP code tabulation area (ZCTA) level. |
| [TIGRIS (R package)](https://github.com/walkerke/tigris) | An R package that provides programmatic access to U.S. Census Bureau TIGER/Line shapefiles, including boundaries for ZIP code tabulation areas, counties, and other geographies. Used to retrieve spatial boundary files for mapping and spatial joins. |
---

## Data Processing & Reconciliation

This project integrates infrastructure, housing, and demographic data from multiple sources. Data center locations were scraped and geocoded for spatial analysis. Housing price data (Zillow) was aggregated from monthly to annual values to align with socioeconomic indicators retrieved via the Census API (ACS 5-year estimates). All datasets were reconciled using geographic identifiers (ZIP codes and Census tracts) to enable spatial and temporal analysis.

See DataProcess.md  for full documentation of the reconciliation and cleaning process.

---

## Data Methodology

To evaluate how data center concentration relates to neighborhood affordability, we construct a composite index at the ZIP code level. The index integrates housing costs, demographic characteristics, and the number of data centers within each ZIP code into a single comparative measure.

We standardize each variable using a decile-based ranking approach, assigning ZIP codes to ten equally sized bins based on empirical quantiles. Lower deciles correspond to lower relative scores, while higher deciles indicate comparatively higher values. These standardized scores are then combined using a weighted average to produce a Composite Index score for each ZIP code.

As an alternative specification, we also implement a z-score normalization approach, which standardizes variables by centering them around the mean and scaling by their standard deviation. This allows comparison across variables with different units of measurement and captures relative deviations rather than rank positions.

Higher Composite Index scores indicate ZIP codes that are comparatively less affordable, while lower scores reflect relatively more affordable areas.

For full technical documentation and mathematical formulation, see DataMethodology.md￼.

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

Navigate to the dashboard directory:
```bash
cd shiny_app
```
Then run:
```bash
cd shiny_app -> shiny run --reload app.py
```

This launches the interactive visualization environment, including:
1. Data center heat map
2. Housing price trends (2000–2025)
3. ZIP-level spatial overlays
4. Composite index scoring

---

## Project Structure

```
project-datacenter-urban-effects/
│
├── data/                                    # Raw and cleaned datasets
│   ├── spatial_data/                        # Geospatial files
│   │   ├── centers/                         # Data center shapefiles
│   │   │   ├── DataCenters.shp
│   │   │   ├── DataCenters.dbf
│   │   │   ├── DataCenters.shx
│   │   │   ├── DataCenters.prj
│   │   │   └── ChicagoDataCentersWithConstruction...
│   │   │
│   │   └── cities/                          # City boundary GeoJSON & shapefiles
│   │       ├── chicago.geojson
│   │       ├── atlanta.geojson
│   │       ├── new_york.geojson
│   │       ├── combined_cities.shp
│   │       ├── combined_cities.dbf
│   │       ├── combined_cities.shx
│   │       ├── combined_cities.prj
│   │       └── cities_with_energy_home_prices.geojson
│   │
│   ├── chicago_data_centers_match (first_permit).csv
│   ├── chicago_data_centers.csv
│   ├── top_us_cities_datacenters.csv
│   ├── zillow_data_zip_code_cook_county.csv
│   └── zillow_yearly_estimates_cook_county.csv
│
├── python_scripts/                          # Data cleaning & processing pipeline
│   ├── chicago_data_centers.py
│   ├── webscrapping_data_centers.py
│   ├── geocoding.py
│   ├── zillow_data.py
│   ├── preparing_data_for_dashboard.py
│   └── aggregate_city_geometries.py
│
├── data_analysis/                           # Index construction & scoring logic
│   ├── DataMethodology.md
│   └── index.py
│
├── shiny_app/                               # Interactive dashboard
│   ├── app.py
│   ├── Data/
│   └── requirements.txt
│
├── milestones/                              # Project documentation
│   ├── milestone1.md
│   └── milestone2.md
│
├── main.py                                  # Composite index prototype
├── pyproject.toml                           # Python dependency management
├── README.md
└── .gitignore
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

**Logan Burton** — [@loganburton](https://github.com/StLaurentMTL) — loganemail@uchicago.edu

**Rodrigo Chaves** — [@rchaves](https://github.com/Rodrigofch7) — rchaves@uchicago.edu

**Sinan Grehan** — [@sinangrehan](https://github.com/sinangrehan) — sinanemaiul@uchicago.edu

**Carlos Eduardo Vargas** — [@cev2030](https://github.com/cev2030) — cev@uchicago.edu

Project Link: [https://github.com/uchicago-2026-capp30122/project-datacenter-urban-effects]
