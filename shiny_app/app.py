from shiny import App, ui, render, reactive
import folium
import branca.colormap as cm
import geopandas as gpd
import fiona
import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import io, base64
from scipy import stats as scipy_stats

# To run: shiny run --reload app.py
# cd shiny_app -> rsconnect deploy shiny .

# =============================================================================
# BRAND & DESIGN TOKENS
# =============================================================================
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

# =============================================================================
# COLORBLIND-FRIENDLY COLORMAPS
# =============================================================================
GROUP_CMAPS = {
    "zillow":      "viridis",
    "census":      "cividis",
    "centers":     "plasma",
    "electricity": "magma",
    "water":       "YlGnBu",
}

def _mpl_to_hex_stops(cmap_name: str, n: int = 9) -> list:
    cmap = plt.get_cmap(cmap_name)
    return [mcolors.to_hex(cmap(i / (n - 1))) for i in range(n)]

def make_colormap(values, metric: str, group: str):
    clean = values.dropna()
    if clean.empty:
        colormap = cm.LinearColormap(["#1a1a2e", "#f0a500"], vmin=0, vmax=1, caption=metric)
        return colormap, 0.0, 1.0

    col_min = float(np.percentile(clean, 2))
    col_max = float(np.percentile(clean, 98))
    if col_min == col_max:
        col_min, col_max = float(clean.min()), float(clean.max())
    if col_min == col_max:
        col_max = col_min + 1

    colors   = _mpl_to_hex_stops(GROUP_CMAPS.get(group, "viridis"), 9)
    colormap = cm.LinearColormap(colors, vmin=col_min, vmax=col_max, caption=metric)
    return colormap, col_min, col_max


# =============================================================================
# COLUMN DEFINITIONS
# =============================================================================
ZILLOW_YEARS         = [2010, 2019, 2024]
ZILLOW_COLS_FRIENDLY = [f"Median Home Value ({y})" for y in ZILLOW_YEARS]

CENSUS_COLS_FRIENDLY = [
    "Median Household Income",
    "Population Density (per sq km)",
    "Broadband Adoption Rate (%)",
    "Poverty Rate (%)",
    "Unemployment Rate (%)",
    "Renter-Occupied Share (%)",
]

DC_COLS_FRIENDLY = [
    "Total Data Centers",
    "Data Centers per 100,000 Residents",
]

ELEC_COLS_FRIENDLY = [
    "Electricity: % Paying Above $50/month",
    "Electricity: % Paying Above $150/month",
    "Electricity: % Paying $250+/month",
]

WATER_COLS_FRIENDLY = [
    "Water & Sewer: % Paying Above $125/year",
    "Water & Sewer: % Paying Above $500/year",
    "Water & Sewer: % Paying $1,000+/year",
]

OPTIONAL_COLS = ["Total Population", "Land Area (sq meters)"]

METRIC_GROUP_CHOICES = {}


# =============================================================================
# LOAD & PRE-PROCESS DATA  <- all heavy lifting happens once at startup
# =============================================================================
def load_data():
    app_dir      = os.path.dirname(os.path.abspath(__file__))
    cities_path  = os.path.join(app_dir, "Data", "Chicago.gpkg")
    centers_path = os.path.join(app_dir, "Data", "ChicagoDataCenters.gpkg")
    cities       = gpd.read_file(cities_path)
    centers      = gpd.read_file(centers_path)
    return cities, centers, cities_path

cities_gdf, centers_gdf, cities_path = load_data()
cities_gdf  = cities_gdf.to_crs(epsg=4326)
centers_gdf = centers_gdf.to_crs(epsg=4326)

# Simplify geometries once
cities_gdf.geometry  = cities_gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)
centers_gdf.geometry = centers_gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)

# Pre-compute map centre once
_centroids  = cities_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
MAP_CENTER  = [float(_centroids.y.mean()), float(_centroids.x.mean())]

# Pre-build tooltip field lists once
TT_FIELDS_BASE, TT_ALIASES_BASE = [], []
for col, alias in [("Zip Code", "📍 ZIP"), ("City", "🏙️ City"),
                   ("Community", "🏘️ Community"), ("County", "🗺️ County"),
                   ("State", "📌 State")]:
    if col in cities_gdf.columns:
        TT_FIELDS_BASE.append(col)
        TT_ALIASES_BASE.append(alias)

with fiona.open(cities_path) as src:
    records = [feat["properties"] for feat in src]
cities_df = pd.DataFrame(records)

def _present(cols):
    return [c for c in cols if c in cities_df.columns]

ZILLOW_COLS  = _present(ZILLOW_COLS_FRIENDLY)
CENSUS_COLS  = _present(CENSUS_COLS_FRIENDLY)
DC_COLS      = _present(DC_COLS_FRIENDLY)
ELEC_COLS    = _present(ELEC_COLS_FRIENDLY)
WATER_COLS   = _present(WATER_COLS_FRIENDLY)
OPT_COLS     = _present(OPTIONAL_COLS)

