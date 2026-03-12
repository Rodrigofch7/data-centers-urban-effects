import pandas as pd
import altair as alt
import webbrowser
from pathlib import Path

# Importing chicago data centers as pandas dataframe
FILEPATH = Path(__file__).parent.parent.parent / "data" / "chicago_data_centers_impact_scores.csv"
OUTPATH = (
    Path(__file__).parent.parent.parent / "data" / "Visualizations" / "data_centers_over_time.html"
)

chicago_data_centers = pd.read_csv(FILEPATH)

#### Preparing data for time series

# Ensuring First Operation Permit is formatted as a date
chicago_data_centers["First_Operation_Permit"] = pd.to_datetime(
    chicago_data_centers["First_Operation_Permit"], format="%Y"
)
# Gathering the cumuluative count of data centers over time
chicago_data_centers_by_year = (
    chicago_data_centers["First_Operation_Permit"]
    .value_counts()
    .sort_index()
    .cumsum()
    .reset_index()
)

#### Creating the time series chart
time_series = (
    alt.Chart(chicago_data_centers_by_year)
    .mark_line()
    .encode(
        x=alt.X("First_Operation_Permit:T", axis=alt.Axis(title="Year")),
        y=alt.Y("count:Q", axis=alt.Axis(title="Total Data Centers")),
    )
    .properties(title="Number of Data Centers in Chicagoland")
)

#### Saving as html file
time_series.save(OUTPATH)
