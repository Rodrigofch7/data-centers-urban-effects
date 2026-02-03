from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget
import plotly.express as px
import pandas as pd

# -----------------------------
# Placeholder data
# -----------------------------

def make_placeholder_data():
    return pd.DataFrame({
        "city": ["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"],
        "num_datacenters": [25, 18, 30, 15, 20],
        "avg_power_mw": [40, 35, 50, 45, 38],
        "avg_latency_ms": [12, 15, 10, 14, 13],
        "latitude": [40.71, 41.88, 32.78, 37.77, 33.75],
        "longitude": [-74.00, -87.63, -96.80, -122.42, -84.39],
    })

# -----------------------------
# UI
# -----------------------------

app_ui = ui.page_navbar(
    ui.nav_panel(
        "Overview",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Controls"),
                ui.p("Interactive prototype using placeholder data"),
                ui.input_select(
                    "metric",
                    "Metric",
                    {
                        "num_datacenters": "Number of Data Centers",
                        "avg_power_mw": "Average Power (MW)",
                        "avg_latency_ms": "Average Latency (ms)",
                    },
                ),
                ui.input_checkbox_group(
                    "cities",
                    "Cities",
                    ["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"],
                    selected=["New York", "Chicago", "Dallas", "San Francisco", "Atlanta"],
                ),
                ui.hr(),
                ui.input_switch("normalize", "Normalize values", False),
            ),
            ui.layout_columns(
                ui.value_box(
                    "Total Data Centers",
                    ui.output_text("kpi_total"),
                    showcase="📦",
                ),
                ui.value_box(
                    "Avg Power (MW)",
                    ui.output_text("kpi_power"),
                    showcase="⚡",
                ),
                ui.value_box(
                    "Avg Latency (ms)",
                    ui.output_text("kpi_latency"),
                    showcase="⏱️",
                ),
                col_widths=(4, 4, 4),
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("City Comparison"),
                    output_widget("bar_plot"),
                ),
                ui.card(
                    ui.card_header("Geographic Distribution"),
                    output_widget("map_plot"),
                ),
                col_widths=(6, 6),
            ),
        ),
    ),
    ui.nav_panel(
        "Table",
        ui.layout_columns(
            ui.card(
                ui.card_header("Summary Table"),
                ui.output_data_frame("summary_table"),
            ),
        ),
    ),
    ui.nav_panel(
        "About",
        ui.card(
            ui.h4("Project context"),
            ui.p(
                "This dashboard is a prototype for analyzing the urban impacts of data centers "
                "across major US cities. Future versions will integrate scraped facility-level data, "
                "energy usage, water consumption, and policy-relevant outcomes."
            ),
        ),
    ),
    title=ui.h2("US Data Center Landscape", class_="fw-bold"),
    bg="#0f172a",
    inverse=True,
)

# -----------------------------
# Server
# -----------------------------

def server(input, output, session):
    data = reactive.Value(make_placeholder_data())

    @reactive.Calc
    def filtered_data():
        df = data().copy()
        df = df[df["city"].isin(input.cities())]
        if input.normalize():
            cols = ["num_datacenters", "avg_power_mw", "avg_latency_ms"]
            # Basic Z-score normalization
            df[cols] = (df[cols] - df[cols].mean()) / df[cols].std()
        return df

    # ---------------- KPIs ----------------

    @render.text
    def kpi_total():
        val = filtered_data()["num_datacenters"].sum()
        return f"{int(val)}"

    @render.text
    def kpi_power():
        val = filtered_data()["avg_power_mw"].mean()
        return f"{round(val, 1)} MW"

    @render.text
    def kpi_latency():
        val = filtered_data()["avg_latency_ms"].mean()
        return f"{round(val, 1)} ms"

    # ---------------- Plots ----------------

    @render_widget
    def bar_plot():
        df = filtered_data()
        fig = px.bar(
            df,
            x="city",
            y=input.metric(),
            color="city",
            title=f"Comparison: {input.metric().replace('_', ' ').title()}",
        )
        fig.update_layout(showlegend=False, height=400, margin=dict(t=40, b=0, l=0, r=0))
        return fig

    @render_widget
    def map_plot():
        df = filtered_data()
        fig = px.scatter_mapbox(
            df,
            lat="latitude",
            lon="longitude",
            size="num_datacenters",
            color="avg_power_mw",
            hover_name="city",
            zoom=3,
        )
        fig.update_layout(
            mapbox_style="carto-positron", 
            height=400, 
            margin=dict(t=0, b=0, l=0, r=0)
        )
        return fig

    # ---------------- Table ----------------

    @render.data_frame
    def summary_table():
        return render.DataTable(filtered_data())

# -----------------------------
# App
# -----------------------------

app = App(app_ui, server)