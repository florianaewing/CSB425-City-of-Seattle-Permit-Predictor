# Permit Complexity Report

This brief report summarizes findings in the permit complexity exploration notebook.

Author: Lauren Connelly and Team Red (Margaret Keu, Florian Ewing, John Farnandez)

### Overview

We explored potential factors that may make a permit process complex. Numerical and categorical features were selected from the dataset. For numerical features, a correlation coefficient was calculated for each feature and the target variable, totaldaysplanreview. For categorical features, association was explored rather than correlation. Association was determined by grouping features by category and calculating the mean of the target variable for each category. A higher mean is a greater association, with the caveat that class imbalance can throw off the calculations. 

### Analysis

After removing the features that directly make up the target (e.g. daysinitialplanreview), the features most correlated with the target are housing units added (0.284), housing units (0.285), number of review cycles (0.343), total review cycles (0.345), and number of correction cycles (0.468). Other positive but weaker correlations include estimated project cost (0.136). Permits that require multiple review cycles also have larger values for total days in plan review but we would need to discover the root cause of why those permits require multiple review cycles in the first place.

The categorical features that appear to be most associated with the target are new construction permits (permittype 'new'), housing category ('middle housing'), zone family (SF, NR and LR), review complexity ('full C') and dwelling unit type. Due to the class imbalance in the dwelling unit type feature it is difficult to say which type of dwelling unit is likely to result in permit complexity since there are inverse relationships between the number of data points in each class and the mean of total days in plan review.

### Conclusion and Next Steps

Conclusion:

There are many factors that go into permit complexity. A few that are readily identified are new construction permits, 'middle housing' permits, permits in SF, NR and LR zone families, and potentially permits that have a high estimated project cost. 

Potential Future Areas For Analysis:
- Region: There may be a way to use latitude and longitude data to explore correlation between certain areas of the city and complexity for permits.
- Dwelling unit type: A closer look at the most common dwelling unit types to see if there are associations with permit complexity.