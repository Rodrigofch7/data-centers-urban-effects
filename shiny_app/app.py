from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.express as px
import pandas as pd
import numpy as np

# -----------------------------
# Enhanced Mock Data
# -----------------------------
def make_placeholder_data():
    # Simulating zip-level data within cities
    cities = ["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"]
    data = []
    for city in cities:
        for i in range(5):  # 5 zip codes per city
            data.append({
                "zip_code": f"{city[:3].upper()}-{100 + i}",
                "city": city,
                "num_datacenters": np.random.randint(1, 10),
                "avg_power_mw": np.random.uniform(10, 60),
                "home_price_index": np.random.uniform(300000, 900000),
                "energy_kwh_sqft": np.random.uniform(1.2, 4.5),
                "latitude": [40.71, 41.88, 32.78, 37.77, 33.75][cities.index(city)] + np.random.uniform(-0.1, 0.1),
                "longitude": [-74.00, -87.63, -96.80, -122.42, -84.39][cities.index(city)] + np.random.uniform(-0.1, 0.1),
            })
    return pd.DataFrame(data)

# -----------------------------
# UI
# -----------------------------
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Market Impact",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Filters"),
                ui.input_select(
                    "y_axis",
                    "Impact Metric (Y-Axis)",
                    {
                        "home_price_index": "Home Price Index",
                        "energy_kwh_sqft": "Energy Intensity (kWh/sqft)",
                        "avg_power_mw": "Data Center Load (MW)"
                    },
                ),
                ui.input_checkbox_group(
                    "cities",
                    "Filter Cities",
                    ["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"],
                    selected=["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"],
                ),
                ui.hr(),
                ui.input_slider("price_range", "Home Price Range", 300000, 1000000, [300000, 1000000]),
            ),
            # KPI Row
            ui.layout_columns(
                ui.value_box(
                    "Avg Home Price",
                    ui.output_text("kpi_price"),
                    showcase="🏠",
                    theme="primary"
                ),
                ui.value_box(
                    "Energy Intensity",
                    ui.output_text("kpi_energy"),
                    showcase="🔌",
                    theme="success"
                ),
                ui.value_box(
                    "DC Saturation",
                    ui.output_text("kpi_dc_count"),
                    showcase="📊",
                ),
                col_widths=(4, 4, 4),
            ),
            # Main Charts
            ui.layout_columns(
                ui.card(
                    ui.card_header("Real Estate vs. Energy Correlation"),
                    output_widget("correlation_plot"),
                ),
                ui.card(
                    ui.card_header("Zip-Level Geospatial Heatmap"),
                    output_widget("map_plot"),
                ),
                col_widths=(6, 6),
            ),
        ),
    ),
    ui.nav_panel(
        "Detailed Data",
        ui.card(ui.output_data_frame("summary_table"))
    ),
    title=ui.h2("Urban DC Intelligence", class_="fw-bold"),
    bg="#1e293b",
    inverse=True,
)

# -----------------------------
# Server
# -----------------------------
def server(input, output, session):
    full_data = reactive.Value(make_placeholder_data())

    @reactive.Calc
    def filtered_df():
        df = full_data()
        idx = (df["city"].isin(input.cities())) & \
              (df["home_price_index"] >= input.price_range()[0]) & \
              (df["home_price_index"] <= input.price_range()[1])
        return df[idx]

    # --- KPIs ---
    @render.text
    def kpi_price():
        val = filtered_df()["home_price_index"].mean()
        return f"${val:,.0f}"

    @render.text
    def kpi_energy():
        val = filtered_df()["energy_kwh_sqft"].mean()
        return f"{val:.2f} kWh/sf"

    @render.text
    def kpi_dc_count():
        return str(filtered_df()["num_datacenters"].sum())

    # --- Visuals ---
    @render_widget
    def correlation_plot():
        df = filtered_df()
        fig = px.scatter(
            df, 
            x="num_datacenters", 
            y=input.y_axis(),
            color="city",
            size="avg_power_mw",
            hover_data=["zip_code"],
            trendline="ols",
            template="plotly_white"
        )
        fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
        return fig

    @render_widget
    def map_plot():
        df = filtered_df()
        fig = px.scatter_mapbox(
            df,
            lat="latitude",
            lon="longitude",
            size="avg_power_mw",
            color="home_price_index",
            color_continuous_scale=px.colors.sequential.Viridis,
            hover_name="zip_code",
            zoom=3,
            mapbox_style="carto-darkmatter"
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        return fig

    @render.data_frame
    def summary_table():
        return render.DataTable(filtered_df())

app = App(app_ui, server)