from shiny import App, ui, render, reactive
import folium
import branca.colormap as cm
import geopandas as gpd
import pandas as pd
import numpy as np
import os

# -----------------------------
# Load and clean data
# -----------------------------
def load_data():
    app_dir = os.path.dirname(os.path.abspath(__file__))

    cities_path = os.path.join(app_dir, "shiny_app/Data", "cities_clean_imputed.gpkg")
    centers_path = os.path.join(app_dir, "shiny_app/Data", "DataCenters_clean.gpkg")

    cities = gpd.read_file(cities_path)
    centers = gpd.read_file(centers_path)

    cities = cities.rename(
        columns={
            "city_label": "City",
            "avg_price_2021": "Avg Price 2021",
            "avg_price_2022": "Avg Price 2022",
            "avg_price_2023": "Avg Price 2023",
            "avg_price_2024": "Avg Price 2024",
            "comm_rate_2021": "Commercial Rate 2021",
            "comm_rate_2022": "Commercial Rate 2022",
            "comm_rate_2023": "Commercial Rate 2023",
            "comm_rate_2024": "Commercial Rate 2024",
            "ind_rate_2021": "Industrial Rate 2021",
            "ind_rate_2022": "Industrial Rate 2022",
            "ind_rate_2023": "Industrial Rate 2023",
            "ind_rate_2024": "Industrial Rate 2024",
            "pct_change_2021": "% Change 2021",
            "pct_change_2022": "% Change 2022",
            "pct_change_2023": "% Change 2023",
            "pct_change_2024": "% Change 2024",
            "res_rate_2021": "Residential Rate 2021",
            "res_rate_2022": "Residential Rate 2022",
            "res_rate_2023": "Residential Rate 2023",
            "res_rate_2024": "Residential Rate 2024",
        }
    )

    centers = centers.rename(
        columns={
            "scraped_ci": "Scraped ID",
            "state": "State",
            "facility": "Facility Name",
            "operator": "Operator",
            "street": "Street",
            "zip_code": "ZIP",
            "city_in_de": "City",
        }
    )

    return cities, centers


cities_gdf, centers_gdf = load_data()

cities_gdf = cities_gdf.to_crs(epsg=4326)
centers_gdf = centers_gdf.to_crs(epsg=4326)

numeric_columns = [
    c for c in cities_gdf.columns
    if "Rate" in c or "Price" in c or "% Change" in c
]

for col in numeric_columns:
    cities_gdf[col] = pd.to_numeric(cities_gdf[col], errors="coerce")

city_choices = sorted(cities_gdf["City"].dropna().unique().tolist())
default_city = "Chicago" if "Chicago" in city_choices else city_choices[0]


def format_value(value, metric):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if "%" in metric or "Change" in metric:
        return f"{value:.2f}%"
    if "Price" in metric:
        return f"${value:,.0f}"
    if "Rate" in metric:
        return f"{value:.4f} ¢/kWh"
    return f"{value:,.2f}"


def make_colormap(values, metric):
    clean = values.dropna()
    col_min = float(clean.min())
    col_max = float(clean.max())
    spread = col_max - col_min
    mean_val = float(clean.mean())
    if mean_val != 0 and (spread / abs(mean_val)) < 0.1:
        col_min = float(np.percentile(clean, 2))
        col_max = float(np.percentile(clean, 98))
    colormap = cm.linear.YlOrRd_09.scale(col_min, col_max)
    colormap.caption = metric
    return colormap, col_min, col_max


def dc_tooltip_html(facility, operator, street):
    if not facility or str(facility).strip() in ("", "nan"):
        return "<b>🏢 Data Center</b>"
    parts = [f"<b>🏢 {facility}</b>"]
    if operator and str(operator).strip() not in ("", "nan", "—"):
        parts.append(f"<span style='color:#999;'>Operator:</span> {operator}")
    if street and str(street).strip() not in ("", "nan", "—"):
        parts.append(f"<span style='color:#999;'>Address:</span> {street}")
    return "<br>".join(parts)


# -----------------------------
# UI
# -----------------------------
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Market Impact",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Filters (Optional)"),
                ui.input_select(
                    "city",
                    "Select City",
                    choices={c: c for c in city_choices},
                    selected=default_city,
                ),
                ui.input_select(
                    "metric",
                    "Select Metric to Visualize",
                    choices={c: c for c in numeric_columns},
                    selected=numeric_columns[0] if numeric_columns else None,
                ),
                ui.hr(),
                ui.markdown("**Project:** Urban DC Effects"),
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("City Map with DataCenters"),
                    ui.output_ui("map_plot"),
                ),
                col_widths=(12,),
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
        city_name = (input.city() or "").lower()
        df = cities_gdf[cities_gdf["City"].str.lower() == city_name].copy()
        df = df.reset_index(drop=True)
        return df

    @reactive.Calc
    def filtered_centers():
        city_name = (input.city() or "").lower()
        return centers_gdf[centers_gdf["City"].str.lower() == city_name]

    @render.ui
    def map_plot():
        city_gdf = filtered_city()
        centers_sel = filtered_centers()
        metric = input.metric()

        if city_gdf.empty:
            m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB dark_matter")
            return ui.HTML(f'<div style="height:600px; width:100%;">{m._repr_html_()}</div>')

        centroids = city_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
        center_lat = centroids.y.mean()
        center_lon = centroids.x.mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles="CartoDB dark_matter",
        )

        colormap, col_min, col_max = make_colormap(city_gdf[metric], metric)

        def style_function(feature):
            value = feature["properties"].get(metric)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return {"fillColor": "#333333", "color": "#444444", "weight": 0.5, "fillOpacity": 0.4}
            clamped = max(col_min, min(col_max, value))
            return {
                "fillColor": colormap(clamped),
                "color": "#111111",
                "weight": 0.5,
                "fillOpacity": 0.75,
            }

        def highlight_function(feature):
            return {"fillOpacity": 0.95, "weight": 2, "color": "white"}

        folium.GeoJson(
            city_gdf.__geo_interface__,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["ZCTA5CE20", metric],
                aliases=["ZIP Code", metric],
                localize=True,
                sticky=True,
                style=(
                    "background-color: #1e293b;"
                    "color: #f1f5f9;"
                    "font-family: monospace;"
                    "font-size: 13px;"
                    "padding: 6px 10px;"
                    "border-radius: 4px;"
                    "border: 1px solid #475569;"
                ),
            ),
        ).add_to(m)

        colormap.add_to(m)

        if not centers_sel.empty:
            for _, row in centers_sel.iterrows():
                facility = str(row.get("Facility Name", "") or "")
                operator = str(row.get("Operator", "") or "—")
                street   = str(row.get("Street",   "") or "—")

                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    icon=folium.Icon(
                        color="white",
                        icon_color="#1e293b",
                        icon="building",
                        prefix="fa",
                    ),
                    tooltip=folium.Tooltip(
                        dc_tooltip_html(facility, operator, street),
                        sticky=True,
                    ),
                ).add_to(m)

        return ui.HTML(f'<div style="height:600px; width:100%;">{m._repr_html_()}</div>')


# -----------------------------
# Run app
# -----------------------------
app = App(app_ui, server)