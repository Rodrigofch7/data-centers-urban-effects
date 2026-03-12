from shiny import App, ui, render, reactive
import folium
import branca.colormap as cm
import geopandas as gpd
import fiona
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import io, base64
import json

# To run: uv run shiny run shiny_app.app.py or uv run shiny run shiny_app/app.py
# To deploy: uv run rsconnect deploy shiny shiny_app/

# =============================================================================
# BRAND & DESIGN TOKENS
# =============================================================================
COLOR_MAROON = "#800000"
COLOR_MAROON_DARK = "#5a0000"
COLOR_MAROON_MID = "#a00000"

COLOR_DARK_BACKGROUND = "#0d1117"
COLOR_PANEL_BACKGROUND = "#161b22"
COLOR_CARD_BACKGROUND = "#1c2128"
COLOR_BORDER = "#30363d"
COLOR_TEXT_PRIMARY = "#e6edf3"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_ACCENT = "#f0a500"

# =============================================================================
# COLORBLIND-FRIENDLY COLORMAPS PER METRIC GROUP
# =============================================================================
COLORMAP_BY_METRIC_GROUP = {
    "zillow": "YlOrRd",
    "census": "RdPu",
    "centers": "YlGn",
    "electricity": "YlOrBr",
    "water": "GnBu",
    "hhc": "OrRd",
}


def get_hex_color_stops_from_matplotlib_colormap(colormap_name: str, num_stops: int = 9) -> list:
    """Convert a named matplotlib colormap into a list of evenly-spaced hex color strings."""
    colormap = plt.get_cmap(colormap_name)
    return [mcolors.to_hex(colormap(i / (num_stops - 1))) for i in range(num_stops)]


def build_choropleth_colormap(column_values: pd.Series, metric_label: str, metric_group: str):
    """
    Build a Folium LinearColormap for a given data column.
    Clips the color scale to the 2nd-98th percentile to reduce outlier distortion.
    Returns the colormap plus the clipped min/max values used for scaling.
    """
    non_null_values = column_values.dropna()
    if non_null_values.empty:
        fallback_colormap = cm.LinearColormap(
            ["#1a1a2e", "#f0a500"], vmin=0, vmax=1, caption=metric_label
        )
        return fallback_colormap, 0.0, 1.0

    scale_min = float(np.percentile(non_null_values, 2))
    scale_max = float(np.percentile(non_null_values, 98))

    if scale_min == scale_max:
        scale_min, scale_max = float(non_null_values.min()), float(non_null_values.max())
    if scale_min == scale_max:
        scale_max = scale_min + 1

    hex_color_stops = get_hex_color_stops_from_matplotlib_colormap(
        COLORMAP_BY_METRIC_GROUP.get(metric_group, "viridis"), 9
    )
    choropleth_colormap = cm.LinearColormap(
        hex_color_stops, vmin=scale_min, vmax=scale_max, caption=metric_label
    )
    return choropleth_colormap, scale_min, scale_max


# =============================================================================
# COLUMN DEFINITIONS
# =============================================================================
ZILLOW_YEARS = [2010, 2019, 2024]
ZILLOW_COLUMN_LABELS = [f"Median Home Value ({year})" for year in ZILLOW_YEARS]

CENSUS_COLUMN_LABELS = [
    "Median Household Income",
    "Population Density (per sq km)",
    "Broadband Adoption Rate (%)",
    "Poverty Rate (%)",
    "Unemployment Rate (%)",
    "Renter-Occupied Share (%)",
]

DATA_CENTER_COLUMN_LABELS = [
    "Total Data Centers",
    "Data Centers per 100,000 Residents",
]

ELECTRICITY_COLUMN_LABELS = [
    "Electricity: % Paying Above $50/month",
    "Electricity: % Paying Above $150/month",
    "Electricity: % Paying $250+/month",
]

WATER_SEWER_COLUMN_LABELS = [
    "Water & Sewer: % Paying Above $125/year",
    "Water & Sewer: % Paying Above $500/year",
    "Water & Sewer: % Paying $1,000+/year",
]

HOUSING_COST_BURDEN_COLUMN_LABELS = [
    "Household Cost Score (2007\u20132011)",
    "Household Cost Score (2019\u20132023)",
    "Household Cost Score (2020\u20132024)",
]

OPTIONAL_COLUMN_LABELS = ["Total Population", "Land Area (sq meters)"]

METRIC_GROUP_DISPLAY_CHOICES = {}


# =============================================================================
# LOAD & PRE-PROCESS DATA
# =============================================================================
def load_all_geodata():
    """Load ZIP-code polygons, data center points, and the impact score CSV."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    zip_polygons_path = os.path.join(app_dir, "Data", "Chicago.gpkg")
    data_centers_path = os.path.join(app_dir, "Data", "ChicagoDataCenters.gpkg")
    impact_scores_path = os.path.join(app_dir, "Data", "chicag_data_centers_impact_scores.csv")

    zip_polygons_gdf = gpd.read_file(zip_polygons_path)
    data_centers_gdf = gpd.read_file(data_centers_path)
    impact_scores_df = (
        pd.read_csv(impact_scores_path) if os.path.exists(impact_scores_path) else pd.DataFrame()
    )
    return zip_polygons_gdf, data_centers_gdf, impact_scores_df, zip_polygons_path


zip_polygons_gdf, data_centers_gdf, impact_scores_df, zip_polygons_path = load_all_geodata()

zip_polygons_gdf = zip_polygons_gdf.to_crs(epsg=4326)
data_centers_gdf = data_centers_gdf.to_crs(epsg=4326)

zip_polygons_gdf.geometry = zip_polygons_gdf.geometry.simplify(
    tolerance=0.001, preserve_topology=True
)
data_centers_gdf.geometry = data_centers_gdf.geometry.simplify(
    tolerance=0.001, preserve_topology=True
)

_zip_centroids = zip_polygons_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
DEFAULT_MAP_CENTER = [float(_zip_centroids.y.mean()), float(_zip_centroids.x.mean())]

TOOLTIP_GEO_FIELDS = []
TOOLTIP_GEO_ALIASES = []
for column_name, display_alias in [
    ("Zip Code", "📍 ZIP"),
    ("City", "🏙️ City"),
    ("Community", "🏘️ Community"),
    ("County", "🗺️ County"),
    ("State", "📌 State"),
]:
    if column_name in zip_polygons_gdf.columns:
        TOOLTIP_GEO_FIELDS.append(column_name)
        TOOLTIP_GEO_ALIASES.append(display_alias)

with fiona.open(zip_polygons_path) as zip_source:
    zip_attribute_records = [feature["properties"] for feature in zip_source]
zip_attributes_df = pd.DataFrame(zip_attribute_records)


def get_columns_present_in_dataframe(candidate_columns: list) -> list:
    """Return only those column names that actually exist in zip_attributes_df."""
    return [col for col in candidate_columns if col in zip_attributes_df.columns]


ZILLOW_COLUMNS = get_columns_present_in_dataframe(ZILLOW_COLUMN_LABELS)
CENSUS_COLUMNS = get_columns_present_in_dataframe(CENSUS_COLUMN_LABELS)
DATA_CENTER_COLUMNS = get_columns_present_in_dataframe(DATA_CENTER_COLUMN_LABELS)
ELECTRICITY_COLUMNS = get_columns_present_in_dataframe(ELECTRICITY_COLUMN_LABELS)
WATER_SEWER_COLUMNS = get_columns_present_in_dataframe(WATER_SEWER_COLUMN_LABELS)
HOUSING_COST_BURDEN_COLUMNS = get_columns_present_in_dataframe(HOUSING_COST_BURDEN_COLUMN_LABELS)
OPTIONAL_COLUMNS = get_columns_present_in_dataframe(OPTIONAL_COLUMN_LABELS)

ALL_NUMERIC_COLUMNS = (
    ZILLOW_COLUMNS
    + CENSUS_COLUMNS
    + DATA_CENTER_COLUMNS
    + ELECTRICITY_COLUMNS
    + WATER_SEWER_COLUMNS
    + HOUSING_COST_BURDEN_COLUMNS
    + OPTIONAL_COLUMNS
)

for column_name in ALL_NUMERIC_COLUMNS:
    if column_name in zip_attributes_df.columns:
        zip_attributes_df[column_name] = pd.to_numeric(
            zip_attributes_df[column_name], errors="coerce"
        )
    if column_name in zip_polygons_gdf.columns:
        zip_polygons_gdf[column_name] = pd.to_numeric(
            zip_polygons_gdf[column_name], errors="coerce"
        )

COLUMN_TO_METRIC_GROUP = {}
for col in ZILLOW_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "zillow"
for col in CENSUS_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "census"
for col in DATA_CENTER_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "centers"
for col in ELECTRICITY_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "electricity"
for col in WATER_SEWER_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "water"
for col in HOUSING_COST_BURDEN_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "hhc"
for col in OPTIONAL_COLUMNS:
    COLUMN_TO_METRIC_GROUP[col] = "census"

if ZILLOW_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["zillow"] = "🏠  Home Values"
if CENSUS_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["census"] = "👥  Demographics"
if DATA_CENTER_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["centers"] = "🏢  Data Centers"
if ELECTRICITY_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["electricity"] = "⚡  Electricity"
if WATER_SEWER_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["water"] = "💧  Water & Sewer"
if HOUSING_COST_BURDEN_COLUMNS:
    METRIC_GROUP_DISPLAY_CHOICES["hhc"] = "💰 Housing Cost Burden"

ZIP_POLYGONS_GEOJSON = zip_polygons_gdf.__geo_interface__

# Path to the merged data centers + housing CSV used for the company bar chart
DATACENTERS_HOUSING_CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Data", "datacenters_housing_merged.csv"
)


def load_boundary_layer(filename: str):
    """Load an optional boundary GeoPackage (state, county, city) and reproject to WGS-84."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data", filename)
    if os.path.exists(path):
        return gpd.read_file(path).to_crs(epsg=4326)
    return None


