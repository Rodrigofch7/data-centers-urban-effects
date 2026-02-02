[All details presented in this document are preliminary and may be refined or modified throughout the duration of the project.]

# Data Centers Next Door: How Cloud Infrastructure Shapes Housing and Local Resource Costs.

## Abstract

Data Centers Next Door examines how the expansion of cloud infrastructure affects housing markets and local resource costs in urban communities. As consumers and businesses become increasingly reliant on digital services such as cloud computing and artificial intelligence, data centers are being built at a rapid pace, often near or within metropolitan areas. While proponents argue that data centers drive economic growth and technological innovation, many communities have raised concerns about rising energy demand and housing affordability associated with their presence.

This project aims to analyze the local impacts of data centers on housing prices and electricity demand, **with a focus on the 10 largest U.S. cities rather than a single metropolitan area**. This shift allows us to leverage a larger and more consistent set of ZIP codes, as data center locations are identified at the ZIP code level while housing prices are reported at the neighborhood level. We aggregate neighborhood-level housing data to the ZIP code level to align these sources and increase analytical coverage.

Using multiple real-world datasets, we combine information on data center locations with demographic, housing, and infrastructure data to explore correlations between data center development and changes in local conditions. **Due to the lack of a reliable and consistent data source, water-related costs are excluded from the analysis**. The project will culminate in a small, interactive, data-driven index that allows users to explore how cloud infrastructure may shape housing affordability and resource pressures across neighborhoods and cities.

## Data Sources

### Data Source #1
https://www.datacentermap.com/usa/illinois/chicago/
Source Type: Scraped
Approximate Number of Records (rows): 862
Approximate Number of Attributes (columns): 6 
Current Status: Successfully scraped
Challenges: Some addresses are abbreviated (e.g., “St” instead of “Street”), requiring minor standardization. Otherwise, data quality is high.

### Data Source #2
https://data.census.gov/table/ACSDP5Y2022.DP05?g=010XX00US$1400000
Source Type: Bulk Data
Approximate Number of Records (rows): 853k
Approximate Number of Attributes (columns): 435
Current Status: The data looks solid and ready to be used
Challenges: ACS data is observational and aggregated, which limits causal inference. Geographic resolution may require careful alignment with data center locations, and time coverage is based on multi-year estimates rather than single-year observations.

### Data Source #3
https://catalog.data.gov/dataset/u-s-electric-utility-companies-and-rates-look-up-by-zip-code-2024
Source Type: Bulk Data
Approximate Number of Records (rows): 49k
Approximate Number of Attributes (columns): 9
Current Status: The data looks solid and ready to be used
Challenges: Although the data is granular at the zip code level, there will be some deduplication required (e.g. many rows are identical). While this is technically simple to address, it will make it so that the average price of electricity (presented in cents/kwh) is aggregated. This would make it so that our index may be generalized. 

### Data Source #4
https://www.zillow.com/research/data/
Source Type: Bulk Data
Approximate Number of Records (rows): 26k
Approximate Number of Attributes (columns): 321
Current Status: The data looks solid and ready to be used
Challenges: Some variables may be missing for certain regions or time periods, necessitating imputation or filtering. 

## Data Reconciliation Plan

We will collect data from multiple sources covering:
    Data center locations (via web scraping)
    Housing prices (bulk datasets)
    Electricity prices (bulk datasets)

(Water prices were initially considered but will be excluded due to limited and inconsistent data availability.)

All datasets will be merged using ZIP code as the primary geographic key. ZIP codes are present either directly or indirectly in all sources and provide the most consistent unit of alignment across datasets.

Reconciling the data will require:
    Extracting and standardizing ZIP codes from scraped data center addresses
    Aggregating housing price and electricity cost data to the ZIP code level
    Handling duplicate entries and minor inconsistencies across sources

ZIP codes offer the best available common geographic unit across all datasets and allow us to combine infrastructure, housing, and cost data in a consistent way.

## Project Plan

We will structure the project around the following components:
    1. Web scraping data center locations: Collect and clean data center address and ZIP code information from DataCenterMap.
    2. Preparing and merging bulk datasets: Process housing price and electricity price datasets and aggregate them to the ZIP code level.
    3. Data reconciliation and index construction: Combine data center counts, housing prices, and electricity prices by ZIP code and construct an index that approximates relative cost pressures associated with data center concentration. This index is exploratory and not intended to imply causality.
    4. Visualization of results: Create a map-based visualization (initially a heat map) to highlight spatial patterns across ZIP codes. The exact visualization may evolve based on results.

The project is divided into three overlapping work streams:
    Scraping: Rodrigo and Sinan
    Analysis: Logan and Carlos
    Visualization: Sinan and Carlos

To reduce bottlenecks, analysis and visualization will begin using partial or mock data if scraping is not fully complete. This overlap allows insights from analysis to inform visualization early, and issues discovered during scraping to be addressed before final integration.

Weeks 5–6:
Complete web scraping and initial cleaning of data center locations. Prepare housing price and electricity price datasets at the ZIP code level.

Week 7 (Prototype):
A working merged dataset by ZIP code, a preliminary version of the index, and an initial visualization showing spatial patterns.

Weeks 8–9:
Refine the index, validate assumptions, improve data quality, and iterate on visualization design.

## Questions

1. Is ZIP code an appropriate unit for merging these datasets, given that housing prices, data center locations, and electricity data are reported at different geographic levels?

2. When datasets don’t align perfectly (for example, neighborhoods vs. ZIP codes), what level of aggregation or approximation is acceptable for this type of exploratory project?

3. Given limitations in publicly available data, which variables are reasonable to include in our analysis, and which should be excluded even if they are conceptually important (e.g., water usage)?

4. How should we think about constructing an index that combines multiple measures (data center counts, housing prices, electricity costs) without implying causal relationships?

5. What level of interpretation and visualization is appropriate for a project that is primarily descriptive and exploratory rather than causal?
