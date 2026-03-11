import pandas as pd
import altair as alt

def dumbbell_plot(
    df: pd.DataFrame,
    before_var: str,
    after_var: str,
    value_lab: str,
    title: str,
    before_lab: str = "Before Permit",
    after_lab: str = "After Permit",
    dc_code: str = "DataCenter_Code",
    operator_var: str = "Operator",
    address_var: str = "Address",
) -> alt.Chart:
    """
    This function creates a dumbbell plot comparing before vs after values
    for each data center.

    Inputs:
        df: DataFrame containing the required columns.
        before_var: Column name for the "before" value.
        after_var: Column name for the "after" value.
        value_lab: Readable label for the metric.
        title: Chart title.
        before_lab: Label for the before period in legend.
        after_lab: Label for the after period in legend.
        dc_code: Column name for the data center code.
        operator_var: Column name for the data center operator name.
        address_var: Column name for the data center address.

    Returns:
        The dumbbell plot.
    """
    plot = df[[dc_code, operator_var, address_var, before_var, 
               after_var]].copy()

    # Reshaping data to long format:
    points = plot.melt(
        id_vars=[dc_code, operator_var, address_var],
        value_vars=[before_var, after_var],
        var_name="period",
        value_name="value")

    # Relabeling period values for the legend:
    points["period"] = points["period"].map(
        {before_var: before_lab, after_var: after_lab})

    # Connecting lines between before and after:
    lines = (
        alt.Chart(plot)
        .mark_rule(color="gray", strokeWidth=3)
        .encode(
            y=alt.Y(f"{dc_code}:N", title="Data Center"),
            x=alt.X(f"{before_var}:Q", title=value_lab, scale=alt.Scale(zero=False)),
            x2=f"{after_var}:Q",
            tooltip=[
                alt.Tooltip(f"{dc_code}:N", title="Data Center"),
                alt.Tooltip(f"{operator_var}:N", title="Operator"),
                alt.Tooltip(f"{address_var}:N", title="Address"),
                alt.Tooltip(f"{before_var}:Q", title=before_lab, format=",.2f"),
                alt.Tooltip(f"{after_var}:Q", title=after_lab, format=",.2f")]))

    # Creating endpoints for before and after:
    dots = (alt.Chart(points).mark_point(size=70, filled=True)
        .encode(
            y=alt.Y(f"{dc_code}:N", title="Data Center"),
            x=alt.X("value:Q", title=value_lab, scale=alt.Scale(zero=False)),
            color=alt.Color(
                "period:N", title="Period", 
                scale=alt.Scale(domain=[before_lab, after_lab],
                range=["blue", "red"])),
            tooltip=[
                alt.Tooltip(f"{dc_code}:N", title="Data Center"),
                alt.Tooltip(f"{operator_var}:N", title="Operator"),
                alt.Tooltip(f"{address_var}:N", title="Address"),
                alt.Tooltip("period:N", title="Period"),
                alt.Tooltip("value:Q", title=value_lab, format=",.2f")]))
    
    chart = ((lines + dots).properties(title=title,
                                         width=1200,
                                         height=min(800, 
                                                    max(300, len(plot) * 25))))

    return chart

def housing_price_dumbbell(df: pd.DataFrame) -> alt.Chart:
    """
    This function creates a dumbbell plot for housing prices 
    before and after each data center permit year.
    """
    return dumbbell_plot(
        df=df,
        before_var="Housing_Avg_Price_Before_Permit",
        after_var="Housing_Avg_Price_After_Permit",
        value_lab="Average Housing Price",
        title="Housing Prices Before and After Data Center Permit",
        before_lab="Before Permit",
        after_lab="After Permit")


def housing_costs_dumbbell(df: pd.DataFrame) -> alt.Chart:
    """
    This function creates a dumbbell plot for housing cost scores
    before and after permit year.
    """
    return dumbbell_plot(
        df=df,
        before_var="HC_Score_Before",
        after_var="HC_Score_After",
        value_lab="Housing Cost Score",
        title="Housing Cost Scores Before and After Data Center Permit",
        before_lab="Before Permit",
        after_lab="After Permit")

def main():
    """
    Loading the final dataset and generating the dumbbell charts.
    The charts are saved to the data folder.
    """

    # Loading dataset:
    df = pd.read_csv("data/chicago_data_centers_final.csv")

    # Creating charts:
    housing_price_chart = housing_price_dumbbell(df)
    housing_cost_chart = housing_costs_dumbbell(df)

    # Saving them:
    housing_price_chart.save("data/Visualizations/housing_price_dumbbell.html")
    housing_cost_chart.save("data/Visualizations/housing_cost_dumbbell.html")

    print("Dumbnell plots saved in data folder.")

if __name__ == "__main__":
    main()