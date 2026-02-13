from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.express as px
import geopandas as gpd
import os

# -----------------------------
# Load and clean data
# -----------------------------
def load_data():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    cities_path = os.path.join(app_dir, "Data", "cities_clean_imputed.gpkg")
    centers_path = os.path.join(app_dir, "Data", "DataCenters_clean.gpkg")

    cities = gpd.read_file(cities_path)
    centers = gpd.read_file(centers_path)

    # Rename columns to human-friendly names
    cities = cities.rename(columns={
        "city_label":"City",
        "state":"State",
        "utility_name":"Utility",
        "ownership":"Ownership",
        "service_type":"Service Type",
        "avg_price_2021":"Avg Price 2021",
        "avg_price_2022":"Avg Price 2022",
        "avg_price_2023":"Avg Price 2023",
        "avg_price_2024":"Avg Price 2024",
        "comm_rate_2021":"Commercial Rate 2021",
        "comm_rate_2022":"Commercial Rate 2022",
        "comm_rate_2023":"Commercial Rate 2023",
        "comm_rate_2024":"Commercial Rate 2024",
        "ind_rate_2021":"Industrial Rate 2021",
        "ind_rate_2022":"Industrial Rate 2022",
        "ind_rate_2023":"Industrial Rate 2023",
        "ind_rate_2024":"Industrial Rate 2024",
        "pct_change_2021":"% Change 2021",
        "pct_change_2022":"% Change 2022",
        "pct_change_2023":"% Change 2023",
        "pct_change_2024":"% Change 2024",
        "res_rate_2021":"Residential Rate 2021",
        "res_rate_2022":"Residential Rate 2022",
        "res_rate_2023":"Residential Rate 2023",
        "res_rate_2024":"Residential Rate 2024"
    })

    centers = centers.rename(columns={
        "scraped_ci":"Scraped ID",
        "state":"State",
        "facility":"Facility Name",
        "operator":"Operator",
        "street":"Street",
        "zip_code":"ZIP",
        "city_in_de":"City"
    })

    return cities, centers

cities_gdf, centers_gdf = load_data()

numeric_columns = [c for c in cities_gdf.columns if "Rate" in c or "Price" in c or "% Change" in c]

# -----------------------------
# UI
# -----------------------------
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Market Impact",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Filters (Optional)"),
                ui.input_select("metric", "Select Metric to Visualize (Optional)", 
                                choices={c:c for c in numeric_columns},
                                selected=None),
                ui.hr(),
                ui.markdown("**Project:** Urban DC Effects")
            ),
            # Map only (Chicago default)
            ui.layout_columns(
                ui.card(ui.card_header("City Map with DataCenters"), output_widget("map_plot")),
                col_widths=(12,)
            ),
        ),
    ),
    title=ui.h2("Urban Intelligence Dashboard", class_="fw-bold"),
    bg="#1e293b",
    inverse=True,
)

# -----------------------------
# Server
# -----------------------------
def server(input, output, session):
    @reactive.Calc
    def filtered_city():
        # Only Chicago by default
        return cities_gdf[cities_gdf["City"].str.lower() == "chicago"]

    @reactive.Calc
    def filtered_centers():
        return centers_gdf[centers_gdf["City"].str.lower() == "chicago"]

    @render_widget
    def map_plot():
        city_gdf = filtered_city()
        centers_sel = filtered_centers()

        # Default color if no metric selected
        color_metric = input.metric() or None

        fig = px.choropleth_mapbox(
            city_gdf,
            geojson=city_gdf.geometry.__geo_interface__,
            locations=city_gdf.index,
            color=color_metric,
            mapbox_style="carto-darkmatter",
            zoom=10,
            center={"lat": city_gdf.geometry.centroid.y.mean(),
                    "lon": city_gdf.geometry.centroid.x.mean()},
            opacity=0.5,
            hover_name="City",
        )

        if not centers_sel.empty:
            fig.add_scattermapbox(
                lat=centers_sel.geometry.y,
                lon=centers_sel.geometry.x,
                mode="markers",
                marker=dict(size=10,color="red"),
                name="DataCenters",
                hovertext=centers_sel["Facility Name"]
            )

        fig.update_layout(margin=dict(t=0,b=0,l=0,r=0))
        return fig

# -----------------------------
# Run app
# -----------------------------
app = App(app_ui, server)