ALL_NUMERIC = ZILLOW_COLS + CENSUS_COLS + DC_COLS + ELEC_COLS + WATER_COLS + OPT_COLS

# Coerce ALL numerics once at load time
for col in ALL_NUMERIC:
    if col in cities_df.columns:
        cities_df[col]  = pd.to_numeric(cities_df[col],  errors="coerce")
    if col in cities_gdf.columns:
        cities_gdf[col] = pd.to_numeric(cities_gdf[col], errors="coerce")

COL_GROUP = {}
for c in ZILLOW_COLS:  COL_GROUP[c] = "zillow"
for c in CENSUS_COLS:  COL_GROUP[c] = "census"
for c in DC_COLS:      COL_GROUP[c] = "centers"
for c in ELEC_COLS:    COL_GROUP[c] = "electricity"
for c in WATER_COLS:   COL_GROUP[c] = "water"
for c in OPT_COLS:     COL_GROUP[c] = "census"

# Map group key -> list of columns (used by Relationships & Regressions)
GROUP_COLS = {
    "zillow":      ZILLOW_COLS,
    "census":      CENSUS_COLS,
    "centers":     DC_COLS,
    "electricity": ELEC_COLS,
    "water":       WATER_COLS,
}

if ZILLOW_COLS:  METRIC_GROUP_CHOICES["zillow"]      = "🏠  Home Values"
if CENSUS_COLS:  METRIC_GROUP_CHOICES["census"]      = "👥  Demographics"
if DC_COLS:      METRIC_GROUP_CHOICES["centers"]     = "🏢  Data Centers"
if ELEC_COLS:    METRIC_GROUP_CHOICES["electricity"] = "⚡  Electricity"
if WATER_COLS:   METRIC_GROUP_CHOICES["water"]       = "💧  Water & Sewer"

# Pre-serialize GeoJSON once
CITIES_GEOJSON = cities_gdf.__geo_interface__


# =============================================================================
# HELPERS
# =============================================================================
def dc_tooltip_html(row):
    facility = str(row.get("Facility Name", row.get("facility", "")) or "").strip()
    zip_code = str(row.get("Data Center ZIP Code", row.get("zip_code", "—")) or "—").strip()
    operator = str(row.get("Operator", row.get("operator", "—")) or "—").strip()
    city     = str(row.get("City", row.get("city_in_de", "—")) or "—").strip()
    for v in ("", "nan", "None"):
        if zip_code == v: zip_code = "—"
        if operator == v: operator = "—"
        if city     == v: city     = "—"
    header = (f"<b>🏢 {facility}</b>"
              if facility and facility not in ("nan", "None", "")
              else "<b>🏢 Data Center</b>")
    return (
        f"<div style='font-family:monospace;line-height:1.8;'>"
        f"{header}<br>"
        f"<span style='color:#8b949e;'>City&nbsp;&nbsp;&nbsp;&nbsp;</span>{city}<br>"
        f"<span style='color:#8b949e;'>ZIP&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>{zip_code}<br>"
        f"<span style='color:#8b949e;'>Operator&nbsp;</span>{operator}"
        f"</div>"
    )

def fig_to_html(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=130)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return f'<img src="data:image/png;base64,{b64}" style="width:100%;border-radius:6px;">'

def setup_ax(ax, fig):
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT_SEC, labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)
    ax.grid(True, color=BORDER, linewidth=0.4, linestyle="--", alpha=0.6)

def _build_dc_markers(m):
    """Add data center markers to a folium map."""
    for _, row in centers_gdf.iterrows():
        geom = row.geometry
        if geom.geom_type == "MultiPoint":
            geom = list(geom.geoms)[0]
        folium.Marker(
            location=[geom.y, geom.x],
            icon=folium.Icon(color="white", icon_color=MAROON, icon="building", prefix="fa"),
            tooltip=folium.Tooltip(
                dc_tooltip_html(row),
                sticky=True,
                style=(
                    f"background-color:{CARD_BG};"
                    f"color:{TEXT_PRI};"
                    "font-family:monospace;"
                    "font-size:12px;"
                    "padding:10px 14px;"
                    "border-radius:7px;"
                    f"border:1px solid {BORDER};"
                ),
            ),
        ).add_to(m)


# =============================================================================
# CSS
# =============================================================================
CUSTOM_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

html, body {{
  font-family: 'DM Sans', sans-serif;
  background: {DARK_BG} !important;
  color: {TEXT_PRI} !important;
  font-size: 14px;
}}

/* Navbar */
.navbar {{
  background: linear-gradient(135deg, {MAROON_DARK} 0%, {MAROON} 55%, {MAROON_MID} 100%) !important;
  border-bottom: 1px solid {MAROON_DARK} !important;
  box-shadow: 0 2px 24px rgba(0,0,0,0.7);
  padding: 0 48px !important;
  min-height: 52px !important;
}}

