from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.express as px
import pandas as pd
import geopandas as gpd
import os

# -----------------------------
# Data Loading & Cleaning
# -----------------------------
def load_data():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    cities_path = os.path.join(app_dir, "Data", "cities_clean_imputed.gpkg")
    centers_path = os.path.join(app_dir, "Data", "DataCenters_clean.gpkg")

    # Load GeoPackages
    cities = gpd.read_file(cities_path)
    centers = gpd.read_file(centers_path)

    # Rename columns to friendly names
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
        "city_in_de":"City",
        "latitude":"Latitude",
        "longitude":"Longitude"
    })

    return cities, centers

cities_gdf, centers_gdf = load_data()
available_cities = sorted(cities_gdf["City"].unique().tolist())

# Numeric columns for selection
numeric_columns = [c for c in cities_gdf.columns if "Rate" in c or "Price" in c or "% Change" in c]

# -----------------------------
# UI
# -----------------------------
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Market Impact",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Filters"),
                ui.input_select("city","Select City",choices=available_cities,selected="chicago"),
                ui.input_select("metric","Select Metric",choices={c:c for c in numeric_columns},selected="Residential Rate 2023"),
                ui.hr(),
                ui.markdown("**Project:** Urban DC Effects")
            ),
            ui.layout_columns(
                ui.value_box("Average Metric",ui.output_text("kpi_metric"),showcase="📊",theme="primary"),
                ui.value_box("City Selected",ui.output_text("kpi_city_name"),showcase="📍"),
                col_widths=(6,6)
            ),
            ui.layout_columns(
                ui.card(ui.card_header("City Metrics"), output_widget("scatter_plot")),
                ui.card(ui.card_header("City Map with DataCenters"), output_widget("map_plot")),
                col_widths=(6,6)
            ),
        ),
    ),
    ui.nav_panel("Detailed Data", ui.card(ui.output_data_frame("summary_table"))),
    title=ui.h2("Urban Intelligence Dashboard", class_="fw-bold"),
    bg="#1e293b",
    inverse=True,
)

# -----------------------------
# SERVER
# -----------------------------
def server(input, output, session):
    @reactive.Calc
    def filtered_city():
        return cities_gdf[cities_gdf["City"].str.lower() == input.city().lower()]

    @reactive.Calc
    def filtered_centers():
        return centers_gdf[centers_gdf["City"].str.lower() == input.city().lower()]

    @render.text
    def kpi_metric():
        df = filtered_city()
        val = df[input.metric()].mean()
        return f"{val:.4f}"

    @render.text
    def kpi_city_name():
        return input.city().title()

    @render_widget
    def scatter_plot():
        df = filtered_city()
        fig = px.scatter(df,y=input.metric(),hover_data=["City"],template="plotly_white")
        fig.update_layout(margin=dict(t=30,b=0,l=0,r=0))
        return fig

    @render_widget
    def map_plot():
        city_gdf = filtered_city()
        centers_sel = filtered_centers()

        # City polygons
        fig = px.choropleth_mapbox(
            city_gdf,
            geojson=city_gdf.geometry.__geo_interface__,
            locations=city_gdf.index,
            color=input.metric(),
            mapbox_style="carto-darkmatter",
            zoom=10,
            center={"lat": city_gdf.geometry.centroid.y.mean(),
                    "lon": city_gdf.geometry.centroid.x.mean()},
            opacity=0.5,
            hover_name="City",
        )

        # DataCenters overlay
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

    @render.data_frame
    def summary_table():
        return filtered_city()

# -----------------------------
# RUN APP
# -----------------------------
app = App(app_ui, server)
