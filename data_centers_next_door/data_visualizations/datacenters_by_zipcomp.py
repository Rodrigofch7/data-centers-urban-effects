import pandas as pd
import altair as alt
from pathlib import Path

FILENAME = Path("datacenters_housing_merged.csv")
#Color palette
MAROON      = "#800000"
MAROON_DARK = "#5a0000"
MAROON_MID  = "#a00000"
DARK_BG   = "#0d1117"
PANEL_BG  = "#161b22"
CARD_BG   = "#1c2128"
BORDER    = "#30363d"
TEXT_PRI  = "#e6edf3"
TEXT_SEC  = "#8b949e"
TEXT_ACC  = "#f0a500"

def datacenters_vis_zipcode():
    """
    Builds html file: bar chart of number of data centers by zip code
    """
    datacenters_housing = pd.read_csv(FILENAME,dtype={"Zipcode": str})
    unique_dc_count = (datacenters_housing.groupby('Zipcode')['Address']
                       .nunique()
                       .reset_index(name="Data Center Count")
                        )
    #In mark_bar, the color and outline of the bar is added 
    chart = alt.Chart(unique_dc_count).mark_bar(color=MAROON,stroke=TEXT_ACC, strokeWidth=0.5).encode(
        x = alt.X("Data Center Count:Q",title="Number of Data Centers",axis=alt.Axis(tickMinStep=1)),
        y= alt.Y("Zipcode:N",sort='-x',title="ZIP Code"),
        tooltip=['Data Center Count'],
    ).properties(
    title={
        "text": f"Number of Data Centers in Each Zip Code",
        "color": TEXT_PRI
    },
    background=DARK_BG
    ).configure_axis(
    labelColor=TEXT_SEC,
    titleColor=TEXT_PRI
    ).configure_title(
    font="Helvetica",
    anchor="start"
    ).interactive()
    
    chart.save("datacenters_vis_zipcode.html")

def datacenters_vis_company():
    """
    Builds html file: bar chart of number of data centers by company
    """
    datacenters_housing = pd.read_csv(FILENAME,dtype={"Zipcode": str})
    unique_dc_count = (datacenters_housing.groupby('Operator')['Address']
                       .nunique()
                       .reset_index(name="Data Center Count")
                        )
    chart = alt.Chart(unique_dc_count).mark_bar(color=MAROON,stroke=TEXT_ACC, strokeWidth=0.5).encode(
        x = alt.X("Data Center Count:Q",title="Number of Data Centers",axis=alt.Axis(tickMinStep=1)),
        y= alt.Y("Operator:N",sort='-x',title="Company Name"),
        tooltip=['Data Center Count'],
    ).properties(
    title={
        "text": f"Number of Data Centers by Each Company",
        "color": TEXT_PRI
    },
    background=DARK_BG
    ).configure_axis(
    labelColor=TEXT_SEC,
    titleColor=TEXT_PRI
    ).configure_title(
    fontSize=18,
    font="Helvetica",
    anchor="start"
    ).interactive()
    
    chart.save("datacenters_vis_company.html")

if __name__ == "__main__":
    datacenters_vis_zipcode()
    datacenters_vis_company()