/* Bottom figurative bar */
#bottom-bar {{
  position: fixed;
  bottom: 0; left: 0; right: 0;
  z-index: 1000;
  height: 42px;
  background: linear-gradient(135deg, {MAROON_DARK} 0%, {MAROON} 55%, {MAROON_MID} 100%);
  border-top: 1px solid {MAROON_DARK};
  box-shadow: 0 -2px 24px rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  padding: 0 48px;
  gap: 32px;
}}
#bottom-bar span {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 12px;
  color: rgba(255,255,255,0.78);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  cursor: default;
}}

/* Push page content up so bottom bar doesn't overlap */
body {{ padding-bottom: 42px !important; }}
.navbar-brand {{
  font-family: 'DM Serif Display', serif !important;
  font-size: 19px !important;
  letter-spacing: 0.02em;
  color: #fff !important;
}}
.navbar-nav .nav-link {{
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
  font-size: 12px !important;
  color: rgba(255,255,255,0.78) !important;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0 18px !important;
  transition: color 0.18s;
}}
.navbar-nav .nav-link:hover,
.navbar-nav .nav-link.active {{
  color: #fff !important;
  border-bottom: 2px solid {TEXT_ACC};
}}
.uchicago-logo-nav {{ height: 36px; display: block; margin: 0 6px; }}

/* Sidebar */
.sidebar,
.bslib-sidebar-layout > .sidebar,
.bslib-sidebar-layout > .sidebar > .sidebar-content,
aside.sidebar {{
  background: {PANEL_BG} !important;
  border-right: 1px solid {BORDER} !important;
  color: {TEXT_PRI} !important;
  padding: 20px 18px !important;
}}
.sidebar-section-title {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: {TEXT_SEC};
  margin: 16px 0 6px;
}}
.sidebar label, .sidebar .control-label,
.sidebar .form-check-label, .sidebar p, .sidebar strong {{
  color: {TEXT_PRI} !important;
  font-size: 13px;
}}
.sidebar h4 {{
  font-family: 'DM Serif Display', serif !important;
  font-size: 20px !important;
  color: {TEXT_ACC} !important;
  margin: 0 0 4px;
  letter-spacing: 0.01em;
}}
.sidebar .form-select, .sidebar .form-control, .sidebar select {{
  background: {CARD_BG} !important;
  color: {TEXT_PRI} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px !important;
  font-size: 13px;
  transition: border-color 0.2s;
}}
.sidebar .form-select:focus {{
  border-color: {MAROON} !important;
  box-shadow: 0 0 0 2px rgba(128,0,0,0.22) !important;
}}
.sidebar .selectize-input, .sidebar .selectize-input input {{
  background: {CARD_BG} !important;
  color: {TEXT_PRI} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px !important;
  box-shadow: none !important;
  font-size: 13px;
}}
.sidebar .selectize-dropdown, .sidebar .selectize-dropdown .option {{
  background: {PANEL_BG} !important;
  color: {TEXT_PRI} !important;
  border: 1px solid {BORDER} !important;
  font-size: 13px;
}}
.sidebar .selectize-dropdown .option:hover,
.sidebar .selectize-dropdown .option.active {{
  background: {MAROON} !important; color: #fff !important;
}}
.sidebar .form-check-input {{
  border-color: {BORDER} !important; background: {CARD_BG} !important;
}}
.sidebar .form-check-input:checked {{
  background: {MAROON} !important; border-color: {MAROON} !important;
}}
.sidebar .form-check-input:focus {{
  box-shadow: 0 0 0 2px rgba(128,0,0,0.25) !important;
}}
.sidebar hr {{
  border: none; border-top: 1px solid {BORDER} !important;
  margin: 16px 0; opacity: 1;
}}
.source-note {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px; color: {TEXT_SEC}; line-height: 1.65;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid {BORDER};
}}

/* Cards */
.card {{
  background: {CARD_BG} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  overflow: hidden;
  box-shadow: 0 6px 28px rgba(0,0,0,0.45);
}}
.card-header {{
  background: linear-gradient(90deg, {MAROON_DARK} 0%, {MAROON} 100%) !important;
  color: #fff !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 10px !important; font-weight: 500 !important;
  letter-spacing: 0.12em !important; text-transform: uppercase !important;
  padding: 10px 16px !important; border-bottom: none !important;
}}

