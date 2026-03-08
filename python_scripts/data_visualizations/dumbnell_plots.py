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

    # Segmenting data for the connecting lines:
    line = plot.rename(columns={
            before_var: "before_value",
            after_var: "after_value",
            change_var: "change_value"})

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

