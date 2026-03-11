# Data Methodology

We implement a composite index based the changes in housing prices and household costs (e.g. electricity and ultility costs) pre- and post-data center's first permitting. The allows us to see the relative impact of the data center on the neighborhood for a specfic timeframe.  

The calculation of the index begins with the assignment of a standardized score based on decile-based rankings using empirical quantiles. Each data center is assigned to one of ten equally sized bins, with lower deciles corresponding lower scores and higher deciles corresponding to higher scores. 

Following the assignment of scores, we take a weighted average of the scores as such:

$$
CI_i = \sum_{j=1}^{J} w_j S_{ij},  
\quad \text{where } \sum_{j=1}^{J} w_j = 1
$$

Where $w_{j}$ represents the percentage weighting of the $j$th variable and $S_{ij}$ representing $i$th data center's score for the respective $j$ variable. A higher index score suggests that the data center had more of a costly impact on housing prices and household expenses (and vice versa for a lower index score).  

As an alternative specification, we have also included as an option to implement a z-scores approach in lieu to the decile ranking methodology that makes comparison between variables with different units of measure more standardized, where $S_{ij}$ is calculated as:

$$S_{ij} = \frac{x_{ij} - \bar{x_{j}}}{\sigma_{j}}$$

where $x_{ij}​$ is the raw value of the variable $j$ for data center $i$, $\bar{x_j}​$ is the mean across data centers for variable $j$, and $\sigma_{j}$​ is the corresponding standard deviation. This transformation centers each variable at zero allowing the index to capture relative deviations from the average rather than through rankings.

Please note that the implementation of these indices are not causal in nature, but rather aim to capture assocations between data centers and housing costs/prices in an easier to digest manner. For a more causal analysis, we suggest a Differences-in-Differences regression model.  
