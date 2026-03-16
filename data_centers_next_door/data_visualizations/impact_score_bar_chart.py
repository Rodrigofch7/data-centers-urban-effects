import pandas as pd
import altair as alt


def impactscore_barchart(path="data/chicago_data_centers_impact_scores.csv") -> alt.Chart:
    """
    This function creates a bar chart of each data center impact score.
    """
    df = pd.read_csv(path)

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("DataCenter_Code:N", sort="-y", title="Data Center Code"),
            y=alt.Y("impact_score:Q", title="Impact Score"),
            tooltip=[
                alt.Tooltip("Operator:N", title="Operator"),
                alt.Tooltip("Address:N", title="Address"),
                alt.Tooltip("impact_score:Q", title="Impact Score", format=",.2f"),
            ],
        )
        .properties(title="Impact Score by Data Center", width=1200, height=800)
    )

    return chart


def main():
    chart = impactscore_barchart()
    chart.save("data/impact_score_bar_chart.html")
    print("Impact score bar chart saved in data folder")


if __name__ == "__main__":
    main()