illinois_boundary_gdf = load_boundary_layer("illinois.gpkg")
cook_county_boundary_gdf = load_boundary_layer("cook_county.gpkg")
chicago_city_boundary_gdf = load_boundary_layer("chicagoproper.gpkg")

ILLINOIS_BOUNDARY_GEOJSON = (
    illinois_boundary_gdf.__geo_interface__ if illinois_boundary_gdf is not None else None
)
COOK_COUNTY_BOUNDARY_GEOJSON = (
    cook_county_boundary_gdf.__geo_interface__ if cook_county_boundary_gdf is not None else None
)
CHICAGO_CITY_BOUNDARY_GEOJSON = (
    chicago_city_boundary_gdf.__geo_interface__ if chicago_city_boundary_gdf is not None else None
)


# =============================================================================
# NUMBER FORMATTING HELPERS
# =============================================================================
def format_number_for_display(value, is_currency: bool = False, decimal_places: int = None) -> str:
    """
    Format a numeric value for human-readable display.
    Examples: $1.2M · $450k · 1,234 · 45.3%
    Returns "—" for None or NaN values.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    value = float(value)
    if is_currency:
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"${value / 1_000:.0f}k"
        return f"${value:,.0f}"
    if decimal_places is not None:
        return f"{value:,.{decimal_places}f}"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value:,.0f}"
    return f"{value:,.3f}"


# =============================================================================
# HELPERS
# =============================================================================
def build_data_center_tooltip_html(row: pd.Series) -> str:
    """Build the HTML tooltip shown when hovering a data center marker on the map."""
    facility_name = str(row.get("Facility Name", row.get("facility", "")) or "").strip()
    zip_code = str(row.get("Data Center ZIP Code", row.get("zip_code", "—")) or "—").strip()
    operator_name = str(row.get("Operator", row.get("operator", "—")) or "—").strip()
    city_name = str(row.get("City", row.get("city_in_de", "—")) or "—").strip()

    for placeholder in ("", "nan", "None"):
        if zip_code == placeholder:
            zip_code = "—"
        if operator_name == placeholder:
            operator_name = "—"
        if city_name == placeholder:
            city_name = "—"

    header_html = (
        f"<b>🏢 {facility_name}</b>"
        if facility_name and facility_name not in ("nan", "None", "")
        else "<b>🏢 Data Center</b>"
    )
    return (
        f"<div style='font-family:monospace;line-height:1.8;'>"
        f"{header_html}<br>"
        f"<span style='color:#8b949e;'>City&nbsp;&nbsp;&nbsp;&nbsp;</span>{city_name}<br>"
        f"<span style='color:#8b949e;'>ZIP&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>{zip_code}<br>"
        f"<span style='color:#8b949e;'>Operator&nbsp;</span>{operator_name}"
        f"</div>"
    )


def encode_matplotlib_figure_as_html_img(fig, dpi: int = 150) -> str:
    """Save a matplotlib Figure to a base64 PNG and return an <img> HTML tag."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=dpi)
    buffer.seek(0)
    base64_png = base64.b64encode(buffer.read()).decode()
    plt.close(fig)
    return f'<img src="data:image/png;base64,{base64_png}" style="width:100%;border-radius:6px;">'


def add_data_center_markers_to_map(folium_map: folium.Map):
    """Add a styled marker pin for every data center in data_centers_gdf."""
    for _, row in data_centers_gdf.iterrows():
        point_geometry = row.geometry
        if point_geometry.geom_type == "MultiPoint":
            point_geometry = list(point_geometry.geoms)[0]
        folium.Marker(
            location=[point_geometry.y, point_geometry.x],
            icon=folium.Icon(color="white", icon_color=COLOR_MAROON, icon="building", prefix="fa"),
            tooltip=folium.Tooltip(
                build_data_center_tooltip_html(row),
                sticky=True,
                style=(
                    f"background-color:{COLOR_CARD_BACKGROUND};"
                    f"color:{COLOR_TEXT_PRIMARY};"
                    "font-family:monospace;"
                    "font-size:12px;"
                    "padding:10px 14px;"
                    "border-radius:7px;"
                    f"border:1px solid {COLOR_BORDER};"
                ),
            ),
        ).add_to(folium_map)


# =============================================================================
# CSS
# =============================================================================
DASHBOARD_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

html, body {{
  font-family: 'DM Sans', sans-serif;
  background: {COLOR_DARK_BACKGROUND} !important;
  color: {COLOR_TEXT_PRIMARY} !important;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}}
.card p, .card li, .card span:not(.bslib-full-screen-enter) {{
  color: {COLOR_TEXT_PRIMARY};
}}

@keyframes shimmer {{
  0%   {{ background-position: -400px 0; }}
  100% {{ background-position:  400px 0; }}
}}
.skeleton-wrap {{ padding: 16px; }}
.skeleton-bar {{
  background: linear-gradient(90deg, {COLOR_PANEL_BACKGROUND} 25%, {COLOR_CARD_BACKGROUND} 50%, {COLOR_PANEL_BACKGROUND} 75%);
  background-size: 800px 100%;
  animation: shimmer 1.4s infinite linear;
  opacity: 0.85;
}}

@keyframes fadeSlideIn {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
.shiny-bound-output > * {{ animation: fadeSlideIn 0.3s ease forwards; }}

.navbar {{
  background: linear-gradient(135deg, {COLOR_MAROON_DARK} 0%, {COLOR_MAROON} 55%, {COLOR_MAROON_MID} 100%) !important;
  border-bottom: 1px solid {COLOR_MAROON_DARK} !important;
  box-shadow: 0 2px 24px rgba(0,0,0,0.7);
  padding: 0 48px !important;
  min-height: 60px !important;
  align-items: flex-end !important;
}}
.navbar-brand {{
  font-family: 'DM Serif Display', serif !important;
  font-size: 19px !important;
  letter-spacing: 0.02em;
  color: #fff !important;
  padding-bottom: 10px !important;
}}
.navbar-nav {{ align-items: flex-end !important; }}
.navbar-nav .nav-link {{
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  color: rgba(255,255,255,0.78) !important;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0 18px 10px !important;
  transition: color 0.18s, border-bottom 0.18s;
}}
.navbar-nav .nav-link:hover,
.navbar-nav .nav-link.active {{
  color: #fff !important;
  border-bottom: 2px solid {COLOR_TEXT_ACCENT};
}}
.uchicago-logo-nav {{ height: 36px; display: block; margin: 0 6px; }}

#bottom-bar {{
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 1000; height: 42px;
  background: linear-gradient(135deg, {COLOR_MAROON_DARK} 0%, {COLOR_MAROON} 55%, {COLOR_MAROON_MID} 100%);
  border-top: 1px solid {COLOR_MAROON_DARK};
  box-shadow: 0 -2px 24px rgba(0,0,0,0.7);
  display: flex; align-items: center; padding: 0 48px; gap: 32px;
  transform: translateY(100%); transition: transform 0.3s ease;
}}
#bottom-bar.visible {{ transform: translateY(0); }}
#bottom-bar span {{
  font-family: 'DM Sans', sans-serif; font-weight: 500; font-size: 12px;
  color: rgba(255,255,255,0.78); letter-spacing: 0.1em; text-transform: uppercase;
}}
body {{ padding-bottom: 42px !important; }}

.sidebar,
.bslib-sidebar-layout > .sidebar,
.bslib-sidebar-layout > .sidebar > .sidebar-content,
aside.sidebar {{
  background: {COLOR_PANEL_BACKGROUND} !important;
  border-right: 1px solid {COLOR_BORDER} !important;
  color: {COLOR_TEXT_PRIMARY} !important;
  padding: 20px 18px !important;
}}
.sidebar-section-title {{
  font-family: 'IBM Plex Mono', monospace; font-size: 9px; letter-spacing: 0.15em;
  text-transform: uppercase; color: {COLOR_TEXT_ACCENT}; margin: 18px 0 5px;
  opacity: 0.85; display: flex; align-items: center; justify-content: space-between; cursor: default;
}}
.sidebar label, .sidebar .control-label,
.sidebar .form-check-label, .sidebar p, .sidebar strong {{
  color: #d0d7de !important; font-size: 13px; font-weight: 400;
}}
.sidebar h4 {{
  font-family: 'DM Serif Display', serif !important; font-size: 18px !important;
  color: #ffffff !important; margin: 0 0 8px; letter-spacing: 0.01em;
  padding-bottom: 8px; border-bottom: 1px solid {COLOR_BORDER};
}}
.sidebar .form-select, .sidebar .form-control, .sidebar select {{
  background: {COLOR_CARD_BACKGROUND} !important; color: {COLOR_TEXT_PRIMARY} !important;
  border: 1px solid {COLOR_BORDER} !important; border-radius: 6px !important;
  font-size: 13px; transition: border-color 0.2s, box-shadow 0.2s;
}}
.sidebar .form-select:focus {{
  border-color: {COLOR_MAROON} !important;
  box-shadow: 0 0 0 2px rgba(128,0,0,0.22) !important;
}}
.sidebar .selectize-input, .sidebar .selectize-input input {{
  background: {COLOR_CARD_BACKGROUND} !important; color: {COLOR_TEXT_PRIMARY} !important;
  border: 1px solid {COLOR_BORDER} !important; border-radius: 6px !important;
  box-shadow: none !important; font-size: 13px; transition: border-color 0.2s;
}}
.sidebar .selectize-input.focus {{
  border-color: {COLOR_MAROON} !important;
  box-shadow: 0 0 0 2px rgba(128,0,0,0.22) !important;
}}
.sidebar .selectize-dropdown, .sidebar .selectize-dropdown .option {{
  background: {COLOR_PANEL_BACKGROUND} !important; color: {COLOR_TEXT_PRIMARY} !important;
  border: 1px solid {COLOR_BORDER} !important; font-size: 13px;
}}
.sidebar .selectize-dropdown .option:hover,
.sidebar .selectize-dropdown .option.active {{
  background: {COLOR_MAROON} !important; color: #fff !important;
}}
.sidebar .form-check-input {{
  border-color: {COLOR_BORDER} !important; background: {COLOR_CARD_BACKGROUND} !important;
  transition: background 0.15s, border-color 0.15s;
}}
.sidebar .form-check-input:checked {{
  background: {COLOR_MAROON} !important; border-color: {COLOR_MAROON} !important;
}}
.sidebar .form-check-input:focus {{ box-shadow: 0 0 0 2px rgba(128,0,0,0.25) !important; }}
.sidebar hr {{ border: none; border-top: 1px solid {COLOR_BORDER} !important; margin: 16px 0; opacity: 1; }}
.source-note {{
  font-family: 'DM Sans', sans-serif; font-size: 11px; color: #a1adb9; line-height: 1.7;
  margin-top: 12px; padding-top: 12px; border-top: 1px solid {COLOR_BORDER};
}}

