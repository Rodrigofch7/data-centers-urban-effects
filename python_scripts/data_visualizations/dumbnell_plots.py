import pandas as pd
import altair as alt

def dumbbell_plot(
    df: pd.DataFrame,
    before_var: str,
    after_var: str,
    change_var: str,
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
        change_var: Column name for the change value for the tooltip.
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
               after_var, change_var]].copy()

    line = plot

    # Reshaping data to long format:
    points = plot.melt(
        id_vars=[dc_code, operator_var, address_var, change_var],
        value_vars=[before_var, after_var],
        var_name="period",
        value_name="value")

    # Relabeling period values for the legend:
    points["period"] = points["period"].map(
        {before_var: before_lab, after_var: after_lab})

    # Sorting data centers by change:
    sort = line.sort_values("change_value", ascending=False)[dc_code].tolist()

    # Connecting lines between before and after:
    lines = (alt.Chart(line).mark_rule(color="lightgray", strokeWidth=2)
        .encode(
            y=alt.Y(f"{dc_code}:N", sort=sort, title="Data Center"),
            x=alt.X("before_value:Q", title=value_lab),
            x2="after_value:Q",
            tooltip=
                [alt.Tooltip(f"{dc_code}:N", title="Data Center"),
                alt.Tooltip(f"{operator_var}:N", title="Operator"),
                alt.Tooltip(f"{address_var}:N", title="Address"),
                alt.Tooltip("before_value:Q", title=before_lab, format=",.2f"),
                alt.Tooltip("after_value:Q", title=after_lab, format=",.2f"),
                alt.Tooltip("change_value:Q", title="Change", format=",.2f")]))

    # Creating endpoints for before and after:
    dots = (alt.Chart(points).mark_point(size=90, filled=True)
        .encode(
            y=alt.Y(f"{dc_code}:N", sort=sort, title="Data Center"),
            x=alt.X("value:Q", title=value_lab),
            color=alt.Color(
                "period:N", title="Period", 
                scale=alt.Scale(domain=[before_lab, after_lab],
                range=["blue", "red"])),
            tooltip=[
                alt.Tooltip(f"{dc_code}:N", title="Data Center"),
                alt.Tooltip(f"{operator_var}:N", title="Operator"),
                alt.Tooltip(f"{address_var}:N", title="Address"),
                alt.Tooltip("period:N", title="Period"),
                alt.Tooltip("value:Q", title=value_lab, format=",.2f"),
                alt.Tooltip(f"{change_var}:Q", title="Change", format=",.2f")]))
    
    chart = ((lines + dots).properties(title=title,
                                         width=800,
                                         height=max(300, len(plot) * 18)))

    return chart