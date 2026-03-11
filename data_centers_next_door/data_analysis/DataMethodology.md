# Data Methodology

NOTE: METHODOLOGY IS IN PROGRESS AND IS NOT FINAL

We implement a composite index based housing costs, demographic characteristics, and the number of data centers within a zip code to act as easy representation of how data centers, in combination with other crucical elements, affect the affordability of neighborhoods. 

The calculation of the index begins with the assignment of a standardized score based on a decile-based rankings using empirical quantiles. Each zip code is assigne to one of ten equally sized bins, with lower deciles corresponding lower scores and higher deciles corresponding to higher scores. 

Following the assignment of scores, we take a weighted average of the scores as such:

$$
CI_i = \sum_{j=1}^{J} w_j S_{ij},  
\quad \text{where } \sum_{j=1}^{J} w_j = 1
$$

Where $w_{j}$ represents the percentage weighting of the $j$th variable and $S_{ij}$ representing $i$th zip code's score for the respective $j$ variable. Higher index scores represent zip codes that are comparatively less affordable and lower index scores indicating relatively more affordable zip codes. 

As an alternative specification, we have also included as an option to implement a z-scores approach in lieu to the decile ranking methodology that makes comparison between variables with different units of measure more standardized, where $S_{ij}$ is calculated as:

$$S_{ij} = \frac{x_{ij} - \bar{x_{j}}}{\sigma_{j}}$$

where $x_{ij}​$ is the raw value for zip code $i$, $\bar{x_j}​$ is the mean across zip codes for variable $j$, and $\sigma_{j}$​ is the corresponding standard deviation. This transformation centers each variable at zero allowing the index to capture relative deviations from the average rather than through rankings.