/* Global backgrounds */
body, .bslib-page-sidebar, .bslib-sidebar-layout {{
  background: {DARK_BG} !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {DARK_BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {MAROON}; }}
"""


# =============================================================================
# UI
# =============================================================================
app_ui = ui.page_navbar(

    # MAP
    ui.nav_panel(
        "Map",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Explore"),
                ui.div("METRIC GROUP", class_="sidebar-section-title"),
                ui.input_select(
                    "metric_group", None,
                    choices=METRIC_GROUP_CHOICES,
                    selected=list(METRIC_GROUP_CHOICES.keys())[0],
                ),
                ui.div("VARIABLE", class_="sidebar-section-title"),
                ui.output_ui("metric_selector"),
                ui.hr(),
                ui.input_checkbox("show_centers", "Show data center pins", value=True),
                ui.hr(),
                ui.div(
                    "Sources: Zillow (2010, 2019, 2024) · ACS 2022 · "
                    "NHGIS 2022 · Manual DC inventory",
                    class_="source-note"
                ),
                style=f"background:{PANEL_BG}; min-width:225px;",
            ),
            ui.card(
                ui.card_header("Chicago Metro — ZIP Code Choropleth"),
                ui.output_ui("map_plot"),
            ),
        ),
    ),

    # RELATIONSHIPS
    ui.nav_panel(
        "Relationships",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Variables"),
                ui.div("FILTER BY GROUP (OPTIONAL)", class_="sidebar-section-title"),
                ui.input_select(
                    "rel_metric_group", None,
                    choices={"all": "— All Variables —", **METRIC_GROUP_CHOICES},
                    selected="all",
                ),
                ui.div("X AXIS", class_="sidebar-section-title"),
                ui.output_ui("rel_x_selector"),
                ui.div("Y AXIS", class_="sidebar-section-title"),
                ui.output_ui("rel_y_selector"),
                ui.hr(),
                ui.input_checkbox("color_by_dc", "Highlight ZIPs with data centers", value=False),
                ui.hr(),
                ui.div(
                    "Each point is one ZIP code. Dashed line = linear trend.",
                    class_="source-note"
                ),
                style=f"background:{PANEL_BG}; min-width:225px;",
            ),
            ui.layout_columns(
                ui.card(ui.card_header("Scatter Plot"),          ui.output_ui("scatter_plot")),
                ui.card(ui.card_header("Distributions"),         ui.output_ui("dist_plot")),
                ui.card(ui.card_header("Correlation & Summary"), ui.output_ui("summary_stats")),
                col_widths=(12, 12, 12),
            ),
        ),
    ),

    # REGRESSIONS (renamed from Analysis)
    ui.nav_panel(
        "Regressions",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Regression"),
                ui.div("FILTER BY GROUP (OPTIONAL)", class_="sidebar-section-title"),
                ui.input_select(
                    "reg_metric_group", None,
                    choices={"all": "— All Variables —", **METRIC_GROUP_CHOICES},
                    selected="all",
                ),
                ui.div("DEPENDENT VARIABLE (Y)", class_="sidebar-section-title"),
                ui.output_ui("reg_y_selector"),
                ui.div("REGRESSORS (X)", class_="sidebar-section-title"),
                ui.output_ui("reg_x_selector"),
                ui.hr(),
                ui.input_checkbox("reg_intercept", "Include intercept", value=True),
                ui.hr(),
                ui.div(
                    "OLS regression across all ZIP codes. "
                    "Select one or more regressors.",
                    class_="source-note"
                ),
                style=f"background:{PANEL_BG}; min-width:225px;",
            ),
            ui.layout_columns(
                ui.card(ui.card_header("Regression Results"), ui.output_ui("reg_summary")),
                ui.card(ui.card_header("Fitted vs Actual"),   ui.output_ui("reg_fit_plot")),
                ui.card(ui.card_header("Residuals"),          ui.output_ui("reg_resid_plot")),
                col_widths=(12, 6, 6),
            ),
        ),
    ),

    ui.nav_spacer(),
    ui.nav_control(ui.tags.img(src="uchicago_logo.png", class_="uchicago-logo-nav")),

    header=ui.tags.head(
        ui.tags.style(CUSTOM_CSS),
        ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
        ui.tags.link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        ui.tags.script("""
            document.addEventListener('DOMContentLoaded', function() {
                var bar = document.createElement('div');
                bar.id = 'bottom-bar';
                bar.innerHTML = '<span>— University of Chicago —</span>';
                bar.style.transform = 'translateY(100%)';
                bar.style.transition = 'transform 0.3s ease';
                document.body.appendChild(bar);
                window.addEventListener('scroll', function() {
                    if (window.scrollY > 40) {
                        bar.style.transform = 'translateY(0)';
                    } else {
                        bar.style.transform = 'translateY(100%)';
                    }
                });
            });
        """),
    ),

    title=ui.tags.span(
        "Chicago Data Center Dashboard",
        style="font-family:'DM Serif Display',serif; font-size:18px; "
              "color:#fff; letter-spacing:0.02em;"
    ),
    bg=MAROON,
    inverse=True,
)


# =============================================================================
# SERVER
# =============================================================================
def server(input, output, session):

    @render.ui
    def metric_selector():
        group = input.metric_group()
        col_map = {
            "zillow":      ZILLOW_COLS,
            "census":      CENSUS_COLS,
            "centers":     DC_COLS,
            "electricity": ELEC_COLS,
            "water":       WATER_COLS,
        }
        cols = col_map.get(group, [])
        if not cols:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        return ui.input_select(
            "metric", None,
            choices={c: c for c in cols},
            selected=cols[-1] if group == "zillow" else cols[0],
        )

    def _resolved_metric():
        try:   return input.metric()
        except: return ALL_NUMERIC[0] if ALL_NUMERIC else None

    def _current_group():
        try:   return input.metric_group()
        except: return "census"

    # ── Relationships: dynamic X / Y selectors ────────────────────────────────
    @render.ui
    def rel_x_selector():
        group = input.rel_metric_group()
        cols  = ALL_NUMERIC if group == "all" else GROUP_COLS.get(group, ALL_NUMERIC)
        if not cols:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        return ui.input_select(
            "x_var", None,
            choices={c: c for c in cols},
            selected=cols[0],
        )

    @render.ui
    def rel_y_selector():
        group = input.rel_metric_group()
        cols  = ALL_NUMERIC if group == "all" else GROUP_COLS.get(group, ALL_NUMERIC)
        if not cols:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        return ui.input_select(
            "y_var", None,
            choices={c: c for c in cols},
            selected=cols[1] if len(cols) > 1 else cols[0],
        )

    # ── Regressions: dynamic Y and X selectors ────────────────────────────────
    @render.ui
    def reg_y_selector():
        group = input.reg_metric_group()
        cols  = ALL_NUMERIC if group == "all" else GROUP_COLS.get(group, ALL_NUMERIC)
        if not cols:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        return ui.input_select(
            "reg_y", None,
            choices={c: c for c in cols},
            selected=cols[0],
        )

    @render.ui
    def reg_x_selector():
        group = input.reg_metric_group()
        cols  = ALL_NUMERIC if group == "all" else GROUP_COLS.get(group, ALL_NUMERIC)
        if not cols:
            return ui.p("No columns available.", style="color:#f87171;font-size:12px;")
        return ui.input_selectize(
            "reg_x", None,
            choices={c: c for c in cols},
            selected=[cols[1]] if len(cols) > 1 else [],
            multiple=True,
        )

    # ── MAP ───────────────────────────────────────────────────────────────────
    @render.ui
    @reactive.event(input.metric_group, input.show_centers,
                    lambda: _resolved_metric())
    def map_plot():
        metric = _resolved_metric()
        group  = _current_group()

        if not metric or metric not in cities_gdf.columns:
            fallback = [c for c in ALL_NUMERIC if c in cities_gdf.columns]
            if not fallback:
                return ui.HTML("")
            metric = fallback[0]
            group  = COL_GROUP.get(metric, "census")

        m = folium.Map(
            location=MAP_CENTER,
            zoom_start=8,
            tiles="CartoDB positron",
            prefer_canvas=True,
        )

        colormap, col_min, col_max = make_colormap(cities_gdf[metric], metric, group)

        tt_fields   = TT_FIELDS_BASE   + [metric]
        tt_aliases  = TT_ALIASES_BASE  + [f"📊 {metric}"]

        def style_fn(feature):
            val = feature["properties"].get(metric)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return {"fillColor": "#21262d", "color": "#30363d",
                        "weight": 0.4, "fillOpacity": 0.45}
            clamped = max(col_min, min(col_max, float(val)))
            return {
                "fillColor":   colormap(clamped),
                "color":       "#0d1117",
                "weight":      0.6,
                "fillOpacity": 0.83,
            }

        def highlight_fn(feature):
            return {"fillOpacity": 1.0, "weight": 2.2, "color": TEXT_ACC}

        folium.GeoJson(
            CITIES_GEOJSON,
            style_function=style_fn,
            highlight_function=highlight_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=tt_fields, aliases=tt_aliases,
                localize=True, sticky=True,
                style=(
                    f"background-color:{CARD_BG};"
                    f"color:{TEXT_PRI};"
                    "font-family:monospace;"
                    "font-size:12px;"
                    "padding:9px 13px;"
                    "border-radius:7px;"
                    f"border:1px solid {BORDER};"
                    "box-shadow:0 4px 16px rgba(0,0,0,0.55);"
                    "min-width:220px;"
                    "line-height:1.8;"
                ),
            ),
        ).add_to(m)

        colormap.add_to(m)

        m.get_root().html.add_child(folium.Element(f"""
            <style>
            .legend {{
              background: {CARD_BG} !important;
              border: 1px solid {BORDER} !important;
              border-radius: 8px !important;
              color: {TEXT_PRI} !important;
              font-family: monospace !important;
              font-size: 11px !important;
              padding: 10px !important;
            }}
            </style>
        """))

        if input.show_centers():
            _build_dc_markers(m)

        return ui.HTML(f'<div style="height:640px;width:100%;">{m._repr_html_()}</div>')

    # ── SCATTER & DISTRIBUTIONS ───────────────────────────────────────────────
    @reactive.Calc
    def plot_data():
        try:
            x_var = input.x_var()
            y_var = input.y_var()
        except:
            return pd.DataFrame(), "", ""
        raw   = [x_var, y_var, "Zip Code", "Total Data Centers"]
        cols  = list(dict.fromkeys([c for c in raw if c in cities_df.columns]))
        df    = cities_df[cols].copy().reset_index(drop=True)
        return df.dropna(subset=[x_var, y_var]).reset_index(drop=True), x_var, y_var

    @render.ui
    def scatter_plot():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML("<p style='color:#f87171;padding:16px;'>No data available.</p>")

        x = df[x_var].to_numpy().astype(float)
        y = df[y_var].to_numpy().astype(float)

        fig, ax = plt.subplots(figsize=(9, 5))
        setup_ax(ax, fig)

        color_by = input.color_by_dc() and "Total Data Centers" in df.columns
        if color_by:
            has_dc = pd.to_numeric(df["Total Data Centers"], errors="coerce").fillna(0).to_numpy() > 0
            ax.scatter(x[~has_dc], y[~has_dc],
                       color="#4895ef", alpha=0.65, edgecolors=DARK_BG,
                       linewidths=0.4, s=52, label="No data center", zorder=3)
            ax.scatter(x[has_dc], y[has_dc],
                       color=TEXT_ACC, alpha=0.95, edgecolors=TEXT_PRI,
                       linewidths=0.6, s=95, label="Has data center",
                       zorder=4, marker="D")
            ax.legend(facecolor=CARD_BG, edgecolor=BORDER,
                      labelcolor=TEXT_PRI, fontsize=9, framealpha=0.9)
        else:
            sc = ax.scatter(x, y, c=y, cmap="cividis", alpha=0.75,
                            edgecolors=DARK_BG, linewidths=0.3, s=52, zorder=3)
            cbar = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01)
            cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
            cbar.outline.set_edgecolor(BORDER)

        try:
            coef = np.polyfit(x, y, 1)
            xl   = np.linspace(x.min(), x.max(), 200)
            ax.plot(xl, np.poly1d(coef)(xl), color=TEXT_ACC,
                    linewidth=1.8, linestyle="--", alpha=0.85, zorder=5)
        except Exception:
            pass

        corr = float(np.corrcoef(x, y)[0, 1])
        ax.annotate(
            f"r = {corr:.3f}",
            xy=(0.97, 0.05), xycoords="axes fraction", ha="right",
            color=TEXT_ACC, fontsize=10, fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=DARK_BG,
                      edgecolor=BORDER, alpha=0.92)
        )
        ax.set_xlabel(x_var, color=TEXT_SEC, fontsize=10, labelpad=8)
        ax.set_ylabel(y_var, color=TEXT_SEC, fontsize=10, labelpad=8)
        plt.tight_layout()
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def dist_plot():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML("<p style='color:#f87171;padding:16px;'>No data available.</p>")

        fig, axes = plt.subplots(1, 2, figsize=(9, 4))
        fig.patch.set_facecolor(DARK_BG)

        cmaps_dist = ["plasma", "viridis"]
        for ax, var, cname in zip(axes, [x_var, y_var], cmaps_dist):
            vals = df[var].dropna().to_numpy().astype(float)
            setup_ax(ax, fig)
            n, bins, patches = ax.hist(vals, bins=22, alpha=0, edgecolor="none")
            cmap_d = plt.get_cmap(cname)
            norm_d = mcolors.Normalize(vmin=bins[0], vmax=bins[-1])
            for patch, left in zip(patches, bins[:-1]):
                patch.set_facecolor(cmap_d(norm_d(left)))
                patch.set_alpha(0.88)
            mean_v = float(vals.mean())
            ax.axvline(mean_v, color=TEXT_ACC, linewidth=1.8, linestyle="--",
                       label=f"μ = {mean_v:,.1f}", zorder=5)
            ax.set_title(var[:36], color=TEXT_PRI, fontsize=9,
                         fontfamily="monospace", pad=8)
            ax.tick_params(colors=TEXT_SEC, labelsize=8)
            ax.legend(facecolor=CARD_BG, edgecolor=BORDER,
                      labelcolor=TEXT_PRI, fontsize=8)

        plt.tight_layout(pad=1.5)
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def summary_stats():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML("<p style='color:#f87171;padding:16px;'>No data available.</p>")

        x    = df[x_var].to_numpy().astype(float)
        y    = df[y_var].to_numpy().astype(float)
        corr = float(np.corrcoef(x, y)[0, 1])
        n    = len(df)

        corr_color = "#4ade80" if abs(corr) > 0.5 else ("#facc15" if abs(corr) > 0.25 else "#f87171")
        corr_label = "Strong" if abs(corr) > 0.5 else ("Moderate" if abs(corr) > 0.25 else "Weak")
        direction  = "positive" if corr > 0 else "negative"

        def row(label, xv, yv):
            return (
                f"<tr style='border-bottom:1px solid {BORDER};'>"
                f"<td style='padding:7px 10px;color:{TEXT_SEC};"
                f"font-family:monospace;font-size:11px;'>{label}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_PRI};"
                f"text-align:right;font-family:monospace;font-size:11px;'>{xv}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_PRI};"
                f"text-align:right;font-family:monospace;font-size:11px;'>{yv}</td>"
                f"</tr>"
            )

        rows = "".join([
            row("N (ZIP codes)", n, n),
            row("Mean",   f"{x.mean():,.2f}",     f"{y.mean():,.2f}"),
            row("Median", f"{np.median(x):,.2f}", f"{np.median(y):,.2f}"),
            row("Std Dev",f"{x.std():,.2f}",      f"{y.std():,.2f}"),
            row("Min",    f"{x.min():,.2f}",       f"{y.min():,.2f}"),
            row("Max",    f"{x.max():,.2f}",       f"{y.max():,.2f}"),
        ])

        html = f"""
        <div style="background:{DARK_BG};padding:16px;border-radius:8px;
                    font-family:'DM Sans',sans-serif;">
          <div style="margin-bottom:16px;padding:14px 16px;background:{CARD_BG};
                      border-radius:8px;border-left:3px solid {MAROON};">
            <div style="font-family:monospace;font-size:9px;color:{TEXT_SEC};
                        letter-spacing:0.12em;text-transform:uppercase;margin-bottom:4px;">
              Pearson Correlation
            </div>
            <div style="font-size:28px;font-weight:700;color:{corr_color};
                        font-family:'IBM Plex Mono',monospace;line-height:1;">
              r = {corr:.4f}
            </div>
            <div style="font-size:11px;color:{TEXT_SEC};margin-top:5px;">
              {corr_label} {direction} relationship &nbsp;·&nbsp; {n} ZIP codes
            </div>
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid {MAROON};">
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:left;
                           font-size:9px;font-family:monospace;letter-spacing:0.1em;
                           text-transform:uppercase;">Statistic</th>
                <th style="padding:7px 10px;color:{TEXT_ACC};text-align:right;
                           font-size:9px;font-family:monospace;">{x_var[:24]}</th>
                <th style="padding:7px 10px;color:#a78bfa;text-align:right;
                           font-size:9px;font-family:monospace;">{y_var[:24]}</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """
        return ui.HTML(html)

    # ── REGRESSION ────────────────────────────────────────────────────────────
    @reactive.Calc
    def reg_data():
        try:
            y_var  = input.reg_y()
            x_vars = list(input.reg_x())
        except:
            return None, "", []
        if not x_vars or not y_var:
            return None, y_var, x_vars

        needed = list(dict.fromkeys([y_var] + x_vars))
        df = cities_df[[c for c in needed if c in cities_df.columns]].copy()
        df = df.dropna().reset_index(drop=True)
        return df, y_var, x_vars

    @render.ui
    def reg_summary():
        df, y_var, x_vars = reg_data()
        if df is None or df.empty or not x_vars:
            return ui.HTML(
                f"<p style='color:{TEXT_SEC};padding:16px;'>"
                f"Select at least one regressor to run the model.</p>"
            )

        y     = df[y_var].to_numpy().astype(float)
        X_raw = df[x_vars].to_numpy().astype(float)
        if input.reg_intercept():
            X = np.column_stack([np.ones(len(X_raw)), X_raw])
            coef_names = ["Intercept"] + x_vars
        else:
            X = X_raw
            coef_names = x_vars

        coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        y_hat     = X @ coefs
        residuals = y - y_hat
        ss_res    = float(np.sum(residuals ** 2))
        ss_tot    = float(np.sum((y - y.mean()) ** 2))
        r2        = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        n, k      = len(y), len(coefs)
        r2_adj    = 1 - (1 - r2) * (n - 1) / (n - k - 1) if n > k + 1 else r2
        mse       = ss_res / (n - k) if n > k else np.nan
        rmse      = np.sqrt(mse) if not np.isnan(mse) else np.nan

        try:
            cov = mse * np.linalg.inv(X.T @ X)
            se  = np.sqrt(np.diag(cov))
            t   = coefs / se
            p   = [2 * (1 - scipy_stats.t.cdf(abs(ti), df=n - k)) for ti in t]
        except Exception:
            se = [np.nan] * len(coefs)
            t  = [np.nan] * len(coefs)
            p  = [np.nan] * len(coefs)

        def sig(pv):
            if np.isnan(pv): return ""
            if pv < 0.001:   return "***"
            if pv < 0.01:    return "**"
            if pv < 0.05:    return "*"
            if pv < 0.1:     return "·"
            return ""

        def pval_color(pv):
            if np.isnan(pv): return TEXT_SEC
            if pv < 0.05:    return "#4ade80"
            if pv < 0.1:     return "#facc15"
            return "#f87171"

        coef_rows = ""
        for name, c, s, ti, pv in zip(coef_names, coefs, se, t, p):
            coef_rows += (
                f"<tr style='border-bottom:1px solid {BORDER};'>"
                f"<td style='padding:7px 10px;color:{TEXT_ACC};font-family:monospace;font-size:11px;'>{name}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_PRI};text-align:right;font-family:monospace;font-size:11px;'>{c:,.4f}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_SEC};text-align:right;font-family:monospace;font-size:11px;'>{s:,.4f}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_SEC};text-align:right;font-family:monospace;font-size:11px;'>{ti:,.3f}</td>"
                f"<td style='padding:7px 10px;color:{pval_color(pv)};text-align:right;font-family:monospace;font-size:11px;'>"
                f"{'<0.001' if pv < 0.001 else f'{pv:.3f}'} {sig(pv)}</td>"
                f"</tr>"
            )

        r2_color = "#4ade80" if r2 > 0.5 else ("#facc15" if r2 > 0.25 else "#f87171")

        stat_cards = "".join([
            f"<div style='flex:1;min-width:120px;padding:12px 16px;background:{CARD_BG};"
            f"border-radius:8px;border-top:3px solid {col};'>"
            f"<div style='font-size:9px;color:{TEXT_SEC};font-family:monospace;"
            f"letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:22px;font-weight:700;color:{col};font-family:monospace;'>{val}</div>"
            f"</div>"
            for label, val, col in [
                ("R²",      f"{r2:.4f}",    r2_color),
                ("Adj. R²", f"{r2_adj:.4f}", r2_color),
                ("RMSE",    f"{rmse:,.2f}", TEXT_ACC),
                ("N",       str(n),         TEXT_SEC),
            ]
        ])

        html = f"""
        <div style="background:{DARK_BG};padding:16px;border-radius:8px;font-family:'DM Sans',sans-serif;">
          <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
            {stat_cards}
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid {MAROON};">
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:left;font-size:9px;font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;">Variable</th>
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:right;font-size:9px;font-family:monospace;">Coef</th>
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:right;font-size:9px;font-family:monospace;">Std Err</th>
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:right;font-size:9px;font-family:monospace;">t</th>
                <th style="padding:7px 10px;color:{TEXT_SEC};text-align:right;font-size:9px;font-family:monospace;">p-value</th>
              </tr>
            </thead>
            <tbody>{coef_rows}</tbody>
          </table>
          <div style="margin-top:10px;font-size:10px;color:{TEXT_SEC};font-family:monospace;">
            Significance: *** p&lt;0.001 &nbsp; ** p&lt;0.01 &nbsp; * p&lt;0.05 &nbsp; · p&lt;0.1
          </div>
        </div>
        """
        return ui.HTML(html)

    @render.ui
    def reg_fit_plot():
        df, y_var, x_vars = reg_data()
        if df is None or df.empty or not x_vars:
            return ui.HTML("")

        y     = df[y_var].to_numpy().astype(float)
        X_raw = df[x_vars].to_numpy().astype(float)
        X     = np.column_stack([np.ones(len(X_raw)), X_raw]) if input.reg_intercept() else X_raw
        coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        y_hat = X @ coefs

        fig, ax = plt.subplots(figsize=(6, 4))
        setup_ax(ax, fig)
        ax.scatter(y, y_hat, color="#4895ef", alpha=0.6, edgecolors=DARK_BG,
                   linewidths=0.3, s=40, zorder=3)
        mn, mx = min(y.min(), y_hat.min()), max(y.max(), y_hat.max())
        ax.plot([mn, mx], [mn, mx], color=TEXT_ACC, linewidth=1.6,
                linestyle="--", alpha=0.85, zorder=4, label="Perfect fit")
        ax.set_xlabel(f"Actual: {y_var[:30]}", color=TEXT_SEC, fontsize=9)
        ax.set_ylabel("Fitted",                color=TEXT_SEC, fontsize=9)
        ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI, fontsize=8)
        plt.tight_layout()
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def reg_resid_plot():
        df, y_var, x_vars = reg_data()
        if df is None or df.empty or not x_vars:
            return ui.HTML("")

        y     = df[y_var].to_numpy().astype(float)
        X_raw = df[x_vars].to_numpy().astype(float)
        X     = np.column_stack([np.ones(len(X_raw)), X_raw]) if input.reg_intercept() else X_raw
        coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        y_hat     = X @ coefs
        residuals = y - y_hat

        fig, ax = plt.subplots(figsize=(6, 4))
        setup_ax(ax, fig)
        ax.scatter(y_hat, residuals, color="#a78bfa", alpha=0.6,
                   edgecolors=DARK_BG, linewidths=0.3, s=40, zorder=3)
        ax.axhline(0, color=TEXT_ACC, linewidth=1.4, linestyle="--", alpha=0.8)
        ax.set_xlabel("Fitted values", color=TEXT_SEC, fontsize=9)
        ax.set_ylabel("Residuals",     color=TEXT_SEC, fontsize=9)
        plt.tight_layout()
        return ui.HTML(fig_to_html(fig))


# =============================================================================
# App
# =============================================================================
www_dir = os.path.join(os.path.dirname(__file__), "Data")
app = App(app_ui, server, static_assets=www_dir)