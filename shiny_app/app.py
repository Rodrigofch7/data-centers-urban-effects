from shiny import App, ui, render, reactive
import folium
import branca.colormap as cm
import geopandas as gpd
import pandas as pd
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

    cities = cities.rename(
        columns={
            "city_label": "City",
            "state": "State",
            "utility_name": "Utility",
            "ownership": "Ownership",
            "service_type": "Service Type",
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
                    "Select Metric to Visualize (Optional)",
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

        # Fallback center if city not found
        if city_gdf.empty:
            m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB dark_matter")
            return ui.HTML(f'<div style="height:600px; width:100%;">{m._repr_html_()}</div>')

        # Compute center from projected CRS to avoid geographic CRS warning
        centroids = city_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
        center_lat = centroids.y.mean()
        center_lon = centroids.x.mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=10,
            tiles="CartoDB dark_matter",
        )

        # ------------------------------------------------------------------
        # THE KEY FOLIUM PATTERN: use GeoJsonTooltip + style_function.
        #
        # Instead of Folium's Choropleth (which still has internal ID
        # matching), we use folium.GeoJson directly with a style_function
        # that reads the metric value straight from each feature's
        # properties dict. Zero ID matching — colors are applied per-feature
        # at render time with no join step that can silently fail.
        # ------------------------------------------------------------------
        col_min = float(city_gdf[metric].min())
        col_max = float(city_gdf[metric].max())

        # Build a branca colormap (Viridis equivalent)
        colormap = cm.linear.YlOrRd_09.scale(col_min, col_max)
        colormap.caption = metric

        # Convert to GeoJSON dict — to_json() keeps all properties intact
        geojson_data = city_gdf.__geo_interface__

        def style_function(feature):
            value = feature["properties"].get(metric)
            if value is None:
                return {
                    "fillColor": "#333333",
                    "color": "#555555",
                    "weight": 0.5,
                    "fillOpacity": 0.4,
                }
            return {
                "fillColor": colormap(value),
                "color": "#222222",
                "weight": 0.5,
                "fillOpacity": 0.75,
            }

        folium.GeoJson(
            geojson_data,
            style_function=style_function,
            name=metric,
        ).add_to(m)

        # Add colormap legend
        colormap.add_to(m)

        # Data center markers
        if not centers_sel.empty:
            for _, row in centers_sel.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=6,
                    color="red",
                    fill=True,
                    fill_color="red",
                    fill_opacity=0.9,
                    popup=folium.Popup(
                        str(row.get("Facility Name", "Data Center")), max_width=200
                    ),
                ).add_to(m)

        map_html = m._repr_html_()
        return ui.HTML(f'<div style="height:600px; width:100%;">{map_html}</div>')


# -----------------------------
# Run app
# -----------------------------
app = App(app_ui, server)