.card {{
  background: {COLOR_CARD_BACKGROUND} !important; border: 1px solid {COLOR_BORDER} !important;
  border-radius: 10px !important; overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
  transition: box-shadow 0.22s ease, border-color 0.22s ease, transform 0.15s ease;
}}
.card:hover {{
  box-shadow: 0 8px 36px rgba(0,0,0,0.6), 0 0 0 1px {COLOR_MAROON_DARK}, inset 0 1px 0 rgba(255,255,255,0.06);
  border-color: {COLOR_MAROON_DARK} !important; transform: translateY(-1px);
}}
.card-header {{
  background: linear-gradient(90deg, {COLOR_MAROON_DARK} 0%, {COLOR_MAROON} 60%, {COLOR_MAROON_MID} 100%) !important;
  color: #fff !important; font-family: 'IBM Plex Mono', monospace !important;
  font-size: 10px !important; font-weight: 500 !important;
  letter-spacing: 0.13em !important; text-transform: uppercase !important;
  padding: 9px 16px !important; border-bottom: none !important;
  display: flex; align-items: center; gap: 8px;
}}
.bslib-full-screen-enter {{ color: rgba(255,255,255,0.55) !important; transition: color 0.15s; }}
.bslib-full-screen-enter:hover {{ color: #fff !important; }}
.bslib-full-screen-exit {{
  background: {COLOR_MAROON} !important; border-color: {COLOR_MAROON_DARK} !important; color: #fff !important;
}}
body, .bslib-page-sidebar, .bslib-sidebar-layout {{ background: {COLOR_DARK_BACKGROUND} !important; }}

::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {COLOR_DARK_BACKGROUND}; }}
::-webkit-scrollbar-thumb {{ background: {COLOR_BORDER}; border-radius: 3px; transition: background 0.2s; }}
::-webkit-scrollbar-thumb:hover {{ background: {COLOR_MAROON}; }}

.tab-content > .tab-pane, .bslib-page-sidebar > .main {{ padding: 16px !important; }}
.card-body {{ color: {COLOR_TEXT_PRIMARY} !important; font-size: 13px; line-height: 1.6; }}
.navbar-nav .nav-link.active {{
  color: #fff !important; border-bottom: 3px solid {COLOR_TEXT_ACCENT} !important; font-weight: 600 !important;
}}

@keyframes countUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
.kpi-value {{ animation: countUp 0.5s cubic-bezier(0.22,1,0.36,1) both; }}
.kpi-value:nth-child(1) {{ animation-delay: 0.05s; }}
.kpi-value:nth-child(2) {{ animation-delay: 0.15s; }}
.kpi-value:nth-child(3) {{ animation-delay: 0.25s; }}

.empty-state {{
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 40px 24px; gap: 12px; color: {COLOR_TEXT_SECONDARY};
  font-family: 'IBM Plex Mono', monospace; font-size: 12px; text-align: center;
}}
.empty-state svg {{ opacity: 0.3; }}

.sidebar-toggle, [data-bs-toggle="collapse"], .bslib-sidebar-layout .collapse-toggle {{
  color: #ffffff !important; background: transparent !important;
}}
.sidebar-toggle svg, [data-bs-toggle="collapse"] svg, .bslib-sidebar-layout .collapse-toggle svg {{
  fill: #ffffff !important; stroke: #ffffff !important; color: #ffffff !important;
}}
"""


# =============================================================================
# UI
# =============================================================================
app_ui = ui.page_navbar(
    # ── INFRASTRUCTURE ATLAS ──────────────────────────────────────────────────
    ui.nav_panel(
        "Infrastructure Atlas",
        ui.div(
            ui.HTML("""
