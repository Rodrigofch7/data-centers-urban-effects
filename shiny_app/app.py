from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.express as px
import pandas as pd
import geopandas as gpd
import os
import numpy as np

# -----------------------------
# Real Data Loading
# -----------------------------
def load_actual_data():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(app_dir, "Data", "cities_with_energy_home_prices.geojson")
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Check path: {data_path}")
        
    gdf = gpd.read_file(data_path)
    
    # Calculate centroids
    gdf["latitude"] = gdf.geometry.centroid.y
    gdf["longitude"] = gdf.geometry.centroid.x
    
    # Convert to DataFrame and drop geometry
    df = pd.DataFrame(gdf.drop(columns='geometry'))

    # FIX: Replace NaNs with 0 for numeric columns to prevent JSON errors
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)
    
    # Replace NaNs in string columns with "N/A"
    object_cols = df.select_dtypes(include=[object]).columns
    df[object_cols] = df[object_cols].fillna("N/A")

    return df

# Load the data once at startup
df_init = load_actual_data()
# Get unique city names from your shapefile for the filter
available_cities = sorted(df_init["city_label"].unique().tolist())

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
                    "Energy/Price Metric (Y-Axis)",
                    {
                        "res_rate_2023": "Res. Energy Rate (2023)",
                        "comm_rate_2023": "Comm. Energy Rate (2023)",
                        "ind_rate_2023": "Ind. Energy Rate (2023)",
                        "avg_price_2023": "Avg Energy Price (2023)",
                        "home_price_index": "Home Price Index"
                    },
                ),
                ui.input_checkbox_group(
                    "cities",
                    "Filter Cities",
                    choices=available_cities,
                    selected=available_cities[:10], # Default to first 10
                ),
                ui.hr(),
                ui.markdown("---"),
                ui.markdown("**Project:** Urban DC Effects")
            ),
            # KPI Row
            ui.layout_columns(
                ui.value_box(
                    "Avg Res Rate",
                    ui.output_text("kpi_res_rate"),
                    showcase="🏠",
                    theme="primary"
                ),
                ui.value_box(
                    "Avg Energy Price",
                    ui.output_text("kpi_avg_price"),
                    showcase="🔌",
                    theme="success"
                ),
                ui.value_box(
                    "Regions Selected",
                    ui.output_text("kpi_city_count"),
                    showcase="📍",
                ),
                col_widths=(4, 4, 4),
            ),
            # Main Charts
            ui.layout_columns(
                ui.card(
                    ui.card_header("Rate vs. Metric Correlation"),
                    output_widget("correlation_plot"),
                ),
                ui.card(
                    ui.card_header("Geospatial Energy Distribution"),
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
    title=ui.h2("Urban Intelligence Dashboard", class_="fw-bold"),
    bg="#1e293b",
    inverse=True,
)

# -----------------------------
# Server
# -----------------------------
def server(input, output, session):
    full_data = reactive.Value(df_init)

    @reactive.Calc
    def filtered_df():
        df = full_data()
        # Filter based on user city selection
        return df[df["NAME20"].isin(input.cities())]

    # --- KPIs ---
    @render.text
    def kpi_res_rate():
        val = filtered_df()["res_rate_2023"].mean()
        return f"${val:.4f} /kWh"

    @render.text
    def kpi_avg_price():
        val = filtered_df()["avg_price_2023"].mean()
        return f"${val:.4f} /kWh"

    @render.text
    def kpi_city_count():
        return str(len(filtered_df()))

    # --- Visuals ---
    @render_widget
    def correlation_plot():
        df = filtered_df()
        # Defaulting x-axis to a fixed metric, y-axis to user input
        fig = px.scatter(
            df, 
            x="res_rate_2023", 
            y=input.y_axis(),
            color="NAME20",
            hover_data=["utility_name", "state"] if "utility_name" in df.columns else ["NAME20"],
            template="plotly_white",
            labels={"res_rate_2023": "Res Rate ($/kWh)", "NAME20": "City"}
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
            color=input.y_axis(),
            size_max=15,
            hover_name="NAME20",
            zoom=3,
            mapbox_style="carto-darkmatter"
        )
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        return fig

    @render.data_frame
    def summary_table():
        return render.DataTable(filtered_df())

app = App(app_ui, server)