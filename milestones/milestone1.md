\# **Data Centers Next Door:** *How Cloud Infrastructure Shapes Housing and Local Resource Costs.*

**\#\# Members**

\- Logan Burton lburton12@uchicago.edu  
\- Carlos Eduardo Vargas cev@uchicago.edu  
\- Sinan Grehan sinangrehan@uchicago.edu  
\- Rodrigo Chaves rchaves@uchicago.edu

**\#\# Abstract**

**Data Centers Next Door** examines how the expansion of cloud infrastructure affects housing markets and local resource costs in urban communities. As consumers and businesses become increasingly reliant on digital services such as cloud computing and artificial intelligence, data centers are being built at a rapid pace, often near or within metropolitan areas. While proponents argue that data centers drive economic growth and technological innovation, many communities have raised concerns about rising energy demand, water usage, and housing affordability associated with their presence.

This project aims to analyze the local impacts of data centers on housing prices, electricity demand, and water-related costs, with an initial focus on the Chicago region. Using multiple real-world datasets, we will combine information on data center locations with demographic, housing, and infrastructure data to explore correlations between data center development and changes in local conditions. The project will culminate in a small, interactive, data-driven index that allows users to explore how cloud infrastructure may shape housing affordability and resource pressures across neighborhoods.

**\#\# Data Sources**

\#\#\# Data Source \#1  
[https://www.datacentermap.com/usa/illinois/chicago/](https://www.datacentermap.com/usa/illinois/chicago/)  
Source Type: Scraped / Bulk Data  
Summary: This dataset provides information on data center facilities in the Chicago region, including approximate locations, operators, and facility characteristics. It is published and maintained by DataCenterMap, a widely used industry directory for data center infrastructure.

Challenges: The dataset may not include historical opening dates or exact capacity measures for all facilities, and coverage may vary by provider. Scraping or manual cleaning may be required to standardize locations and match facilities to geographic units such as neighborhoods or census tracts.

\#\#\# Data Source \#2  
[https://data.census.gov/table/ACSDP5Y2022.DP05?g=010XX00US$1400000](https://data.census.gov/table/ACSDP5Y2022.DP05?g=010XX00US$1400000)  
Source Type: API / Bulk Data  
Summary: This dataset is published by the U.S. Census Bureau as part of the American Community Survey (ACS). It provides demographic and housing-related variables, including population characteristics, housing occupancy, and selected economic indicators at multiple geographic levels.  
Challenges: ACS data is observational and aggregated, which limits causal inference. Geographic resolution may require careful alignment with data center locations, and time coverage is based on multi-year estimates rather than single-year observations.

**\#\# Questions**

1. How does the presence or expansion of data centers correlate with changes in housing prices or housing affordability in nearby urban areas?

2. What relationship exists between data center development and local electricity demand or electricity-related costs at the city or county level?

3. How does increased data center activity relate to water usage or water system demand in affected communities?

4. Do these impacts vary across neighborhoods within the Chicago region or over time?

5. Can these outcomes be combined into a data-driven index that helps identify which communities experience the greatest local costs associated with data center development?