<div style="
  position:relative;overflow:hidden;
  background:linear-gradient(135deg,#0d1117 0%,#1a0a0a 40%,#1c1020 100%);
  border:1px solid #30363d;border-radius:12px;
  padding:32px 36px 28px;margin-bottom:4px;">
  <div style="position:absolute;right:-20px;top:-30px;font-size:220px;line-height:1;opacity:0.03;
    font-family:'DM Serif Display',serif;color:#fff;pointer-events:none;user-select:none;">⬡</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:0.18em;
    text-transform:uppercase;color:#800000;margin-bottom:12px;display:flex;align-items:center;gap:8px;">
    <span style="display:inline-block;width:24px;height:1px;background:#800000;"></span>
    Research Question
  </div>
  <div style="font-family:'DM Serif Display',serif;font-size:26px;color:#ffffff;margin-bottom:16px;
    line-height:1.25;letter-spacing:0.01em;max-width:680px;">
    Do data centers change the<br>neighborhoods around them?
  </div>
  <div style="width:48px;height:2px;background:linear-gradient(90deg,#800000,transparent);margin-bottom:18px;"></div>
  <div style="font-family:'DM Sans',sans-serif;font-size:13.5px;color:#a1adb9;line-height:1.75;
    max-width:820px;margin-bottom:24px;">
    This dashboard examines <span style="color:#e6edf3;font-weight:500;">45 data center facilities
    across the Chicago metro area</span> and their relationship to local housing markets.
    For each facility we compare housing prices and housing-cost burden scores
    <span style="color:#e6edf3;font-weight:500;">before and after the first operation permit</span>
    was issued, then combine those changes into a single
    <span style="color:#f0a500;font-weight:600;">impact score</span>.
    A <span style="color:#4ade80;font-weight:500;">positive score</span> means the surrounding ZIP code
    became more expensive <em>and</em> housing-cost burden increased after the facility opened;
    a <span style="color:#f87171;font-weight:500;">negative score</span> suggests the opposite.
  </div>
  <div style="font-family:'DM Sans',sans-serif;font-size:12.5px;color:#8b949e;line-height:1.75;
    max-width:820px;margin-bottom:24px;border-top:1px solid #30363d;padding-top:16px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:0.15em;
      text-transform:uppercase;color:#800000;display:block;margin-bottom:6px;">Background</span>
    Data Centers are facilities with IT infrastructure that enables companies and users to build,
    run, and deliver applications and services. As AI becomes an increasingly integral part of
    digital products and services, new data centers are built at an unprecedented rate. However, data
    centers have been subject to controversy among many communities for how they have affected
    costs of living. In <span style="color:#e6edf3;font-weight:500;">Data Centers Next Door</span>,
    we aim to see if communities in the Chicagoland area have seen similar rising costs due to
    the building of data centers in their community.
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:0.12em;
      text-transform:uppercase;color:#8b949e;margin-right:4px;">Explore →</span>
    <span style="display:inline-flex;align-items:center;gap:6px;background:rgba(128,0,0,0.18);
      border:1px solid rgba(128,0,0,0.4);border-radius:20px;padding:5px 14px;
      font-family:'DM Sans',sans-serif;font-size:12px;color:#e6edf3;">
      <span style="font-size:13px;">📍</span> This tab — facility scores &amp; comparisons
    </span>
    <span style="display:inline-flex;align-items:center;gap:6px;background:rgba(30,40,55,0.6);
      border:1px solid #30363d;border-radius:20px;padding:5px 14px;
      font-family:'DM Sans',sans-serif;font-size:12px;color:#c9d1d9;">
      <span style="font-size:13px;">🗺️</span> Map — geographic patterns by ZIP
    </span>
  </div>
</div>
"""),
            ui.output_ui("atlas_kpi_strip"),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Data Centers Over Time"),
                    ui.output_ui("atlas_timeseries_chart"),
                    ui.p(
                        "The first data center in Chicagoland started operating early on in 2000, after which for "
                        "the next seven years, only one other data center started operating. However, starting in "
                        "2008, the rate at which new data centers were built grew dramatically. For example, between "
                        "just 2014 and 2015, 8 new data centers started operating. We anticipate that this dramatic "
                        "rate of growth will continue in the upcoming years, especially as AI usage proliferates.",
                        style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{COLOR_TEXT_SECONDARY};"
                        "line-height:1.7;padding:4px 8px 8px;margin:0;",
                    ),
                    full_screen=True,
                ),
                ui.card(
                    ui.card_header("Data Centers by Company"),
                    ui.output_ui("atlas_company_bar_chart"),
                    ui.p(
                        "The company with the most data centers (5) is Digital Reality. There are 25 companies "
                        "with one datacenter each. It should be noted that some companies may be owned by the same "
                        "parent companies (e.g., Aligned Data Centers is owned by BlackRock and its financial partners).",
                        style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{COLOR_TEXT_SECONDARY};"
                        "line-height:1.7;padding:4px 8px 8px;margin:0;",
                    ),
                    full_screen=True,
                ),
                col_widths=(6, 6),
            ),
            ui.card(
                ui.card_header("Before vs. After Permit Comparison"),
                ui.div(
                    ui.input_select(
                        "before_after_metric",
                        None,
                        choices={
                            "price": "🏠  Housing Price",
                            "hc_score": "💰  Housing Cost Score",
                        },
                        selected="price",
                    ),
                    style=f"padding:10px 16px 0;background:{COLOR_CARD_BACKGROUND};max-width:260px;",
                ),
                ui.output_ui("atlas_before_after_price_chart"),
                full_screen=True,
            ),
            style="display:flex; flex-direction:column; gap:16px; padding:16px 12px;",
        ),
        ui.card(
            ui.card_header("Facility Impact Directory"),
            ui.p(
                "The Facility Impact Directory shows the impact scores for each data center. "
                "A small number of facilities have the highest scores, suggesting larger combined changes in "
                "housing prices and housing cost indicators. Most data centers fall within a middle range, "
                "indicating moderate impact, while several on the right show lower scores and smaller changes. "
                "Overall, the distribution highlights variation in the potential local effects associated "
                "with different data center developments.",
                style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{COLOR_TEXT_SECONDARY};"
                "line-height:1.7;padding:8px 16px 4px;margin:0;",
            ),
            ui.output_ui("atlas_facility_directory_table"),
            full_screen=True,
        ),
    ),
    # ── MAP ────────────────────────────────────────────────────────────────────
    ui.nav_panel(
        "Map",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Explore"),
                ui.div("METRIC GROUP", class_="sidebar-section-title"),
                ui.input_select(
                    "metric_group",
                    None,
                    choices=METRIC_GROUP_DISPLAY_CHOICES,
                    selected=list(METRIC_GROUP_DISPLAY_CHOICES.keys())[0],
                ),
                ui.div("VARIABLE", class_="sidebar-section-title"),
                ui.output_ui("metric_variable_selector"),
                ui.hr(),
                ui.input_checkbox("show_data_center_markers", "Data Centers", value=True),
                ui.input_checkbox("show_illinois_boundary", "Illinois", value=True),
                ui.input_checkbox("show_cook_county_boundary", "Cook County", value=True),
                ui.input_checkbox("show_chicago_city_boundary", "Chicago", value=True),
                ui.hr(),
                ui.HTML(f"""
                <div id="map-guide-wrap" style="margin-bottom:12px;">
                <button onclick="(function(){{
                    var b=document.getElementById('map-guide-body');
                    var arr=document.getElementById('map-guide-arrow');
                    var open=b.style.display!=='none';
                    b.style.display=open?'none':'block';
                    arr.style.transform=open?'rotate(0deg)':'rotate(180deg)';
                }})()" style="width:100%;display:flex;align-items:center;justify-content:space-between;
                    background:{COLOR_CARD_BACKGROUND};border:1px solid {COLOR_BORDER};border-radius:8px;
                    padding:9px 16px;cursor:pointer;transition:border-color 0.2s;">
                  <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                    letter-spacing:0.13em;text-transform:uppercase;color:{COLOR_TEXT_SECONDARY};">
                    🗺️ &nbsp;How to use this map
                  </span>
                  <svg id="map-guide-arrow" width="12" height="12" viewBox="0 0 24 24"
                    fill="none" stroke="{COLOR_TEXT_SECONDARY}" stroke-width="2.5" stroke-linecap="round"
                    style="transition:transform 0.25s ease;">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </button>
                <div id="map-guide-body" style="display:none;background:{COLOR_CARD_BACKGROUND};
                    border:1px solid {COLOR_BORDER};border-top:none;
                    border-radius:0 0 8px 8px;padding:14px 18px 16px;">
                  <div style="font-family:'DM Sans',sans-serif;font-size:12.5px;
                    color:{COLOR_TEXT_SECONDARY};line-height:1.8;">
                    Pick a <span style="color:{COLOR_TEXT_PRIMARY};font-weight:500;">Metric Group</span> and
                    <span style="color:{COLOR_TEXT_PRIMARY};font-weight:500;">Variable</span> from the sidebar —
                    the map shades each ZIP code accordingly.
                    <span style="color:{COLOR_TEXT_PRIMARY};font-weight:500;">Darker = higher values</span>;
                    the scale clips at the 2nd–98th percentile to reduce outlier distortion.
                    Hover any ZIP for details.
                  </div>
                </div>
                </div>
                """),
                ui.hr(),
                ui.div(
                    "Sources: Zillow (2010, 2019, 2024) · ACS 2022 · NHGIS 2022 · Manual DC inventory",
                    class_="source-note",
                ),
                style=f"background:{COLOR_PANEL_BACKGROUND}; min-width:225px;",
            ),
            ui.div(
                ui.card(
                    ui.card_header("Chicago Metro — ZIP Code Choropleth"),
                    ui.output_ui("choropleth_map"),
                ),
                style="position:relative;",
            ),
        ),
    ),
    ui.nav_spacer(),
    ui.nav_control(ui.tags.img(src="uchicago_logo.png", class_="uchicago-logo-nav")),
    header=ui.tags.head(
        ui.tags.style(DASHBOARD_CSS),
        ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
        ui.tags.link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        ui.tags.script("""
          document.addEventListener('DOMContentLoaded', function() {
            var bottomBar = document.createElement('div');
            bottomBar.id = 'bottom-bar';
            bottomBar.innerHTML = '<span>— University of Chicago —</span>';
            document.body.appendChild(bottomBar);
            window.addEventListener('scroll', function() {
              bottomBar.classList.toggle('visible', window.scrollY > 40);
            }, { passive: true });
          });
          document.addEventListener('keydown', function(e) {
            if (e.target.tagName==='INPUT'||e.target.tagName==='SELECT'||e.target.tagName==='TEXTAREA') return;
            var navLinks = document.querySelectorAll('.navbar-nav .nav-link');
            var keyToTabIndex = {'1':0,'2':1};
            if (keyToTabIndex[e.key]!==undefined && navLinks[keyToTabIndex[e.key]]) {
              navLinks[keyToTabIndex[e.key]].click(); e.preventDefault();
            }
          });
        """),
    ),
    title=ui.HTML(
        '<span style="display:inline-flex;flex-direction:column;line-height:1.1;vertical-align:middle;gap:1px;">'
        "<span style=\"font-family:'IBM Plex Mono',monospace;font-size:8.5px;color:#f0a500;letter-spacing:0.2em;text-transform:uppercase;\">Chicagoland</span>"
        "<span style=\"font-family:'DM Serif Display',serif;font-size:17px;color:#fff;letter-spacing:0.02em;\">Data Center Dashboard</span>"
        "</span>"
    ),
    bg=COLOR_MAROON,
    inverse=True,
)


# =============================================================================
# SERVER
# =============================================================================
def server(input, output, session):
    # ── SHARED REACTIVE DATA ─────────────────────────────────────────────────

    @reactive.Calc
    def get_cleaned_impact_scores_df():
        """
        Coerce all numeric columns in the impact scores CSV to float.
        Returns an empty DataFrame if the file was not found at startup.
        """
        if impact_scores_df.empty:
            return pd.DataFrame()
        df = impact_scores_df.copy()
        numeric_impact_columns = [
            "Housing_Avg_Price",
            "Housing_Avg_Price_Before_Permit",
            "Housing_Avg_Price_After_Permit",
            "HC_Score_Before",
            "HC_Score_After",
            "Housing_Change",
            "HC_Score_Change",
            "Complete",
            "Housing_Change_score",
            "Housing_Change_z_score",
            "HC_Score_Change_score",
            "HC_Score_Change_z_score",
            "impact_score",
            "impact_z_score",
        ]
        for col in numeric_impact_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "First_Operation_Permit" in df.columns:
            df["Year"] = pd.to_numeric(df["First_Operation_Permit"], errors="coerce")
        return df

    def render_empty_state(
        headline: str = "Impact data file not found",
        subtext: str = "Place chicag_data_centers_impact_scores.csv in the Data/ folder",
    ):
        """Return a styled empty-state UI block with an info icon, headline, and subtext."""
        return ui.HTML(
            f"""<div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="{COLOR_TEXT_SECONDARY}" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <div style="color:{COLOR_TEXT_PRIMARY};font-weight:500;">{headline}</div>
              <div style="font-size:11px;">{subtext}</div>
            </div>"""
        )

    # ── INFRASTRUCTURE ATLAS OUTPUTS ─────────────────────────────────────────

    @render.ui
    def atlas_kpi_strip():
        """Render the three top-line KPI cards: facility count, avg impact, % positive."""
        df = get_cleaned_impact_scores_df()
        if df.empty:
            return render_empty_state()

        num_facilities = len(df)
        avg_impact_score = (
            df["impact_score"].mean() if "impact_score" in df.columns else float("nan")
        )

        avg_impact_color = (
            "#4ade80" if (not np.isnan(avg_impact_score) and avg_impact_score > 0) else "#f87171"
        )

        def build_kpi_card_html(label, value_text, subtext, accent_color):
            return (
                f"<div style='flex:1;background:{COLOR_CARD_BACKGROUND};border:1px solid {COLOR_BORDER};"
                f"border-radius:10px;padding:20px 24px;border-top:3px solid {accent_color};"
                f"box-shadow:0 4px 16px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.04);'>"
                f"<div style='font-family:monospace;font-size:9px;letter-spacing:0.13em;"
                f"text-transform:uppercase;color:{COLOR_TEXT_SECONDARY};margin-bottom:8px;'>{label}</div>"
                f"<div class='kpi-value' style='font-family:monospace;font-size:32px;font-weight:700;"
                f"color:{accent_color};line-height:1;letter-spacing:-0.02em;'>{value_text}</div>"
                f"<div style='font-size:10px;color:{COLOR_TEXT_SECONDARY};margin-top:6px;'>{subtext}</div>"
                f"</div>"
            )

        cards_html = "".join(
            [
                build_kpi_card_html(
                    "Facilities", str(num_facilities), "data centers in dataset", COLOR_TEXT_ACCENT
                ),
                build_kpi_card_html(
                    "Avg Impact Score",
                    f"{avg_impact_score:+.3f}" if not np.isnan(avg_impact_score) else "—",
                    "composite score across all ZIPs",
                    avg_impact_color,
                ),
            ]
        )
        return ui.HTML(f"<div style='display:flex;gap:16px;padding:4px 4px 0;'>{cards_html}</div>")

    @render.ui
    def atlas_timeseries_chart():
        """
        Cumulative area/line chart of data center openings by permit year,
        rendered as an inline SVG with vanilla JavaScript.
        """
        df = get_cleaned_impact_scores_df()
        permit_year_series = None

        if not df.empty and "First_Operation_Permit" in df.columns:
            permit_year_series = df[["First_Operation_Permit"]].copy()
            permit_year_series["year"] = pd.to_numeric(
                permit_year_series["First_Operation_Permit"], errors="coerce"
            )
        elif not data_centers_gdf.empty:
            for col in data_centers_gdf.columns:
                if any(k in col.lower() for k in ["permit", "operation", "year", "opened"]):
                    permit_year_series = pd.DataFrame(
                        {"year": pd.to_numeric(data_centers_gdf[col], errors="coerce")}
                    )
                    break

        if permit_year_series is None or permit_year_series["year"].dropna().empty:
            return render_empty_state(
                "No permit year data found", "Add First_Operation_Permit to impact CSV"
            )

        permit_year_series = permit_year_series.dropna(subset=["year"])
        permit_year_series["year"] = permit_year_series["year"].astype(int)
        cumulative_by_year = (
            permit_year_series["year"].value_counts().sort_index().cumsum().reset_index()
        )
        cumulative_by_year.columns = ["year", "cumulative_count"]

        chart_data_points = [
            {"year": int(r["year"]), "count": int(r["cumulative_count"])}
            for _, r in cumulative_by_year.iterrows()
        ]
        chart_data_json = json.dumps(chart_data_points)
        total_facilities = int(cumulative_by_year["cumulative_count"].max())

        html = f"""
