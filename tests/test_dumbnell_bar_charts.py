import pandas as pd
import altair as alt

from data_centers_next_door.data_visualizations.hp_hc_dumbnell_plots import (
    dumbbell_plot,
    housing_price_dumbbell)

from data_centers_next_door.data_visualizations.impact_score_bar_chart import (
    impactscore_barchart)


def main():
    df = pd.read_csv("data/chicago_data_centers_final.csv")

    df2 = pd.read_csv("data/chicago_data_centers_impact_scores.csv")

    # Testing housing price dumbbell plot:

    housing_price_plot = housing_price_dumbbell(df)

    assert isinstance(housing_price_plot, alt.Chart)

    row = df[df["DataCenter_Code"] == "DC01"].iloc[0]

    before_value = row["Housing_Avg_Price_Before_Permit"]

    after_value = row["Housing_Avg_Price_After_Permit"]

    assert pd.notna(before_value)
    assert pd.notna(after_value)

    # Testing housing costs dumbbell plot:

    costs_plot = dumbbell_plot(df)
    assert isinstance(costs_plot, alt.Chart)

    row = df[df["DataCenter_Code"] == "DC01"].iloc[0]

    before_cost = row["HC_Score_Before"]
    after_cost = row["HC_Score_After"]

    assert pd.notna(before_cost)
    assert pd.notna(after_cost)

    # Testing impact score bar chart:

    impact_barchart = impactscore_barchart()
    assert isinstance(impact_barchart, alt.Chart)

    impact_row = df2[df2["DataCenter_Code"] == "DC01"].iloc[0]
    impact_value = impact_row["Impact_Score"]

    assert pd.notna(impact_value)

if __name__ == "__main__":
    main()