<div style="font-family:monospace;padding:8px 4px;height:100%;">
  <div style="font-size:10px;color:{COLOR_TEXT_SECONDARY};margin-bottom:6px;padding:0 4px;">
    Cumulative facilities · first operation permit year
  </div>
  <svg id="ts-svg" width="100%" style="display:block;"></svg>
</div>
<script>
(function(){{
  const CHART_POINTS={chart_data_json}, TOTAL={total_facilities};
  const C_DARK="{COLOR_DARK_BACKGROUND}",C_BDR="{COLOR_BORDER}",
        C_SEC="{COLOR_TEXT_SECONDARY}",C_ACC="{COLOR_TEXT_ACCENT}",C_MAR="{COLOR_MAROON}";
  const PAD={{t:14,r:14,b:34,l:38}};
  const svg=document.getElementById("ts-svg"), NS="http://www.w3.org/2000/svg";
  const tip=document.createElement("div");
  tip.style.cssText="display:none;position:fixed;pointer-events:none;z-index:9999;background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:6px 10px;font-size:11px;color:#e6edf3;font-family:monospace;box-shadow:0 4px 16px rgba(0,0,0,0.6);";
  document.body.appendChild(tip);
  function draw(){{
    const W=svg.getBoundingClientRect().width||280,H=935;
    svg.setAttribute("height",H); svg.innerHTML="";
    const cw=W-PAD.l-PAD.r, ch=H-PAD.t-PAD.b;
    const minX=CHART_POINTS[0].year, maxX=CHART_POINTS[CHART_POINTS.length-1].year, spanX=maxX-minX||1;
    const toX=yr=>PAD.l+(yr-minX)/spanX*cw;
    const toY=v=>PAD.t+ch-(v/TOTAL)*ch;
    const bg=document.createElementNS(NS,"rect"); bg.setAttribute("width","100%"); bg.setAttribute("height",H); bg.setAttribute("fill",C_DARK); svg.appendChild(bg);
    [0,.25,.5,.75,1].forEach(f=>{{
      const v=Math.round(TOTAL*f),y=toY(v);
      const gl=document.createElementNS(NS,"line"); gl.setAttribute("x1",PAD.l); gl.setAttribute("x2",PAD.l+cw); gl.setAttribute("y1",y); gl.setAttribute("y2",y); gl.setAttribute("stroke",C_BDR); gl.setAttribute("stroke-width","0.5"); gl.setAttribute("stroke-dasharray","3,3"); svg.appendChild(gl);
      const tl=document.createElementNS(NS,"text"); tl.setAttribute("x",PAD.l-4); tl.setAttribute("y",y+3.5); tl.setAttribute("fill",C_SEC); tl.setAttribute("font-size","7.5"); tl.setAttribute("font-family","monospace"); tl.setAttribute("text-anchor","end"); tl.textContent=v; svg.appendChild(tl);
    }});
    let ap=`M ${{toX(CHART_POINTS[0].year)}} ${{toY(0)}} L ${{toX(CHART_POINTS[0].year)}} ${{toY(CHART_POINTS[0].count)}}`;
    CHART_POINTS.forEach((p,i)=>{{if(i>0)ap+=` L ${{toX(p.year)}} ${{toY(p.count)}}`;}});
    ap+=` L ${{toX(CHART_POINTS[CHART_POINTS.length-1].year)}} ${{toY(0)}} Z`;
    const area=document.createElementNS(NS,"path"); area.setAttribute("d",ap); area.setAttribute("fill",C_MAR); area.setAttribute("fill-opacity","0.2"); svg.appendChild(area);
    let lp=`M ${{toX(CHART_POINTS[0].year)}} ${{toY(CHART_POINTS[0].count)}}`;
    CHART_POINTS.forEach((p,i)=>{{if(i>0)lp+=` L ${{toX(p.year)}} ${{toY(p.count)}}`;}});
    const ln=document.createElementNS(NS,"path"); ln.setAttribute("d",lp); ln.setAttribute("fill","none"); ln.setAttribute("stroke",C_MAR); ln.setAttribute("stroke-width","2.2"); ln.setAttribute("stroke-linejoin","round"); ln.setAttribute("stroke-linecap","round"); svg.appendChild(ln);
    const step=Math.max(1,Math.floor(spanX/4));
    for(let yr=minX;yr<=maxX;yr+=step){{
      const tl=document.createElementNS(NS,"text"); tl.setAttribute("x",toX(yr)); tl.setAttribute("y",H-PAD.b+14); tl.setAttribute("fill",C_SEC); tl.setAttribute("font-size","7.5"); tl.setAttribute("font-family","monospace"); tl.setAttribute("text-anchor","middle"); tl.textContent=yr; svg.appendChild(tl);
    }}
    CHART_POINTS.forEach(p=>{{
      const cx=toX(p.year),cy=toY(p.count);
      const dot=document.createElementNS(NS,"circle"); dot.setAttribute("cx",cx); dot.setAttribute("cy",cy); dot.setAttribute("r","3"); dot.setAttribute("fill",C_ACC); dot.setAttribute("stroke",C_DARK); dot.setAttribute("stroke-width","1"); svg.appendChild(dot);
      const hit=document.createElementNS(NS,"circle"); hit.setAttribute("cx",cx); hit.setAttribute("cy",cy); hit.setAttribute("r","9"); hit.setAttribute("fill","transparent"); hit.style.cursor="default";
      hit.addEventListener("mousemove",e=>{{ tip.style.display="block"; tip.style.left=(e.clientX+8)+"px"; tip.style.top=(e.clientY+8)+"px"; tip.innerHTML=`<b style="color:${{C_ACC}}">${{p.year}}</b><br><span style="color:#8b949e">Cumulative: </span>${{p.count}} facilities`; }});
      hit.addEventListener("mouseleave",()=>{{tip.style.display="none";}}); svg.appendChild(hit);
    }});
    const last=CHART_POINTS[CHART_POINTS.length-1];
    const ann=document.createElementNS(NS,"text"); ann.setAttribute("x",toX(last.year)-5); ann.setAttribute("y",toY(last.count)-8); ann.setAttribute("fill",C_ACC); ann.setAttribute("font-size","9"); ann.setAttribute("font-family","monospace"); ann.setAttribute("text-anchor","end"); ann.setAttribute("font-weight","bold"); ann.textContent=TOTAL+" total"; svg.appendChild(ann);
  }}
  draw(); new ResizeObserver(draw).observe(svg);
}})();
</script>"""
        return ui.HTML(html)

    @render.ui
    def atlas_company_bar_chart():
        """
        Horizontal bar chart showing the number of unique data center locations
        per operator, sorted descending by count.
        Reads from datacenters_housing_merged.csv.
        """
        if not os.path.exists(DATACENTERS_HOUSING_CSV_PATH):
            return render_empty_state(
                "datacenters_housing_merged.csv not found",
                "Place the file in the Data/ folder",
            )

        datacenters_housing_df = pd.read_csv(DATACENTERS_HOUSING_CSV_PATH, dtype={"Zipcode": str})

        unique_dc_count_by_operator = (
            datacenters_housing_df.groupby("Operator")["Address"]
            .nunique()
            .reset_index(name="Data Center Count")
            .sort_values(
                "Data Center Count", ascending=False
            )  # ascending so largest bar ends up at top
        )

        chart_rows = [
            {"operator": str(row["Operator"]), "count": int(row["Data Center Count"])}
            for _, row in unique_dc_count_by_operator.iterrows()
        ]
        chart_rows_json = json.dumps(chart_rows)
        max_count = max(r["count"] for r in chart_rows) if chart_rows else 1

        html = f"""
<div style="font-family:monospace;padding:8px 4px;">
  <div style="font-size:10px;color:{COLOR_TEXT_SECONDARY};margin-bottom:8px;padding:0 4px;">
    Unique facility addresses per operator
  </div>
  <svg id="company-bar-svg" width="100%" style="display:block;"></svg>
</div>
<script>
(function(){{
  const ROWS={chart_rows_json}, MAX={max_count};
  const C_DARK="{COLOR_DARK_BACKGROUND}", C_BDR="{COLOR_BORDER}",
        C_SEC="{COLOR_TEXT_SECONDARY}",  C_PRI="{COLOR_TEXT_PRIMARY}",
        C_MAR="{COLOR_MAROON}",          C_ACC="{COLOR_TEXT_ACCENT}";
  const ROW_H=28, LBL_W=180, PAD_R=48, PAD_T=8, PAD_B=28;
  const NS="http://www.w3.org/2000/svg";
  const svg=document.getElementById("company-bar-svg");
  const totalH=ROWS.length*ROW_H+PAD_T+PAD_B;
  svg.setAttribute("height",totalH);
  const tip=document.createElement("div");
  tip.style.cssText="display:none;position:fixed;pointer-events:none;z-index:9999;background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:6px 10px;font-size:11px;color:#e6edf3;font-family:monospace;box-shadow:0 4px 16px rgba(0,0,0,0.6);";
  document.body.appendChild(tip);
  function W(){{return svg.getBoundingClientRect().width||500;}}
  function draw(){{
    const w=W(), barMax=w-LBL_W-PAD_R;
    svg.innerHTML="";
    const bg=document.createElementNS(NS,"rect"); bg.setAttribute("width","100%"); bg.setAttribute("height",totalH); bg.setAttribute("fill",C_DARK); svg.appendChild(bg);
    const nTicks=Math.min(MAX,5);
    for(let t=0;t<=nTicks;t++){{
      const tv=Math.round(MAX*t/nTicks), tx=LBL_W+(tv/MAX)*barMax;
      const gl=document.createElementNS(NS,"line"); gl.setAttribute("x1",tx); gl.setAttribute("x2",tx); gl.setAttribute("y1",PAD_T); gl.setAttribute("y2",totalH-PAD_B+4); gl.setAttribute("stroke",C_BDR); gl.setAttribute("stroke-width","0.5"); gl.setAttribute("stroke-dasharray","3,3"); svg.appendChild(gl);
      const tl=document.createElementNS(NS,"text"); tl.setAttribute("x",tx); tl.setAttribute("y",totalH-PAD_B+16); tl.setAttribute("fill",C_SEC); tl.setAttribute("font-size","8.5"); tl.setAttribute("font-family","monospace"); tl.setAttribute("text-anchor","middle"); tl.textContent=tv; svg.appendChild(tl);
    }}
    ROWS.forEach((row,i)=>{{
      const cy=PAD_T+i*ROW_H+ROW_H/2, bw=(row.count/MAX)*barMax;
      const rbg=document.createElementNS(NS,"rect"); rbg.setAttribute("x",0); rbg.setAttribute("y",PAD_T+i*ROW_H); rbg.setAttribute("width","100%"); rbg.setAttribute("height",ROW_H); rbg.setAttribute("fill",i%2===0?"#161b22":C_DARK); rbg.setAttribute("opacity","0.6"); svg.appendChild(rbg);
      const maxC=Math.floor((LBL_W-12)/6);
      const lbl=document.createElementNS(NS,"text"); lbl.setAttribute("x",LBL_W-8); lbl.setAttribute("y",cy+4); lbl.setAttribute("fill",C_PRI); lbl.setAttribute("font-size","9.5"); lbl.setAttribute("font-family","monospace"); lbl.setAttribute("text-anchor","end"); lbl.textContent=row.operator.length>maxC?row.operator.slice(0,maxC-1)+"…":row.operator; svg.appendChild(lbl);
      const bar=document.createElementNS(NS,"rect"); bar.setAttribute("x",LBL_W); bar.setAttribute("y",PAD_T+i*ROW_H+4); bar.setAttribute("width",bw); bar.setAttribute("height",ROW_H-8); bar.setAttribute("fill",C_MAR); bar.setAttribute("fill-opacity","0.85"); bar.setAttribute("stroke",C_ACC); bar.setAttribute("stroke-width","0.5"); bar.setAttribute("rx","2"); svg.appendChild(bar);
      const cnt=document.createElementNS(NS,"text"); cnt.setAttribute("x",LBL_W+bw+5); cnt.setAttribute("y",cy+4); cnt.setAttribute("fill",C_ACC); cnt.setAttribute("font-size","9"); cnt.setAttribute("font-family","monospace"); cnt.textContent=row.count; svg.appendChild(cnt);
      const hit=document.createElementNS(NS,"rect"); hit.setAttribute("x",0); hit.setAttribute("y",PAD_T+i*ROW_H); hit.setAttribute("width","100%"); hit.setAttribute("height",ROW_H); hit.setAttribute("fill","transparent"); hit.style.cursor="default";
      hit.addEventListener("mousemove",e=>{{ tip.style.display="block"; tip.style.left=(e.clientX+8)+"px"; tip.style.top=(e.clientY+8)+"px"; tip.innerHTML=`<b style="color:#e6edf3;">${{row.operator}}</b><br><span style="color:#8b949e;">Unique locations: </span><span style="color:${{C_ACC}};font-weight:600;">${{row.count}}</span>`; }});
      hit.addEventListener("mouseleave",()=>{{tip.style.display="none";}}); svg.appendChild(hit);
    }});
  }}
  draw(); new ResizeObserver(draw).observe(svg);
}})();
</script>
"""
        return ui.HTML(html)

    @render.ui
    def atlas_before_after_price_chart():
        """
        Dumbbell chart comparing a selected before/after metric for each facility,
        sorted ascending by percentage change.
        Toggle between Housing Price and Housing Cost Score via the dropdown.
        """
        df = get_cleaned_impact_scores_df()

        metric_choice = input.before_after_metric()

        if metric_choice == "price":
            before_col = "Housing_Avg_Price_Before_Permit"
            after_col = "Housing_Avg_Price_After_Permit"
            x_axis_label = "Average Housing Price"
            is_currency = True
            chart_description = (
                "The dumbbell plots compares average housing prices and housing costs around each data center before and "
                "after the first permit was issued. "
                "Each line connects the price in the year before the permit (blue) and the year after "
                "(red), allowing a visual comparison of price changes at each site. "
                "In most cases, the red point appears to the right of the blue point, indicating that "
                "housing prices increased after permitting. While the magnitude of these changes varies across "
                "locations, the overall pattern suggests a general upward trend."
            )
        else:
            before_col = "HC_Score_Before"
            after_col = "HC_Score_After"
            x_axis_label = "Housing Cost Score"
            is_currency = False
            chart_description = (
                "The dumbbell plot compares housing cost scores around each data center before and after "
                "the first permit was issued. "
                "Each line connects the score in the year before the permit (blue) and the year after "
                "(red). In many cases, the red point appears slightly to the right of the blue point, "
                "suggesting an increase in housing cost scores after permitting, while in other cases "
                "the change is slightly or even far negative."
            )

        required_columns = {before_col, after_col, "impact_score"}
        if df.empty or not required_columns.issubset(df.columns):
            return render_empty_state()

        plot_df = df.dropna(subset=list(required_columns)).copy()
        if plot_df.empty:
            return render_empty_state()

        sort_col = "Housing_Change" if metric_choice == "price" else "HC_Score_Change"
        plot_df = (
            plot_df.dropna(subset=[sort_col])
            .sort_values(sort_col, ascending=False)
            .reset_index(drop=True)
        )

        chart_rows = []
        for _, row in plot_df.iterrows():
            op = str(row.get("Operator", "Unknown"))[:26]
            zip_ = str(row.get("Zipcode", "")).strip()
            label = f"{op} ({zip_})" if zip_ else op
            pb = float(row[before_col])
            pa = float(row[after_col])
            imp = float(row["impact_score"])
            pct = (pa - pb) / (pb or 1) * 100
            chart_rows.append(
                {
                    "label": label,
                    "before": round(pb, 3),
                    "after": round(pa, 3),
                    "before_fmt": format_number_for_display(
                        pb, is_currency=is_currency, decimal_places=None if is_currency else 3
                    ),
                    "after_fmt": format_number_for_display(
                        pa, is_currency=is_currency, decimal_places=None if is_currency else 3
                    ),
                    "pct": round(pct, 1),
                    "impact": round(imp, 3),
                }
            )

        pct_up = sum(1 for r in chart_rows if r["after"] >= r["before"]) / len(chart_rows) * 100
        ann_col = "#4ade80" if pct_up >= 50 else "#f87171"
        rows_json = json.dumps(chart_rows)

        html = f"""
    <div style="display:flex;flex-direction:column;height:100%;font-family:monospace;">
    <div style="font-family:'DM Sans',sans-serif;font-size:12px;color:{COLOR_TEXT_SECONDARY};
        line-height:1.7;padding:6px 8px 4px;flex-shrink:0;">
        {chart_description}
    </div>
    <div style="font-size:11px;color:{ann_col};padding:4px 8px 6px;flex-shrink:0;">
        {pct_up:.0f}% of facilities saw {x_axis_label.lower()} rise after permit
        &nbsp;·&nbsp;
        <span style="color:#8b949e;">
        <span style="color:#60a5fa;">●</span> before &nbsp;
        <span style="color:#a3e635;">●</span> after &nbsp;·&nbsp; dot color = impact score
        </span>
    </div>
    <div style="flex:1;overflow-y:auto;min-height:0;">
        <svg id="dumbbell-svg" width="100%" style="display:block;"></svg>
    </div>

    </div>
    <script>
    (function(){{
    const ROWS={rows_json};
    const X_LABEL="{x_axis_label}";
    const C_DARK="#0d1117",C_BDR="#30363d",C_SEC="#8b949e",C_PRI="#e6edf3";
    const ROW_H=30,LBL_W=210,PAD_R=60,PAD_T=8,PAD_B=32;
    const svg=document.getElementById("dumbbell-svg");
    const tip=document.createElement("div");
    tip.style.cssText="display:none;position:fixed;pointer-events:none;z-index:9999;background:#1c2128;border:1px solid #30363d;border-radius:6px;padding:8px 12px;font-size:11px;color:#e6edf3;line-height:1.6;font-family:monospace;box-shadow:0 4px 16px rgba(0,0,0,0.6);";
    document.body.appendChild(tip);
    const NS="http://www.w3.org/2000/svg";
    const totalH=ROWS.length*ROW_H+PAD_T+PAD_B;
    svg.setAttribute("height",totalH);
    const allP=ROWS.flatMap(r=>[r.before,r.after]);
    const pMin=Math.min(...allP),pMax=Math.max(...allP),pRange=pMax-pMin||1;
    function W(){{return svg.getBoundingClientRect().width||600;}}
    function toX(p,w){{return LBL_W+(p-pMin)/pRange*(w-LBL_W-PAD_R);}}
    function iCol(imp){{
        if(imp>=0){{const t=Math.min(imp/2,1);return `rgb(${{Math.round(30+130*t)}},${{Math.round(180*t+40)}},${{Math.round(50*t)}})`;}}
        const t=Math.min(-imp/2,1);return `rgb(${{Math.round(220*t+35)}},${{Math.round(40*(1-t))}},${{Math.round(40*(1-t))}})`;
    }}
    function draw(){{
        const w=W(); svg.innerHTML="";
        const bg=document.createElementNS(NS,"rect"); bg.setAttribute("width","100%"); bg.setAttribute("height",totalH); bg.setAttribute("fill",C_DARK); svg.appendChild(bg);
        for(let t=0;t<=5;t++){{
        const v=pMin+pRange*t/5,x=toX(v,w);
        const gl=document.createElementNS(NS,"line"); gl.setAttribute("x1",x); gl.setAttribute("x2",x); gl.setAttribute("y1",PAD_T); gl.setAttribute("y2",totalH-PAD_B+6); gl.setAttribute("stroke",C_BDR); gl.setAttribute("stroke-width","0.5"); gl.setAttribute("stroke-dasharray","3,3"); svg.appendChild(gl);
        const lbl=v>=1000000?"$"+(v/1000000).toFixed(1)+"M":v>=1000?"$"+Math.round(v/1000)+"k":v>=1||v===0?v.toFixed(1):v.toFixed(3);
        const tl=document.createElementNS(NS,"text"); tl.setAttribute("x",x); tl.setAttribute("y",totalH-PAD_B+18); tl.setAttribute("fill",C_SEC); tl.setAttribute("font-size","8.5"); tl.setAttribute("font-family","monospace"); tl.setAttribute("text-anchor","middle"); tl.textContent=lbl; svg.appendChild(tl);
        }}
        const xl=document.createElementNS(NS,"text"); xl.setAttribute("x",LBL_W+(w-LBL_W-PAD_R)/2); xl.setAttribute("y",totalH-4); xl.setAttribute("fill",C_SEC); xl.setAttribute("font-size","9"); xl.setAttribute("font-family","monospace"); xl.setAttribute("text-anchor","middle"); xl.textContent=X_LABEL; svg.appendChild(xl);
        ROWS.forEach((row,i)=>{{
        const cy=PAD_T+i*ROW_H+ROW_H/2, bx=toX(row.before,w), ax=toX(row.after,w);
        const col=row.after>=row.before?"#4ade80":"#f87171", ic=iCol(row.impact);
        const rbg=document.createElementNS(NS,"rect"); rbg.setAttribute("x",0); rbg.setAttribute("y",PAD_T+i*ROW_H); rbg.setAttribute("width","100%"); rbg.setAttribute("height",ROW_H); rbg.setAttribute("fill",i%2===0?"#161b22":C_DARK); rbg.setAttribute("opacity","0.6"); svg.appendChild(rbg);
        const maxC=Math.floor((LBL_W-12)/5.5);
        const lbl=document.createElementNS(NS,"text"); lbl.setAttribute("x",LBL_W-8); lbl.setAttribute("y",cy+4); lbl.setAttribute("fill",C_PRI); lbl.setAttribute("font-size","9"); lbl.setAttribute("font-family","monospace"); lbl.setAttribute("text-anchor","end"); lbl.textContent=row.label.length>maxC?row.label.slice(0,maxC-1)+"…":row.label; svg.appendChild(lbl);
        const ln=document.createElementNS(NS,"line"); ln.setAttribute("x1",Math.min(bx,ax)); ln.setAttribute("x2",Math.max(bx,ax)); ln.setAttribute("y1",cy); ln.setAttribute("y2",cy); ln.setAttribute("stroke",col); ln.setAttribute("stroke-width","2.2"); ln.setAttribute("stroke-opacity","0.6"); ln.setAttribute("stroke-linecap","round"); svg.appendChild(ln);
        const bd=document.createElementNS(NS,"circle"); bd.setAttribute("cx",bx); bd.setAttribute("cy",cy); bd.setAttribute("r","5"); bd.setAttribute("fill","#60a5fa"); bd.setAttribute("stroke",C_DARK); bd.setAttribute("stroke-width","0.8"); svg.appendChild(bd);
        const ad=document.createElementNS(NS,"circle"); ad.setAttribute("cx",ax); ad.setAttribute("cy",cy); ad.setAttribute("r","6"); ad.setAttribute("fill",ic); ad.setAttribute("stroke",C_DARK); ad.setAttribute("stroke-width","0.8"); svg.appendChild(ad);
        const pt=document.createElementNS(NS,"text"); pt.setAttribute("x",Math.max(bx,ax)+6); pt.setAttribute("y",cy+4); pt.setAttribute("fill",col); pt.setAttribute("font-size","8.5"); pt.setAttribute("font-family","monospace"); pt.textContent=(row.pct>=0?"+":"")+row.pct.toFixed(1)+"%"; svg.appendChild(pt);
        const hit=document.createElementNS(NS,"rect"); hit.setAttribute("x",0); hit.setAttribute("y",PAD_T+i*ROW_H); hit.setAttribute("width","100%"); hit.setAttribute("height",ROW_H); hit.setAttribute("fill","transparent"); hit.style.cursor="default";
        hit.addEventListener("mousemove",e=>{{ tip.style.display="block"; tip.style.left=(e.clientX+8)+"px"; tip.style.top=(e.clientY+8)+"px"; tip.innerHTML=`<b style="color:#e6edf3;">${{row.label}}</b><br><span style="color:#60a5fa;">Before</span> ${{row.before_fmt}}&nbsp;&nbsp;<span style="color:${{ic}};">After</span> ${{row.after_fmt}}<br>Change <span style="color:${{col}};font-weight:600;">${{row.pct>=0?"+":""}}${{row.pct.toFixed(1)}}%</span>&nbsp;&nbsp;Impact <span style="color:${{ic}};font-weight:600;">${{row.impact>=0?"+":""}}${{row.impact.toFixed(3)}}</span>`; }});
        hit.addEventListener("mouseleave",()=>{{tip.style.display="none";}}); svg.appendChild(hit);
        }});
    }}
    draw(); new ResizeObserver(draw).observe(svg);
    }})();
    </script>
    """
        return ui.HTML(html)

    @render.ui
    def atlas_facility_directory_table():
        """
        HTML table listing every facility with key before/after metrics and impact scores,
        sorted by impact z-score descending.
        """
        df = get_cleaned_impact_scores_df()
        if df.empty:
            return render_empty_state()

        DESIRED_COLUMNS = [
            "Operator",
            "Address",
            "Zipcode",
            "CountyName",
            "First_Operation_Permit",
            "Housing_Avg_Price_Before_Permit",
            "Housing_Avg_Price_After_Permit",
            "Housing_Change",
            "HC_Score_Change",
            "impact_score",
            "impact_z_score",
        ]
        display_columns = [col for col in DESIRED_COLUMNS if col in df.columns] or list(df.columns)
        display_df = df[display_columns].copy()
        if "impact_z_score" in display_df.columns:
            display_df = display_df.sort_values("impact_z_score", ascending=False)

        COLUMN_LABELS = {
            "Operator": "Operator",
            "Address": "Address",
            "Zipcode": "ZIP",
            "CountyName": "County",
            "First_Operation_Permit": "Year",
            "Housing_Avg_Price_Before_Permit": "Price Before",
            "Housing_Avg_Price_After_Permit": "Price After",
            "Housing_Change": "Hsg Δ%",
            "HC_Score_Change": "HC Δ",
            "impact_score": "Impact",
            "impact_z_score": "Impact Z",
        }
        SCORE_COLS = {"impact_score", "impact_z_score", "HC_Score_Change", "Housing_Change"}
        PRICE_COLS = {"Housing_Avg_Price_Before_Permit", "Housing_Avg_Price_After_Permit"}

        def fmt_cell(value, col):
            if pd.isna(value):
                return f"<span style='color:{COLOR_BORDER};'>—</span>"
            if col in SCORE_COLS:
                v = float(value)
                c = "#4ade80" if v > 0 else "#f87171"
                return f"<span style='color:{c};font-weight:600;'>{v:+.3f}</span>"
            if col in PRICE_COLS:
                return f"<span style='color:{COLOR_TEXT_SECONDARY};'>{format_number_for_display(float(value), is_currency=True)}</span>"
            if col == "First_Operation_Permit":
                try:
                    return f"<span style='color:{COLOR_TEXT_SECONDARY};'>{int(float(value))}</span>"
                except:
                    return str(value)
            return f"<span style='color:{COLOR_TEXT_PRIMARY};'>{value}</span>"

        header_html = "".join(
            f"<th style='padding:8px 12px;color:{COLOR_TEXT_SECONDARY};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.11em;text-transform:uppercase;text-align:left;"
            f"white-space:nowrap;border-bottom:2px solid {COLOR_MAROON};position:sticky;top:0;"
            f"background:{COLOR_PANEL_BACKGROUND};z-index:1;'>{COLUMN_LABELS.get(c, c)}</th>"
            for c in display_columns
        )
        rows_html = ""
        for i, (_, row) in enumerate(display_df.iterrows()):
            bg = COLOR_CARD_BACKGROUND if i % 2 == 0 else COLOR_DARK_BACKGROUND
            cells = "".join(
                f"<td style='padding:7px 12px;border-bottom:1px solid {COLOR_BORDER};"
                f"font-family:monospace;font-size:11px;white-space:nowrap;'>{fmt_cell(row[c], c)}</td>"
                for c in display_columns
            )
            rows_html += (
                f"<tr style='background:{bg};transition:background 0.1s;'"
                f" onmouseover=\"this.style.background='#2d333b'\""
                f" onmouseout=\"this.style.background='{bg}'\">{cells}</tr>"
            )

        if not rows_html:
            return render_empty_state("No rows to display", "")

        return ui.HTML(f"""
        <div style="overflow:auto;max-height:520px;">
          <table style="width:100%;border-collapse:collapse;min-width:600px;">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """)

    # ── MAP OUTPUTS ───────────────────────────────────────────────────────────

    @render.ui
    def metric_variable_selector():
        """Render the variable dropdown for the currently selected metric group."""
        selected_group = input.metric_group()
        columns_by_group = {
            "zillow": ZILLOW_COLUMNS,
            "census": CENSUS_COLUMNS,
            "centers": DATA_CENTER_COLUMNS,
            "electricity": ELECTRICITY_COLUMNS,
            "water": WATER_SEWER_COLUMNS,
            "hhc": HOUSING_COST_BURDEN_COLUMNS,
        }
        available_columns = columns_by_group.get(selected_group, [])
        if not available_columns:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        default = available_columns[-1] if selected_group == "zillow" else available_columns[0]
        return ui.input_select(
            "metric", None, choices={c: c for c in available_columns}, selected=default
        )

    def get_selected_metric_column() -> str:
        """Safely read the currently selected metric column."""
        try:
            return input.metric()
        except:
            return ALL_NUMERIC_COLUMNS[0] if ALL_NUMERIC_COLUMNS else None

    def get_selected_metric_group() -> str:
        """Safely read the currently selected metric group."""
        try:
            return input.metric_group()
        except:
            return "census"

    @render.ui
    @reactive.event(
        input.metric_group,
        input.show_data_center_markers,
        input.show_illinois_boundary,
        input.show_cook_county_boundary,
        input.show_chicago_city_boundary,
        lambda: get_selected_metric_column(),
    )
    def choropleth_map():
        """
        Folium choropleth map with the selected variable, optional boundary overlays,
        and data center markers.
        """
        selected_metric = get_selected_metric_column()
        selected_group = get_selected_metric_group()

        if not selected_metric or selected_metric not in zip_polygons_gdf.columns:
            fallback = [c for c in ALL_NUMERIC_COLUMNS if c in zip_polygons_gdf.columns]
            if not fallback:
                return ui.HTML("")
            selected_metric = fallback[0]
            selected_group = COLUMN_TO_METRIC_GROUP.get(selected_metric, "census")

        folium_map = folium.Map(
            location=DEFAULT_MAP_CENTER, zoom_start=8, tiles="OpenStreetMap", prefer_canvas=True
        )

        choropleth_colormap, scale_min, scale_max = build_choropleth_colormap(
            zip_polygons_gdf[selected_metric], selected_metric, selected_group
        )

        def get_zip_polygon_style(feature):
            val = feature["properties"].get(selected_metric)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return {
                    "fillColor": "#1c2128",
                    "color": "#30363d",
                    "weight": 0.4,
                    "fillOpacity": 0.6,
                }
            return {
                "fillColor": choropleth_colormap(max(scale_min, min(scale_max, float(val)))),
                "color": "#21262d",
                "weight": 0.6,
                "fillOpacity": 0.75,
            }

        def get_zip_polygon_highlight_style(feature):
            return {"fillOpacity": 1.0, "weight": 2.2, "color": COLOR_TEXT_ACCENT}

        folium.GeoJson(
            ZIP_POLYGONS_GEOJSON,
            style_function=get_zip_polygon_style,
            highlight_function=get_zip_polygon_highlight_style,
            tooltip=folium.GeoJsonTooltip(
                fields=TOOLTIP_GEO_FIELDS + [selected_metric],
                aliases=TOOLTIP_GEO_ALIASES + [f"📊 {selected_metric}"],
                localize=True,
                sticky=True,
                style=(
                    f"background-color:{COLOR_CARD_BACKGROUND};color:{COLOR_TEXT_PRIMARY};"
                    "font-family:monospace;font-size:12px;padding:9px 13px;"
                    f"border-radius:7px;border:1px solid {COLOR_BORDER};"
                    "box-shadow:0 4px 16px rgba(0,0,0,0.55);min-width:220px;line-height:1.8;"
                ),
            ),
        ).add_to(folium_map)

        choropleth_colormap.add_to(folium_map)
        folium_map.get_root().html.add_child(
            folium.Element(f"""
            <style>
            .legend {{ background:{COLOR_CARD_BACKGROUND}!important;border:1px solid {COLOR_BORDER}!important;
            border-radius:8px!important;color:#ffffff!important;font-family:monospace!important;
            font-size:11px!important;padding:10px!important; }}
            .legend svg text {{ fill:#ffffff!important; }}
            .legend * {{ color:#ffffff!important; }}
            </style>
        """)
        )

        if input.show_illinois_boundary() and ILLINOIS_BOUNDARY_GEOJSON is not None:
            folium.GeoJson(
                ILLINOIS_BOUNDARY_GEOJSON,
                style_function=lambda f: {
                    "fillColor": "none",
                    "fillOpacity": 0.0,
                    "color": "#000000",
                    "weight": 2,
                },
                interactive=False,
            ).add_to(folium_map)

        if input.show_cook_county_boundary() and COOK_COUNTY_BOUNDARY_GEOJSON is not None:
            folium.GeoJson(
                COOK_COUNTY_BOUNDARY_GEOJSON,
                style_function=lambda f: {
                    "fillColor": "none",
                    "fillOpacity": 0.0,
                    "color": "#ffffff",
                    "weight": 2,
                },
                interactive=False,
            ).add_to(folium_map)

        if input.show_chicago_city_boundary() and CHICAGO_CITY_BOUNDARY_GEOJSON is not None:
            folium.GeoJson(
                CHICAGO_CITY_BOUNDARY_GEOJSON,
                style_function=lambda f: {
                    "fillColor": "none",
                    "fillOpacity": 0.0,
                    "color": "#ffffff",
                    "weight": 2,
                },
                interactive=False,
            ).add_to(folium_map)

        if input.show_data_center_markers():
            add_data_center_markers_to_map(folium_map)

        return ui.HTML(f'<div style="height:640px;width:100%;">{folium_map._repr_html_()}</div>')


# =============================================================================
# App entry point
# =============================================================================
static_assets_dir = os.path.join(os.path.dirname(__file__), "Data")
app = App(app_ui, server, static_assets=static_assets_dir)
