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
import matplotlib.ticker as mticker
import io, base64
from scipy import stats as scipy_stats
import altair as alt

# To run: # cd shiny_app -> shiny run --reload app.py
# To deploy # cd shiny_app -> rsconnect deploy shiny .

# =============================================================================
# BRAND & DESIGN TOKENS
# =============================================================================
MAROON      = "#0e7490"
MAROON_DARK = "#0c4a6e"
MAROON_MID  = "#0891b2"

DARK_BG   = "#0d1117"
PANEL_BG  = "#161b22"
CARD_BG   = "#1c2128"
BORDER    = "#30363d"
TEXT_PRI  = "#e6edf3"
TEXT_SEC  = "#8b949e"
TEXT_ACC  = "#22d3ee"

# =============================================================================
# COLORBLIND-FRIENDLY COLORMAPS
# =============================================================================
GROUP_CMAPS = {
    "zillow":      "YlOrRd",
    "census":      "RdPu",
    "centers":     "YlGn",
    "electricity": "YlOrBr",
    "water":       "GnBu",
    "hhc":         "OrRd",
}


def _mpl_to_hex_stops(cmap_name: str, n: int = 9) -> list:
    cmap = plt.get_cmap(cmap_name)
    return [mcolors.to_hex(cmap(i / (n - 1))) for i in range(n)]

def make_colormap(values, metric: str, group: str):
    clean = values.dropna()
    if clean.empty:
        colormap = cm.LinearColormap(["#1a1a2e", "#22d3ee"], vmin=0, vmax=1, caption=metric)
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

HHC_COLS_FRIENDLY = [
    "Household Cost Score (2007\u20132011)",
    "Household Cost Score (2019\u20132023)",
    "Household Cost Score (2020\u20132024)",
]

OPTIONAL_COLS = ["Total Population", "Land Area (sq meters)"]

METRIC_GROUP_CHOICES = {}

def _grouped_select_html(input_id, groups, default=None):
    first_val = default
    opts = ""
    for grp_label, cols in groups:
        if not cols:
            continue
        opts += f"<optgroup label=\"{grp_label}\">"
        for c in cols:
            sel = ' selected' if first_val is None else (' selected' if c == first_val else '')
            if first_val is None:
                first_val = c
            opts += f"<option value=\"{c}\"{sel}>{c}</option>"
        opts += "</optgroup>"

    html = f"""
    <select id="gs-{input_id}"
      onchange="Shiny.setInputValue('{input_id}', this.value)"
      style="width:100%;background:#1c2128;color:#e6edf3;border:1px solid #30363d;
             border-radius:6px;font-size:13px;padding:6px 8px;
             font-family:'DM Sans',sans-serif;outline:none;cursor:pointer;
             transition:border-color 0.2s;">
      {opts}
    </select>
    <script>
      (function(){{
        var el = document.getElementById("gs-{input_id}");
        if (el) {{
          Shiny.setInputValue("{input_id}", el.value);
          el.addEventListener('focus', function() {{ this.style.borderColor='#0e7490'; this.style.boxShadow='0 0 0 2px rgba(14,116,144,0.22)'; }});
          el.addEventListener('blur',  function() {{ this.style.borderColor='#30363d'; this.style.boxShadow='none'; }});
        }}
      }})();
    </script>
    """
    return ui.HTML(html)


# =============================================================================
# LOAD & PRE-PROCESS DATA
# =============================================================================
def load_data():
    app_dir      = os.path.dirname(os.path.abspath(__file__))
    cities_path  = os.path.join(app_dir, "Data", "Chicago.gpkg")
    centers_path = os.path.join(app_dir, "Data", "ChicagoDataCenters.gpkg")
    impact_path  = os.path.join(app_dir, "Data", "chicag_data_centers_impact_scores.csv")
    cities       = gpd.read_file(cities_path)
    centers      = gpd.read_file(centers_path)
    impact_df    = pd.read_csv(impact_path) if os.path.exists(impact_path) else pd.DataFrame()
    return cities, centers, impact_df, cities_path

cities_gdf, centers_gdf, impact_df, cities_path = load_data()
cities_gdf  = cities_gdf.to_crs(epsg=4326)
centers_gdf = centers_gdf.to_crs(epsg=4326)

cities_gdf.geometry  = cities_gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)
centers_gdf.geometry = centers_gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)

_centroids  = cities_gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
MAP_CENTER  = [float(_centroids.y.mean()), float(_centroids.x.mean())]

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
HHC_COLS     = _present(HHC_COLS_FRIENDLY)
OPT_COLS     = _present(OPTIONAL_COLS)

ALL_NUMERIC = ZILLOW_COLS + CENSUS_COLS + DC_COLS + ELEC_COLS + WATER_COLS + HHC_COLS + OPT_COLS

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
for c in HHC_COLS:     COL_GROUP[c] = "hhc"
for c in OPT_COLS:     COL_GROUP[c] = "census"

GROUP_COLS = {
    "zillow":      ZILLOW_COLS,
    "census":      CENSUS_COLS,
    "centers":     DC_COLS,
    "electricity": ELEC_COLS,
    "water":       WATER_COLS,
    "hhc":         HHC_COLS,
}

if ZILLOW_COLS:  METRIC_GROUP_CHOICES["zillow"]      = "🏠  Home Values"
if CENSUS_COLS:  METRIC_GROUP_CHOICES["census"]      = "👥  Demographics"
if DC_COLS:      METRIC_GROUP_CHOICES["centers"]     = "🏢  Data Centers"
if ELEC_COLS:    METRIC_GROUP_CHOICES["electricity"] = "⚡  Electricity"
if WATER_COLS:   METRIC_GROUP_CHOICES["water"]       = "💧  Water & Sewer"
if HHC_COLS:     METRIC_GROUP_CHOICES["hhc"]         = "💰 Housing Cost Burden"

CITIES_GEOJSON = cities_gdf.__geo_interface__

def _load_boundary(filename):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data", filename)
    if os.path.exists(path):
        return gpd.read_file(path).to_crs(epsg=4326)
    return None

illinois_gdf    = _load_boundary("illinois.gpkg")
cook_county_gdf = _load_boundary("cook_county.gpkg")
chicago_gdf     = _load_boundary("chicagoproper.gpkg")

ILLINOIS_GEOJSON    = illinois_gdf.__geo_interface__    if illinois_gdf    is not None else None
COOK_COUNTY_GEOJSON = cook_county_gdf.__geo_interface__ if cook_county_gdf is not None else None
CHICAGO_GEOJSON     = chicago_gdf.__geo_interface__     if chicago_gdf     is not None else None


# =============================================================================
# NUMBER FORMATTING HELPERS
# =============================================================================
def fmt_number(v, is_price=False, decimals=None):
    """Smart number formatter: $1.2M, $450k, 1,234, 45.3%"""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    v = float(v)
    if is_price:
        if abs(v) >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if abs(v) >= 1_000:     return f"${v/1_000:.0f}k"
        return f"${v:,.0f}"
    if decimals is not None:
        return f"{v:,.{decimals}f}"
    if abs(v) >= 1_000_000: return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:     return f"{v:,.0f}"
    return f"{v:,.3f}"

def smart_axis_formatter(col_name):
    """Return a matplotlib FuncFormatter appropriate for the column."""
    col_lower = col_name.lower()
    if any(k in col_lower for k in ["home value", "income", "price"]):
        return mticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k" if abs(x) >= 1000 else f"${x:.0f}")
    if "%" in col_name or "rate" in col_lower or "share" in col_lower:
        return mticker.FuncFormatter(lambda x, _: f"{x:.1f}%")
    if abs(float(col_name.replace(",","") if col_name.replace(",","").replace(".","").lstrip("-").isdigit() else "0")) >= 1000:
        return mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k" if abs(x) >= 1000 else f"{x:.0f}")
    return mticker.FuncFormatter(lambda x, _: f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.2f}")


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

def fig_to_html(fig, dpi=150):
    """Lower DPI default (150 vs 180) for faster rendering on free tier."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=dpi)
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

# Skeleton loader HTML (shown while outputs render)
SKELETON_HTML = f"""
<div class="skeleton-wrap">
  <div class="skeleton-bar" style="width:60%;height:14px;margin-bottom:12px;border-radius:4px;"></div>
  <div class="skeleton-bar" style="width:100%;height:240px;border-radius:6px;margin-bottom:10px;"></div>
  <div class="skeleton-bar" style="width:80%;height:12px;border-radius:4px;"></div>
</div>
"""

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
  -webkit-font-smoothing: antialiased;
}}
.card p, .card li, .card span:not(.bslib-full-screen-enter) {{
  color: {TEXT_PRI};
}}

/* ── Skeleton loader ── */
@keyframes shimmer {{
  0%   {{ background-position: -400px 0; }}
  100% {{ background-position:  400px 0; }}
}}
.skeleton-wrap {{ padding: 16px; }}
.skeleton-bar {{
  background: linear-gradient(
    90deg,
    {PANEL_BG} 25%,
    {CARD_BG}  50%,
    {PANEL_BG} 75%
  );
  background-size: 800px 100%;
  animation: shimmer 1.4s infinite linear;
  opacity: 0.85;
}}

/* ── Fade-in for rendered outputs ── */
@keyframes fadeSlideIn {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
.shiny-bound-output > * {{
  animation: fadeSlideIn 0.3s ease forwards;
}}

/* ── Navbar ── */
.navbar {{
  background: linear-gradient(135deg, {MAROON_DARK} 0%, {MAROON} 55%, {MAROON_MID} 100%) !important;
  border-bottom: 1px solid {MAROON_DARK} !important;
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
.navbar-nav {{
  align-items: flex-end !important;
}}
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
  border-bottom: 2px solid {TEXT_ACC};
}}


/* ── Bottom bar ── */
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
  transform: translateY(100%);
  transition: transform 0.3s ease;
}}
#bottom-bar.visible {{ transform: translateY(0); }}
#bottom-bar span {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 12px;
  color: rgba(255,255,255,0.78);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}}
body {{ padding-bottom: 42px !important; }}

/* ── Sidebar ── */
.sidebar,
.bslib-sidebar-layout > .sidebar,
.bslib-sidebar-layout > .sidebar > .sidebar-content,
aside.sidebar {{
  background: {PANEL_BG} !important;
  border-right: 1px solid {BORDER} !important;
  color: {TEXT_PRI} !important;
  padding: 20px 18px !important;
}}

/* ── Collapsible sidebar sections ── */
.sidebar-section-title {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: {TEXT_ACC};
  margin: 18px 0 5px;
  opacity: 0.85;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: default;
}}
.sidebar label, .sidebar .control-label,
.sidebar .form-check-label, .sidebar p, .sidebar strong {{
  color: #d0d7de !important;
  font-size: 13px;
  font-weight: 400;
}}
.sidebar h4 {{
  font-family: 'DM Serif Display', serif !important;
  font-size: 18px !important;
  color: #ffffff !important;
  margin: 0 0 8px;
  letter-spacing: 0.01em;
  padding-bottom: 8px;
  border-bottom: 1px solid {BORDER};
}}
.sidebar .form-select, .sidebar .form-control, .sidebar select {{
  background: {CARD_BG} !important;
  color: {TEXT_PRI} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px !important;
  font-size: 13px;
  transition: border-color 0.2s, box-shadow 0.2s;
}}
.sidebar .form-select:focus {{
  border-color: {MAROON} !important;
  box-shadow: 0 0 0 2px rgba(14,116,144,0.22) !important;
}}
.sidebar .selectize-input, .sidebar .selectize-input input {{
  background: {CARD_BG} !important;
  color: {TEXT_PRI} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 6px !important;
  box-shadow: none !important;
  font-size: 13px;
  transition: border-color 0.2s;
}}
.sidebar .selectize-input.focus {{
  border-color: {MAROON} !important;
  box-shadow: 0 0 0 2px rgba(14,116,144,0.22) !important;
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
  transition: background 0.15s, border-color 0.15s;
}}
.sidebar .form-check-input:checked {{
  background: {MAROON} !important; border-color: {MAROON} !important;
}}
.sidebar .form-check-input:focus {{
  box-shadow: 0 0 0 2px rgba(14,116,144,0.25) !important;
}}
.sidebar hr {{
  border: none; border-top: 1px solid {BORDER} !important;
  margin: 16px 0; opacity: 1;
}}
.source-note {{
  font-family: 'DM Sans', sans-serif;
  font-size: 11px; color: #a1adb9; line-height: 1.7;
  margin-top: 12px; padding-top: 12px;
  border-top: 1px solid {BORDER};
}}

/* ── Reset button ── */
.reset-btn {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: 1px solid {BORDER};
  border-radius: 5px;
  color: {TEXT_SEC};
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.08em;
  padding: 4px 10px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  margin-top: 10px;
  width: 100%;
  justify-content: center;
}}
.reset-btn:hover {{
  background: rgba(14,116,144,0.15);
  border-color: {MAROON};
  color: {TEXT_PRI};
}}

/* ── Cards ── */
.card {{
  background: {CARD_BG} !important;
  border: 1px solid {BORDER} !important;
  border-radius: 10px !important;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04);
  transition: box-shadow 0.22s ease, border-color 0.22s ease, transform 0.15s ease;
}}
.card:hover {{
  box-shadow: 0 8px 36px rgba(0,0,0,0.6), 0 0 0 1px {MAROON_DARK}, inset 0 1px 0 rgba(255,255,255,0.06);
  border-color: {MAROON_DARK} !important;
  transform: translateY(-1px);
}}
.card-header {{
  background: linear-gradient(90deg, {MAROON_DARK} 0%, {MAROON} 60%, {MAROON_MID} 100%) !important;
  color: #fff !important;
  font-family: 'IBM Plex Mono', monospace !important;
  font-size: 10px !important; font-weight: 500 !important;
  letter-spacing: 0.13em !important; text-transform: uppercase !important;
  padding: 9px 16px !important; border-bottom: none !important;
  display: flex; align-items: center; gap: 8px;
}}
.bslib-full-screen-enter {{
  color: rgba(255,255,255,0.55) !important;
  transition: color 0.15s;
}}
.bslib-full-screen-enter:hover {{ color: #fff !important; }}
.bslib-full-screen-exit {{
  background: {MAROON} !important;
  border-color: {MAROON_DARK} !important;
  color: #fff !important;
}}

/* ── Global backgrounds ── */
body, .bslib-page-sidebar, .bslib-sidebar-layout {{
  background: {DARK_BG} !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {DARK_BG}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; transition: background 0.2s; }}
::-webkit-scrollbar-thumb:hover {{ background: {MAROON}; }}

/* ── Tabs main content area padding ── */
.tab-content > .tab-pane,
.bslib-page-sidebar > .main {{
  padding: 16px !important;
}}

/* ── Card body text clarity ── */
.card-body {{
  color: {TEXT_PRI} !important;
  font-size: 13px;
  line-height: 1.6;
}}

/* ── Active nav pill highlight ── */
.navbar-nav .nav-link.active {{
  color: #fff !important;
  border-bottom: 3px solid {TEXT_ACC} !important;
  font-weight: 600 !important;
}}

/* ── Note banner ── */
.placeholder-note {{
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(34,211,238,0.07);
  border: 1px solid rgba(34,211,238,0.22);
  border-radius: 8px;
  padding: 10px 16px;
  margin: 0 20px 14px;
  font-size: 11px;
  color: {TEXT_ACC};
  font-family: 'IBM Plex Mono', monospace;
}}

/* ── Regression X selectize pills ── */
.sidebar .selectize-input .item {{
  background: {MAROON} !important;
  color: #ffffff !important;
  border: 1px solid {MAROON_DARK} !important;
  border-radius: 4px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: 12px !important;
  padding: 2px 8px !important;
  margin: 2px 3px 2px 0 !important;
}}
.sidebar .selectize-input .item .remove {{
  color: rgba(255,255,255,0.6) !important;
  border-left: 1px solid rgba(255,255,255,0.25) !important;
  padding: 0 4px !important;
  margin-left: 4px !important;
}}
.sidebar .selectize-input .item .remove:hover {{
  background: {MAROON_DARK} !important;
  color: #ffffff !important;
}}

/* ── KPI strip counter animation ── */
@keyframes countUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
.kpi-value {{
  animation: countUp 0.5s cubic-bezier(0.22,1,0.36,1) both;
}}
.kpi-value:nth-child(1) {{ animation-delay: 0.05s; }}
.kpi-value:nth-child(2) {{ animation-delay: 0.15s; }}
.kpi-value:nth-child(3) {{ animation-delay: 0.25s; }}

/* ── Map floating metric badge ── */
#metric-badge {{
  position: absolute;
  top: 12px; right: 12px;
  z-index: 1000;
  background: rgba(22,27,34,0.92);
  border: 1px solid {BORDER};
  border-left: 3px solid {MAROON};
  border-radius: 6px;
  padding: 6px 12px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: {TEXT_PRI};
  pointer-events: none;
  max-width: 220px;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  letter-spacing: 0.04em;
}}

/* ── Keyboard shortcut hint ── */
.kbd {{
  display: inline-block;
  background: {CARD_BG};
  border: 1px solid {BORDER};
  border-radius: 3px;
  padding: 1px 5px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: {TEXT_SEC};
  letter-spacing: 0;
  vertical-align: middle;
}}

/* ── Empty state ── */
.empty-state {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  gap: 12px;
  color: {TEXT_SEC};
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  text-align: center;
}}
.empty-state svg {{ opacity: 0.3; }}

/* ── Sidebar toggle button ── */
.sidebar-toggle,
[data-bs-toggle="collapse"],
.bslib-sidebar-layout .collapse-toggle {{
  color: #ffffff !important;
  background: transparent !important;
}}
.sidebar-toggle svg,
[data-bs-toggle="collapse"] svg,
.bslib-sidebar-layout .collapse-toggle svg {{
  fill: #ffffff !important;
  stroke: #ffffff !important;
  color: #ffffff !important;
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
    text-transform:uppercase;color:#0e7490;margin-bottom:12px;display:flex;align-items:center;gap:8px;">
    <span style="display:inline-block;width:24px;height:1px;background:#0e7490;"></span>
    Research Question
  </div>
  <div style="font-family:'DM Serif Display',serif;font-size:26px;color:#ffffff;margin-bottom:16px;
    line-height:1.25;letter-spacing:0.01em;max-width:680px;">
    Do data centers change the<br>neighborhoods around them?
  </div>
  <div style="width:48px;height:2px;background:linear-gradient(90deg,#0e7490,transparent);margin-bottom:18px;"></div>
  <div style="font-family:'DM Sans',sans-serif;font-size:13.5px;color:#a1adb9;line-height:1.75;
    max-width:820px;margin-bottom:24px;">
    This dashboard examines <span style="color:#e6edf3;font-weight:500;">45 data center facilities
    across the Chicago metro area</span> and their relationship to local housing markets.
    For each facility we compare housing prices and housing-cost burden scores
    <span style="color:#e6edf3;font-weight:500;">before and after the first operation permit</span>
    was issued, then combine those changes into a single
    <span style="color:#22d3ee;font-weight:600;">impact score</span>.
    A <span style="color:#4ade80;font-weight:500;">positive score</span> means the surrounding ZIP code
    became more expensive <em>and</em> housing-cost burden increased after the facility opened;
    a <span style="color:#f87171;font-weight:500;">negative score</span> suggests the opposite.
  </div>
  <div style="font-family:'DM Sans',sans-serif;font-size:12.5px;color:#8b949e;line-height:1.75;
    max-width:820px;margin-bottom:24px;border-top:1px solid #30363d;padding-top:16px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:0.15em;
      text-transform:uppercase;color:#0e7490;display:block;margin-bottom:6px;">Background</span>
    Data Centers are facilities with IT infrastructure that enables companies and users to build,
    run, and deliver applications and services. As AI becomes an increasingly integral part of
    digital products and services, new data centers are built at an unprecedented rate. However, data
    centers have been subject to controversy among many communities for how they have affected
    costs of living. In <span style="color:#e6edf3;font-weight:500;">Data Centers Next Door</span>,
    we aim to see if communities in the Chicagoland area have seen similar rising costs due to
    the building of data centers in their community.
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                 letter-spacing:0.12em;text-transform:uppercase;color:#8b949e;
                 margin-right:4px;">Explore →</span>
    <span onclick="document.querySelectorAll('.navbar-nav .nav-link')[0].click()"
      style="display:inline-flex;align-items:center;gap:5px;background:rgba(14,116,144,0.18);
      border:1px solid rgba(14,116,144,0.4);border-radius:20px;padding:5px 12px;
      font-family:'DM Sans',sans-serif;font-size:11px;color:#e6edf3;cursor:pointer;">
      📍 Atlas
    </span>
    <span onclick="document.querySelectorAll('.navbar-nav .nav-link')[1].click()"
      style="display:inline-flex;align-items:center;gap:5px;
                 background:rgba(30,40,55,0.6);border:1px solid #30363d;
                 border-radius:20px;padding:5px 12px;
                 font-family:'DM Sans',sans-serif;font-size:11px;color:#c9d1d9;cursor:pointer;">
      🗺️ Map
    </span>
    <span onclick="document.querySelectorAll('.navbar-nav .nav-link')[2].click()"
      style="display:inline-flex;align-items:center;gap:5px;
                 background:rgba(30,40,55,0.6);border:1px solid #30363d;
                 border-radius:20px;padding:5px 12px;
                 font-family:'DM Sans',sans-serif;font-size:11px;color:#c9d1d9;cursor:pointer;">
      📈 Correlations
    </span>
    <span onclick="document.querySelectorAll('.navbar-nav .nav-link')[3].click()"
      style="display:inline-flex;align-items:center;gap:5px;
                 background:rgba(30,40,55,0.6);border:1px solid #30363d;
                 border-radius:20px;padding:5px 12px;
                 font-family:'DM Sans',sans-serif;font-size:11px;color:#c9d1d9;cursor:pointer;">
      📊 OLS
    </span>
    <span onclick="document.querySelectorAll('.navbar-nav .nav-link')[4].click()"
      style="display:inline-flex;align-items:center;gap:5px;
                 background:rgba(30,40,55,0.6);border:1px solid #30363d;
                 border-radius:20px;padding:5px 12px;
                 font-family:'DM Sans',sans-serif;font-size:11px;color:#c9d1d9;cursor:pointer;">
      🔬 PCA
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
                        style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{TEXT_SEC};"
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
                        style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{TEXT_SEC};"
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
                    style=f"padding:10px 16px 0;background:{CARD_BG};max-width:260px;",
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
                style=f"font-family:'DM Sans',sans-serif;font-size:12px;color:{TEXT_SEC};"
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
                    "metric_group", None,
                    choices=METRIC_GROUP_CHOICES,
                    selected=list(METRIC_GROUP_CHOICES.keys())[0],
                ),
                ui.div("VARIABLE", class_="sidebar-section-title"),
                ui.output_ui("metric_selector"),
                ui.hr(),
                ui.input_checkbox("show_centers",  "Data Centers",  value=True),
                ui.input_checkbox("show_illinois", "Illinois",      value=True),
                ui.input_checkbox("show_cook",     "Cook County",   value=True),
                ui.input_checkbox("show_chicago",  "Chicago",       value=True),
                ui.hr(),
                ui.HTML(f"""
                  <button class="reset-btn" onclick="resetMapDefaults()">
                    ↺ &nbsp;Reset to defaults
                  </button>
                  <script>
                  function resetMapDefaults() {{
                    var sel = document.querySelector('#metric_group');
                    if (sel) {{ sel.selectedIndex = 0; sel.dispatchEvent(new Event('change')); }}
                  }}
                  </script>
                """),
                ui.hr(),
                ui.div(
                    "Sources: Zillow (2010, 2019, 2024) · ACS 2022 · "
                    "NHGIS 2022 · Manual DC inventory",
                    class_="source-note"
                ),
                style=f"background:{PANEL_BG}; min-width:225px;",
            ),
            ui.div(
                ui.card(
                    ui.card_header("Chicago Metro — ZIP Code Choropleth"),
                    ui.output_ui("map_plot"),
                ),
                style="position:relative;",
            ),
        ),
    ),

    # ── RELATIONSHIPS ─────────────────────────────────────────────────────────
    ui.nav_panel(
        "Explore Correlations",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Variables"),
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
                ui.card(ui.card_header("Scatter Plot"),          ui.output_ui("scatter_plot"), full_screen=True),
                ui.card(ui.card_header("Correlation & Summary"), ui.output_ui("summary_stats")),
                col_widths=(8, 4),
            ),
            ui.card(ui.card_header("Distributions"),             ui.output_ui("dist_plot"),    full_screen=True),
        ),
    ),

    # ── REGRESSIONS ───────────────────────────────────────────────────────────
    ui.nav_panel(
        "OLS Model",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Regression"),
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
            ui.card(ui.card_header("Regression Results"),  ui.output_ui("reg_summary")),
            ui.layout_columns(
                ui.card(ui.card_header("Fitted vs Actual"), ui.output_ui("reg_fit_plot"),   full_screen=True),
                ui.card(ui.card_header("Residuals"),        ui.output_ui("reg_resid_plot"), full_screen=True),
                col_widths=(6, 6),
            ),
        ),
    ),

    # ── PCA ───────────────────────────────────────────────────────────────────
    ui.nav_panel(
        "PCA Analysis",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("PCA"),
                ui.div("VARIABLES", class_="sidebar-section-title"),
                ui.input_selectize(
                    "pca_vars", None,
                    choices={c: c for c in ALL_NUMERIC},
                    selected=ALL_NUMERIC[:6] if len(ALL_NUMERIC) >= 6 else ALL_NUMERIC,
                    multiple=True,
                ),
                ui.hr(),
                ui.div("COLOUR POINTS BY", class_="sidebar-section-title"),
                ui.input_select(
                    "pca_color_var", None,
                    choices={"none": "— None —", **{c: c for c in ALL_NUMERIC}},
                    selected="none",
                ),
                ui.hr(),
                ui.input_checkbox("pca_scale", "Standardise variables (recommended)", value=True),
                ui.hr(),
                ui.div(
                    "PCA via numpy SVD. Each point = one ZIP code. "
                    "Select ≥ 2 variables to run.",
                    class_="source-note"
                ),
                style=f"background:{PANEL_BG}; min-width:225px;",
            ),
            ui.layout_columns(
                ui.card(ui.card_header("Scree Plot — Explained Variance"),   ui.output_ui("pca_scree")),
                ui.card(ui.card_header("PC1 vs PC2 — ZIP Code Scores"),      ui.output_ui("pca_scores")),
                col_widths=(5, 7),
            ),
            ui.layout_columns(
                ui.card(ui.card_header("Loadings — PC1 & PC2"),              ui.output_ui("pca_loadings")),
                ui.card(ui.card_header("Correlation: Variables vs PCs"),     ui.output_ui("pca_corr_heat")),
                col_widths=(6, 6),
            ),
            ui.card(ui.card_header("Component Summary Table"),               ui.output_ui("pca_table")),
        ),
    ),

    ui.nav_spacer(),
    ui.nav_control(ui.tags.img(src="logo.png", style="height:36px;display:block;margin:0 6px;")),


    header=ui.tags.head(
        ui.tags.style(CUSTOM_CSS),
        ui.tags.link(rel="preconnect", href="https://fonts.googleapis.com"),
        ui.tags.link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        ui.tags.script("""
          // ── Bottom bar scroll show/hide ──
          document.addEventListener('DOMContentLoaded', function() {
            var bar = document.createElement('div');
            bar.id = 'bottom-bar';
            bar.innerHTML = '<span>— Data Centers Next Door —</span>';
            document.body.appendChild(bar);
            window.addEventListener('scroll', function() {
              bar.classList.toggle('visible', window.scrollY > 40);
            }, { passive: true });
          });

          // ── Keyboard shortcuts: 1=Atlas 2=Map 3=Rel 4=Reg 5=PCA ──
          document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
            var tabs = document.querySelectorAll('.navbar-nav .nav-link');
            var map = {'1':0,'2':1,'3':2,'4':3,'5':4};
            if (map[e.key] !== undefined && tabs[map[e.key]]) {
              tabs[map[e.key]].click();
              e.preventDefault();
            }
          });
        """),
    ),

    title=ui.HTML(
        "<span style=\"display:inline-flex; flex-direction:column; line-height:1.1; "
        "vertical-align:middle; gap:1px;\">"
        "<span style=\"font-family:'IBM Plex Mono',monospace; font-size:8.5px; "
        "color:#22d3ee; letter-spacing:0.2em; text-transform:uppercase;\">Chicagoland</span>"
        "<span style=\"font-family:'DM Serif Display',serif; font-size:17px; "
        "color:#fff; letter-spacing:0.02em;\">Data Center Dashboard</span>"
        "</span>"
    ),
    bg="#0c4a6e",
    inverse=True,
)


# =============================================================================
# SERVER
# =============================================================================
def server(input, output, session):

    # ── INFRASTRUCTURE ATLAS ─────────────────────────────────────────────────
    @reactive.Calc
    def _atlas_df():
        if impact_df.empty:
            return pd.DataFrame()
        df = impact_df.copy()
        num_cols = [
            "Housing_Avg_Price", "Housing_Avg_Price_Before_Permit",
            "Housing_Avg_Price_After_Permit", "HC_Score_Before", "HC_Score_After",
            "Housing_Change", "HC_Score_Change", "Complete",
            "Housing_Change_score", "Housing_Change_z_score",
            "HC_Score_Change_score", "HC_Score_Change_z_score",
            "impact_score", "impact_z_score",
        ]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "First_Operation_Permit" in df.columns:
            df["Year"] = pd.to_numeric(df["First_Operation_Permit"], errors="coerce")
        return df

    def _empty_state(msg="Impact data file not found", sub="Place chicag_data_centers_impact_scores.csv in the Data/ folder"):
        return ui.HTML(
            f"""<div class="empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="{TEXT_SEC}" stroke-width="1.5">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <div style="color:{TEXT_PRI};font-weight:500;">{msg}</div>
              <div style="font-size:11px;">{sub}</div>
            </div>"""
        )

    @render.ui
    def atlas_kpi_strip():
        df = _atlas_df()
        if df.empty:
            return _empty_state()
        n_fac   = len(df)
        avg_imp = df["impact_score"].mean() if "impact_score" in df.columns else float("nan")
        imp_color = "#4ade80" if (not np.isnan(avg_imp) and avg_imp > 0) else "#f87171"
        def kpi(label, val, sub, accent):
            return (
                f"<div style='flex:1;background:{CARD_BG};border:1px solid {BORDER};"
                f"border-radius:10px;padding:20px 24px;border-top:3px solid {accent};"
                f"box-shadow:0 4px 16px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.04);'>"
                f"<div style='font-family:monospace;font-size:9px;letter-spacing:0.13em;"
                f"text-transform:uppercase;color:{TEXT_SEC};margin-bottom:8px;'>{label}</div>"
                f"<div class='kpi-value' style='font-family:monospace;font-size:32px;font-weight:700;"
                f"color:{accent};line-height:1;letter-spacing:-0.02em;'>{val}</div>"
                f"<div style='font-size:10px;color:{TEXT_SEC};margin-top:6px;'>{sub}</div>"
                f"</div>"
            )
        cards = "".join([
            kpi("Facilities", str(n_fac), "data centers in dataset", TEXT_ACC),
            kpi("Avg Impact Score", f"{avg_imp:+.3f}" if not np.isnan(avg_imp) else "—",
                "composite score across all ZIPs", imp_color),
        ])
        return ui.HTML(f"<div style='display:flex;gap:16px;padding:4px 4px 0;'>{cards}</div>")

    @render.ui
    def atlas_timeseries_chart():
        df = _atlas_df()
        ts_df = None
        if not df.empty and "First_Operation_Permit" in df.columns:
            ts_df = df[["First_Operation_Permit"]].copy()
            ts_df["year"] = pd.to_numeric(ts_df["First_Operation_Permit"], errors="coerce")
        elif not centers_gdf.empty:
            for col in centers_gdf.columns:
                if any(k in col.lower() for k in ["permit", "operation", "year", "opened"]):
                    ts_df = pd.DataFrame({"year": pd.to_numeric(centers_gdf[col], errors="coerce")})
                    break
        if ts_df is None or ts_df["year"].dropna().empty:
            return _empty_state("No permit year data found", "Add First_Operation_Permit to impact CSV")
        ts_df = ts_df.dropna(subset=["year"])
        ts_df["year"] = ts_df["year"].astype(int)
        by_year = ts_df["year"].value_counts().sort_index().cumsum().reset_index()
        by_year.columns = ["year", "count"]
        import json as _json
        pts = [{"year": int(r["year"]), "count": int(r["count"])} for _, r in by_year.iterrows()]
        pts_json = _json.dumps(pts)
        total = int(by_year["count"].max())
        html = f"""
<div style="font-family:monospace;padding:8px 4px;height:100%;">
  <div style="font-size:10px;color:{TEXT_SEC};margin-bottom:6px;padding:0 4px;">
    Cumulative facilities · first operation permit year
  </div>
  <svg id="ts-svg" width="100%" style="display:block;"></svg>
</div>
<script>
(function(){{
  const PTS={pts_json}, TOTAL={total};
  const DARK="{DARK_BG}",BDR="{BORDER}",TSEC="{TEXT_SEC}",TACC="{TEXT_ACC}",MAR="{MAROON}";
  const PAD={{t:14,r:14,b:34,l:38}};
  const svg=document.getElementById("ts-svg");
  const ns="http://www.w3.org/2000/svg";
  const tip=document.createElement("div");
  tip.style.cssText="display:none;position:fixed;pointer-events:none;z-index:9999;"+
    "background:#1c2128;border:1px solid #30363d;border-radius:6px;"+
    "padding:6px 10px;font-size:11px;color:#e6edf3;font-family:monospace;"+
    "box-shadow:0 4px 16px rgba(0,0,0,0.6);";
  document.body.appendChild(tip);
  function render(){{
    const W=svg.getBoundingClientRect().width||280, H=500;
    svg.setAttribute("height",H); svg.innerHTML="";
    const cw=W-PAD.l-PAD.r, ch=H-PAD.t-PAD.b;
    const minX=PTS[0].year, maxX=PTS[PTS.length-1].year, spanX=maxX-minX||1;
    function px(yr){{return PAD.l+(yr-minX)/spanX*cw;}}
    function py(v) {{return PAD.t+ch-(v/TOTAL)*ch;}}
    const bg=document.createElementNS(ns,"rect");
    bg.setAttribute("width","100%");bg.setAttribute("height",H);
    bg.setAttribute("fill",DARK);svg.appendChild(bg);
    [0,0.25,0.5,0.75,1].forEach(f=>{{
      const v=Math.round(TOTAL*f), y=py(v);
      const gl=document.createElementNS(ns,"line");
      gl.setAttribute("x1",PAD.l);gl.setAttribute("x2",PAD.l+cw);
      gl.setAttribute("y1",y);gl.setAttribute("y2",y);
      gl.setAttribute("stroke",BDR);gl.setAttribute("stroke-width","0.5");
      gl.setAttribute("stroke-dasharray","3,3");svg.appendChild(gl);
      const tl=document.createElementNS(ns,"text");
      tl.setAttribute("x",PAD.l-4);tl.setAttribute("y",y+3.5);
      tl.setAttribute("fill",TSEC);tl.setAttribute("font-size","7.5");
      tl.setAttribute("font-family","monospace");tl.setAttribute("text-anchor","end");
      tl.textContent=v;svg.appendChild(tl);
    }});
    let ap=`M ${{px(PTS[0].year)}} ${{py(0)}} L ${{px(PTS[0].year)}} ${{py(PTS[0].count)}}`;
    PTS.forEach((p,i)=>{{if(i>0)ap+=` L ${{px(p.year)}} ${{py(p.count)}}`;}});
    ap+=` L ${{px(PTS[PTS.length-1].year)}} ${{py(0)}} Z`;
    const area=document.createElementNS(ns,"path");
    area.setAttribute("d",ap);area.setAttribute("fill",MAR);
    area.setAttribute("fill-opacity","0.2");svg.appendChild(area);
    let lp=`M ${{px(PTS[0].year)}} ${{py(PTS[0].count)}}`;
    PTS.forEach((p,i)=>{{if(i>0)lp+=` L ${{px(p.year)}} ${{py(p.count)}}`;}});
    const ln=document.createElementNS(ns,"path");
    ln.setAttribute("d",lp);ln.setAttribute("fill","none");
    ln.setAttribute("stroke",MAR);ln.setAttribute("stroke-width","2.2");
    ln.setAttribute("stroke-linejoin","round");ln.setAttribute("stroke-linecap","round");
    svg.appendChild(ln);
    const step=Math.max(1,Math.floor(spanX/4));
    for(let yr=minX;yr<=maxX;yr+=step){{
      const tl=document.createElementNS(ns,"text");
      tl.setAttribute("x",px(yr));tl.setAttribute("y",H-PAD.b+14);
      tl.setAttribute("fill",TSEC);tl.setAttribute("font-size","7.5");
      tl.setAttribute("font-family","monospace");tl.setAttribute("text-anchor","middle");
      tl.textContent=yr;svg.appendChild(tl);
    }}
    PTS.forEach(p=>{{
      const cx=px(p.year),cy=py(p.count);
      const dot=document.createElementNS(ns,"circle");
      dot.setAttribute("cx",cx);dot.setAttribute("cy",cy);dot.setAttribute("r","3");
      dot.setAttribute("fill",TACC);dot.setAttribute("stroke",DARK);
      dot.setAttribute("stroke-width","1");svg.appendChild(dot);
      const hit=document.createElementNS(ns,"circle");
      hit.setAttribute("cx",cx);hit.setAttribute("cy",cy);hit.setAttribute("r","9");
      hit.setAttribute("fill","transparent");hit.style.cursor="default";
      hit.addEventListener("mousemove",e=>{{
        tip.style.display="block";
        tip.style.left=(e.clientX+14)+"px";tip.style.top=(e.clientY-10)+"px";
        tip.innerHTML=`<b style="color:${{TACC}}">${{p.year}}</b><br>`+
          `<span style="color:#8b949e">Cumulative: </span>${{p.count}} facilities`;
      }});
      hit.addEventListener("mouseleave",()=>{{tip.style.display="none";}});
      svg.appendChild(hit);
    }});
    const last=PTS[PTS.length-1];
    const ann=document.createElementNS(ns,"text");
    ann.setAttribute("x",px(last.year)-5);ann.setAttribute("y",py(last.count)-8);
    ann.setAttribute("fill",TACC);ann.setAttribute("font-size","9");
    ann.setAttribute("font-family","monospace");ann.setAttribute("text-anchor","end");
    ann.setAttribute("font-weight","bold");ann.textContent=TOTAL+" total";
    svg.appendChild(ann);
  }}
  render();
  new ResizeObserver(render).observe(svg);
}})();
</script>"""
        return ui.HTML(html)

    @render.ui
    def atlas_company_bar_chart():
        import os as _os
        import json as _json
        dc_csv = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "Data", "datacenters_housing_merged.csv")
        if not _os.path.exists(dc_csv):
            return _empty_state("datacenters_housing_merged.csv not found", "Place the file in the Data/ folder")
        dc_df = pd.read_csv(dc_csv, dtype={"Zipcode": str})
        by_op = (dc_df.groupby("Operator")["Address"]
                 .nunique().reset_index(name="count")
                 .sort_values("count", ascending=False))
        rows = [{"operator": str(r["Operator"]), "count": int(r["count"])} for _, r in by_op.iterrows()]
        rows_json = _json.dumps(rows)
        max_count = max(r["count"] for r in rows) if rows else 1
        html = f"""
<div style="font-family:monospace;padding:8px 4px;">
  <div style="font-size:10px;color:{TEXT_SEC};margin-bottom:8px;padding:0 4px;">
    Unique facility addresses per operator
  </div>
  <svg id="company-bar-svg" width="100%" style="display:block;"></svg>
</div>
<script>
(function(){{
  const ROWS={rows_json}, MAX={max_count};
  const C_DARK="{DARK_BG}", C_BDR="{BORDER}",
        C_SEC="{TEXT_SEC}",  C_PRI="{TEXT_PRI}",
        C_MAR="{MAROON}",    C_ACC="{TEXT_ACC}";
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
</script>"""
        return ui.HTML(html)

    @render.ui
    def atlas_before_after_price_chart():
        df = _atlas_df()
        metric_choice = input.before_after_metric()
        if metric_choice == "price":
            before_col, after_col = "Housing_Avg_Price_Before_Permit", "Housing_Avg_Price_After_Permit"
            x_axis_label, is_currency = "Average Housing Price", True
            chart_description = (
                "The dumbbell plot compares average housing prices around each data center before and "
                "after the first permit was issued. Each line connects the price in the year before "
                "the permit (blue) and the year after (red). In most cases, the red point appears to "
                "the right of the blue point, indicating that housing prices increased after permitting."
            )
        else:
            before_col, after_col = "HC_Score_Before", "HC_Score_After"
            x_axis_label, is_currency = "Housing Cost Score", False
            chart_description = (
                "The dumbbell plot compares housing cost scores around each data center before and after "
                "the first permit was issued. Each line connects the score before (blue) and after (red). "
                "In many cases, the red point appears slightly to the right of the blue point, suggesting "
                "an increase in housing cost scores after permitting."
            )
        needed = {before_col, after_col, "impact_score"}
        if df.empty or not needed.issubset(df.columns):
            return _empty_state()
        plot_df = df.dropna(subset=list(needed)).copy()
        if plot_df.empty:
            return _empty_state()
        sort_col = "Housing_Change" if metric_choice == "price" else "HC_Score_Change"
        if sort_col in plot_df.columns:
            plot_df = plot_df.dropna(subset=[sort_col]).sort_values(sort_col, ascending=False)
        plot_df = plot_df.reset_index(drop=True)
        import json as _json
        chart_rows = []
        for _, r in plot_df.iterrows():
            op   = str(r.get("Operator", "Unknown"))[:26]
            zip_ = str(r.get("Zipcode", "")).strip()
            label = f"{op} ({zip_})" if zip_ else op
            pb, pa = float(r[before_col]), float(r[after_col])
            imp    = float(r["impact_score"])
            pct    = (pa - pb) / (pb or 1) * 100
            chart_rows.append({
                "label":      label,
                "before":     round(pb, 3),
                "after":      round(pa, 3),
                "before_fmt": fmt_number(pb, is_price=is_currency, decimals=None if is_currency else 3),
                "after_fmt":  fmt_number(pa, is_price=is_currency, decimals=None if is_currency else 3),
                "pct":        round(pct, 1),
                "impact":     round(imp, 3),
            })
        pct_up  = sum(1 for r in chart_rows if r["after"] >= r["before"]) / len(chart_rows) * 100
        ann_col = "#4ade80" if pct_up >= 50 else "#f87171"
        rows_json = _json.dumps(chart_rows)
        html = f"""
<div style="display:flex;flex-direction:column;height:100%;font-family:monospace;">
  <div style="font-family:'DM Sans',sans-serif;font-size:12px;color:{TEXT_SEC};
      line-height:1.7;padding:6px 8px 4px;flex-shrink:0;">{chart_description}</div>
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
</script>"""
        return ui.HTML(html)

    @render.ui
    def atlas_facility_directory_table():
        df = _atlas_df()
        if df.empty:
            return _empty_state()
        WANT = [
            "Operator", "Address", "Zipcode", "CountyName",
            "First_Operation_Permit",
            "Housing_Avg_Price_Before_Permit", "Housing_Avg_Price_After_Permit",
            "Housing_Change", "HC_Score_Change", "impact_score", "impact_z_score",
        ]
        display_cols = [c for c in WANT if c in df.columns] or list(df.columns)
        disp = df[display_cols].copy()
        if "impact_z_score" in disp.columns:
            disp = disp.sort_values("impact_z_score", ascending=False)
        COL_LABELS = {
            "Operator": "Operator", "Address": "Address", "Zipcode": "ZIP",
            "CountyName": "County", "First_Operation_Permit": "Year",
            "Housing_Avg_Price_Before_Permit": "Price Before",
            "Housing_Avg_Price_After_Permit": "Price After",
            "Housing_Change": "Hsg Δ%", "HC_Score_Change": "HC Δ",
            "impact_score": "Impact", "impact_z_score": "Impact Z",
        }
        SCORE_COLS = {"impact_score", "impact_z_score", "HC_Score_Change", "Housing_Change"}
        PRICE_COLS = {"Housing_Avg_Price_Before_Permit", "Housing_Avg_Price_After_Permit"}
        def fmt(val, col):
            if pd.isna(val): return f"<span style='color:{BORDER};'>—</span>"
            if col in SCORE_COLS:
                fv = float(val); c = "#4ade80" if fv > 0 else "#f87171"
                return f"<span style='color:{c};font-weight:600;'>{fv:+.3f}</span>"
            if col in PRICE_COLS:
                return f"<span style='color:{TEXT_SEC};'>{fmt_number(float(val), is_price=True)}</span>"
            if col == "First_Operation_Permit":
                try: return f"<span style='color:{TEXT_SEC};'>{int(float(val))}</span>"
                except: return str(val)
            return f"<span style='color:{TEXT_PRI};'>{val}</span>"
        header = "".join(
            f"<th style='padding:8px 12px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.11em;text-transform:uppercase;text-align:left;"
            f"white-space:nowrap;border-bottom:2px solid {MAROON};position:sticky;top:0;"
            f"background:{PANEL_BG};z-index:1;'>{COL_LABELS.get(c, c)}</th>"
            for c in display_cols
        )
        rows_html = ""
        for i, (_, row) in enumerate(disp.iterrows()):
            bg = CARD_BG if i % 2 == 0 else DARK_BG
            cells = "".join(
                f"<td style='padding:7px 12px;border-bottom:1px solid {BORDER};"
                f"font-family:monospace;font-size:11px;white-space:nowrap;'>{fmt(row[c], c)}</td>"
                for c in display_cols
            )
            rows_html += (
                f"<tr style='background:{bg};transition:background 0.1s;'"
                f" onmouseover=\"this.style.background='#2d333b'\""
                f" onmouseout=\"this.style.background='{bg}'\">{cells}</tr>"
            )
        if not rows_html:
            return _empty_state("No rows to display", "")
        return ui.HTML(f"""
        <div style="overflow:auto;max-height:520px;">
          <table style="width:100%;border-collapse:collapse;min-width:600px;">
            <thead><tr>{header}</tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>""")

    @render.ui
    def metric_selector():
        group = input.metric_group()
        col_map = {
            "zillow":      ZILLOW_COLS,
            "census":      CENSUS_COLS,
            "centers":     DC_COLS,
            "electricity": ELEC_COLS,
            "water":       WATER_COLS,
            "hhc":         HHC_COLS,
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


    # ── Relationships: grouped selectors ────────────────────────────────────
    @render.ui
    def rel_x_selector():
        groups = [
            ("🏠 Home Values",          ZILLOW_COLS),
            ("👥 Demographics",          CENSUS_COLS),
            ("🏢 Data Centers",          DC_COLS),
            ("⚡ Electricity",           ELEC_COLS),
            ("💧 Water & Sewer",         WATER_COLS),
            ("💰 Housing Cost Burden",   HHC_COLS),
        ]
        default = DC_COLS[1] if DC_COLS else (ALL_NUMERIC[0] if ALL_NUMERIC else None)
        return _grouped_select_html("x_var", groups, default=default)

    @render.ui
    def rel_y_selector():
        groups = [
            ("🏠 Home Values",          ZILLOW_COLS),
            ("👥 Demographics",          CENSUS_COLS),
            ("🏢 Data Centers",          DC_COLS),
            ("⚡ Electricity",           ELEC_COLS),
            ("💧 Water & Sewer",         WATER_COLS),
            ("💰 Housing Cost Burden",   HHC_COLS),
        ]
        default = (ZILLOW_COLS[0] if len(ZILLOW_COLS) > 1
                   else CENSUS_COLS[0] if CENSUS_COLS
                   else (ALL_NUMERIC[1] if len(ALL_NUMERIC) > 1 else None))
        return _grouped_select_html("y_var", groups, default=default)

    # ── Regressions: grouped selectors ──────────────────────────────────────
    @render.ui
    def reg_y_selector():
        groups = [
            ("🏠 Home Values",          ZILLOW_COLS),
            ("👥 Demographics",          CENSUS_COLS),
            ("🏢 Data Centers",          DC_COLS),
            ("⚡ Electricity",           ELEC_COLS),
            ("💧 Water & Sewer",         WATER_COLS),
            ("💰 Housing Cost Burden",   HHC_COLS),
        ]
        default = DC_COLS[1] if DC_COLS else (ALL_NUMERIC[0] if ALL_NUMERIC else None)
        return _grouped_select_html("reg_y", groups, default=default)

    @render.ui
    def reg_x_selector():
        grouped_choices = {}
        labels = {
            "zillow":      "🏠 Home Values",
            "census":      "👥 Demographics",
            "centers":     "🏢 Data Centers",
            "electricity": "⚡ Electricity",
            "water":       "💧 Water & Sewer",
            "hhc":         "💰 Housing Cost Burden",
        }
        for key, cols in [("zillow", ZILLOW_COLS), ("census", CENSUS_COLS),
                          ("centers", DC_COLS), ("electricity", ELEC_COLS),
                          ("water", WATER_COLS), ("hhc", HHC_COLS)]:
            if cols:
                grouped_choices[labels[key]] = {c: c for c in cols}
        default_x = CENSUS_COLS[0] if CENSUS_COLS else (ALL_NUMERIC[1] if len(ALL_NUMERIC)>1 else [])
        return ui.input_selectize(
            "reg_x", None,
            choices=grouped_choices,
            selected=[default_x] if default_x else [],
            multiple=True,
        )

    # ── MAP ───────────────────────────────────────────────────────────────────
    @render.ui
    @reactive.event(input.metric_group, input.show_centers, input.show_illinois,
                    input.show_cook, input.show_chicago, lambda: _resolved_metric())
    def map_plot():
        metric = _resolved_metric()
        group  = _current_group()

        if not metric or metric not in cities_gdf.columns:
            fallback = [c for c in ALL_NUMERIC if c in cities_gdf.columns]
            if not fallback:
                return ui.HTML("")
            metric = fallback[0]
            group  = COL_GROUP.get(metric, "census")

        m = folium.Map(location=MAP_CENTER, zoom_start=8,
                       tiles="OpenStreetMap", prefer_canvas=True)

        colormap, col_min, col_max = make_colormap(cities_gdf[metric], metric, group)
        tt_fields  = TT_FIELDS_BASE  + [metric]
        tt_aliases = TT_ALIASES_BASE + [f"📊 {metric}"]

        def style_fn(feature):
            val = feature["properties"].get(metric)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return {"fillColor": "#1c2128", "color": "#30363d",
                        "weight": 0.4, "fillOpacity": 0.6}
            clamped = max(col_min, min(col_max, float(val)))
            return {"fillColor": colormap(clamped), "color": "#21262d",
                    "weight": 0.6, "fillOpacity": 0.75}

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
                    f"background-color:{CARD_BG};color:{TEXT_PRI};"
                    "font-family:monospace;font-size:12px;padding:9px 13px;"
                    f"border-radius:7px;border:1px solid {BORDER};"
                    "box-shadow:0 4px 16px rgba(0,0,0,0.55);min-width:220px;line-height:1.8;"
                ),
            ),
        ).add_to(m)

        colormap.add_to(m)
        m.get_root().html.add_child(folium.Element(f"""
            <style>
            .legend {{
            background: {CARD_BG} !important; border: 1px solid {BORDER} !important;
            border-radius: 8px !important; color: #ffffff !important;
            font-family: monospace !important; font-size: 11px !important;
            padding: 10px !important;
            }}
            .legend svg text {{ fill: #ffffff !important; }}
            .legend * {{ color: #ffffff !important; }}
            </style>
        """))
        if input.show_illinois() and ILLINOIS_GEOJSON is not None:
            folium.GeoJson(ILLINOIS_GEOJSON,
                style_function=lambda f: {"fillColor":"none","fillOpacity":0.0,"color":"#000000","weight":2},
                interactive=False).add_to(m)
        if input.show_cook() and COOK_COUNTY_GEOJSON is not None:
            folium.GeoJson(COOK_COUNTY_GEOJSON,
                style_function=lambda f: {"fillColor":"none","fillOpacity":0.0,"color":"#ffffff","weight":2},
                interactive=False).add_to(m)
        if input.show_chicago() and CHICAGO_GEOJSON is not None:
            folium.GeoJson(CHICAGO_GEOJSON,
                style_function=lambda f: {"fillColor":"none","fillOpacity":0.0,"color":"#ffffff","weight":2},
                interactive=False).add_to(m)
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
        raw  = [x_var, y_var, "Zip Code", "Total Data Centers"]
        cols = list(dict.fromkeys([c for c in raw if c in cities_df.columns]))
        df   = cities_df[cols].copy().reset_index(drop=True)
        return df.dropna(subset=[x_var, y_var]).reset_index(drop=True), x_var, y_var

    @render.ui
    def scatter_plot():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML(f"""<div class="empty-state">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="{TEXT_SEC}" stroke-width="1.5">
                <circle cx="9" cy="9" r="4"/><circle cx="15" cy="15" r="4"/>
              </svg>
              <div>No data available for this combination</div>
            </div>""")
        x = df[x_var].to_numpy().astype(float)
        y = df[y_var].to_numpy().astype(float)

        fig, ax = plt.subplots(figsize=(9, 5.2))
        setup_ax(ax, fig)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        color_by = input.color_by_dc() and "Total Data Centers" in df.columns
        if color_by:
            dc_vals = pd.to_numeric(df["Total Data Centers"], errors="coerce").fillna(0).to_numpy()
            has_dc  = dc_vals > 0
            ax.scatter(x[~has_dc], y[~has_dc], color="#4895ef", alpha=0.55,
                       edgecolors=DARK_BG, linewidths=0.4, s=48, label="No data center", zorder=3)
            sc = ax.scatter(x[has_dc], y[has_dc], c=dc_vals[has_dc], cmap="plasma",
                            alpha=0.95, edgecolors=TEXT_PRI, linewidths=0.6,
                            s=110, label="Has data center", zorder=4, marker="D",
                            vmin=1, vmax=max(dc_vals.max(), 2))
            cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.01, shrink=0.75)
            cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
            cbar.outline.set_edgecolor(BORDER)
            cbar.set_label("# Data Centers", color=TEXT_SEC, fontsize=8)
            ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI,
                      fontsize=9, framealpha=0.92, loc="upper left")
            if "Zip Code" in df.columns:
                top_idx = np.argsort(dc_vals)[-5:]
                for i in top_idx:
                    if dc_vals[i] > 0:
                        ax.annotate(str(df["Zip Code"].iloc[i]),
                            xy=(x[i], y[i]), xytext=(5, 3), textcoords="offset points",
                            fontsize=7, color=TEXT_ACC, fontfamily="monospace", alpha=0.85)
        else:
            from scipy.stats import gaussian_kde
            try:
                xy_stack = np.vstack([x, y])
                kde_vals  = gaussian_kde(xy_stack)(xy_stack)
                order     = kde_vals.argsort()
                sc = ax.scatter(x[order], y[order], c=kde_vals[order], cmap="plasma",
                                alpha=0.78, edgecolors="none", s=52, zorder=3)
                cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.01, shrink=0.75)
                cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
                cbar.outline.set_edgecolor(BORDER)
                cbar.set_label("Point density", color=TEXT_SEC, fontsize=8)
            except Exception:
                ax.scatter(x, y, color="#4895ef", alpha=0.65,
                           edgecolors=DARK_BG, linewidths=0.3, s=52, zorder=3)

        try:
            coef = np.polyfit(x, y, 1)
            xl   = np.linspace(x.min(), x.max(), 200)
            yl   = np.poly1d(coef)(xl)
            ax.plot(xl, yl, color=TEXT_ACC, linewidth=2, linestyle="--", alpha=0.9, zorder=5)
            resid = y - np.poly1d(coef)(x)
            se    = resid.std()
            ax.fill_between(xl, yl - se, yl + se, color=TEXT_ACC, alpha=0.08, zorder=4)
        except Exception:
            pass

        corr = float(np.corrcoef(x, y)[0, 1])
        corr_col = "#4ade80" if abs(corr) > 0.5 else ("#facc15" if abs(corr) > 0.25 else "#f87171")
        ax.annotate(f"r = {corr:+.3f}", xy=(0.97, 0.05), xycoords="axes fraction", ha="right",
                    color=corr_col, fontsize=11, fontfamily="monospace", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.45", facecolor=DARK_BG, edgecolor=corr_col, alpha=0.92, linewidth=1.2))

        def short_label(s, n=40): return s if len(s) <= n else s[:n-1]+"…"
        ax.set_xlabel(short_label(x_var), color=TEXT_SEC, fontsize=10, labelpad=10)
        ax.set_ylabel(short_label(y_var), color=TEXT_SEC, fontsize=10, labelpad=10)

        # Smart axis number formatting
        ax.xaxis.set_major_formatter(smart_axis_formatter(x_var))
        ax.yaxis.set_major_formatter(smart_axis_formatter(y_var))
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)

        ax.grid(color=BORDER, linewidth=0.35, linestyle="--", alpha=0.5)
        plt.tight_layout(pad=1.4)
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def dist_plot():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML(f"<div class='empty-state'><div>No data available.</div></div>")
        from scipy.stats import gaussian_kde as _kde
        fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
        fig.patch.set_facecolor(DARK_BG)
        palette = [("#60a5fa", "#3b82f6"), (TEXT_ACC, "#ca8a04")]
        for ax, var, (fill_col, line_col) in zip(axes, [x_var, y_var], palette):
            vals = df[var].dropna().to_numpy().astype(float)
            setup_ax(ax, fig)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            n_bins = min(28, max(10, len(vals)//4))
            counts, bins, patches = ax.hist(vals, bins=n_bins, color=fill_col,
                                            alpha=0.35, edgecolor=DARK_BG, linewidth=0.3)
            try:
                xkde = np.linspace(vals.min(), vals.max(), 300)
                ykde = _kde(vals)(xkde)
                scale = counts.max() / ykde.max() if ykde.max() > 0 else 1
                ax.plot(xkde, ykde * scale, color=line_col, linewidth=2.2, zorder=5)
                ax.fill_between(xkde, ykde * scale, alpha=0.12, color=line_col)
            except Exception:
                pass
            mean_v   = float(vals.mean())
            median_v = float(np.median(vals))
            ax.axvline(mean_v,   color=TEXT_ACC,   linewidth=1.6, linestyle="--",
                       label=f"mean  {fmt_number(mean_v)}", zorder=6)
            ax.axvline(median_v, color="#a78bfa", linewidth=1.4, linestyle=":",
                       label=f"median {fmt_number(median_v)}", zorder=6)
            short_title = var if len(var) <= 32 else var[:31]+"…"
            ax.set_title(short_title, color=TEXT_PRI, fontsize=9,
                         fontfamily="monospace", pad=9, fontweight="500")
            ax.tick_params(colors=TEXT_SEC, labelsize=8)
            ax.set_ylabel("Count", color=TEXT_SEC, fontsize=8)
            # Smart formatting
            ax.xaxis.set_major_formatter(smart_axis_formatter(var))
            plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
            ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI,
                      fontsize=8, framealpha=0.92)
        plt.tight_layout(pad=1.5)
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def summary_stats():
        df, x_var, y_var = plot_data()
        if df.empty or not x_var:
            return ui.HTML(f"<div class='empty-state'><div>No data available.</div></div>")
        x    = df[x_var].to_numpy().astype(float)
        y    = df[y_var].to_numpy().astype(float)
        corr = float(np.corrcoef(x, y)[0, 1])
        n    = len(df)

        abs_r = abs(corr)
        if abs_r > 0.7:
            strength, strength_col = "strong", "#4ade80"
        elif abs_r > 0.4:
            strength, strength_col = "moderate", "#facc15"
        elif abs_r > 0.2:
            strength, strength_col = "weak", "#fb923c"
        else:
            strength, strength_col = "very weak or no", "#f87171"

        direction = "positive" if corr > 0 else "negative"
        dir_arrow = "↑" if corr > 0 else "↓"

        xn = x_var.split("(")[0].strip()
        yn = y_var.split("(")[0].strip()

        if abs_r > 0.2:
            if corr > 0:
                interp = (f"ZIP codes with higher <b>{xn}</b> tend to also have "
                          f"higher <b>{yn}</b>. The relationship is {strength}.")
            else:
                interp = (f"ZIP codes with higher <b>{xn}</b> tend to have "
                          f"lower <b>{yn}</b>. The relationship is {strength}.")
        else:
            interp = (f"There is little to no linear relationship between "
                      f"<b>{xn}</b> and <b>{yn}</b> across ZIP codes.")

        skew_x = float(((x - x.mean())**3).mean() / (x.std()**3 + 1e-9))
        skew_note_x = " (right-skewed — a few very high ZIPs pull the mean up)" if skew_x > 1 else \
                      " (left-skewed)" if skew_x < -1 else ""

        def row(label, xv, yv, highlight=False):
            bg = f"background:rgba(14,116,144,0.07);" if highlight else ""
            return (
                f"<tr style='border-bottom:1px solid {BORDER};{bg}'>"
                f"<td style='padding:7px 12px;color:{TEXT_SEC};font-family:monospace;font-size:11px;'>{label}</td>"
                f"<td style='padding:7px 12px;color:{TEXT_ACC};text-align:right;font-family:monospace;font-size:11px;'>{xv}</td>"
                f"<td style='padding:7px 12px;color:#a78bfa;text-align:right;font-family:monospace;font-size:11px;'>{yv}</td>"
                f"</tr>"
            )

        rows_html = "".join([
            row("Observations", str(n), str(n), highlight=True),
            row("Mean",   fmt_number(x.mean()),          fmt_number(y.mean())),
            row("Median", fmt_number(float(np.median(x))), fmt_number(float(np.median(y)))),
            row("Std Dev",fmt_number(x.std()),            fmt_number(y.std())),
            row("Min",    fmt_number(x.min()),             fmt_number(y.min())),
            row("Max",    fmt_number(x.max()),             fmt_number(y.max())),
        ])

        def short(s, n=22):
            s = s.split("(")[0].strip()
            return s if len(s) <= n else s[:n-1]+"…"

        html = f"""
        <div style="padding:4px;font-family:'DM Sans',sans-serif;">
          <div style="margin-bottom:14px;padding:16px 18px;
                      background:linear-gradient(135deg,{CARD_BG},{DARK_BG});
                      border-radius:10px;border-left:4px solid {strength_col};
                      box-shadow:0 2px 12px rgba(0,0,0,0.3);">
            <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                        color:{TEXT_SEC};letter-spacing:0.14em;text-transform:uppercase;
                        margin-bottom:6px;">Pearson Correlation</div>
            <div style="display:flex;align-items:baseline;gap:12px;">
              <span style="font-size:32px;font-weight:700;color:{strength_col};
                           font-family:'IBM Plex Mono',monospace;line-height:1;
                           letter-spacing:-0.02em;">
                r = {corr:+.3f}
              </span>
              <span style="font-size:13px;color:{strength_col};font-weight:600;">
                {dir_arrow} {strength} {direction}
              </span>
            </div>
          </div>
          <div style="margin-bottom:14px;padding:12px 16px;
                      background:rgba(34,211,238,0.06);
                      border:1px solid rgba(34,211,238,0.18);
                      border-radius:8px;font-size:13px;
                      color:{TEXT_PRI};line-height:1.65;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         color:{TEXT_ACC};letter-spacing:0.1em;text-transform:uppercase;
                         display:block;margin-bottom:5px;">✦ Interpretation</span>
            {interp}
            {'<br><span style="font-size:11px;color:'+TEXT_SEC+';">Distribution note: '+xn+skew_note_x+'.</span>' if skew_note_x else ''}
          </div>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid {MAROON};">
                <th style="padding:7px 12px;color:{TEXT_SEC};text-align:left;
                           font-size:9px;font-family:monospace;letter-spacing:0.1em;
                           text-transform:uppercase;">Statistic</th>
                <th style="padding:7px 12px;color:{TEXT_ACC};text-align:right;
                           font-size:9px;font-family:monospace;max-width:120px;">
                  {short(x_var)}</th>
                <th style="padding:7px 12px;color:#a78bfa;text-align:right;
                           font-size:9px;font-family:monospace;max-width:120px;">
                  {short(y_var)}</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
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
                f"<div class='empty-state'><div>Select at least one regressor to run the model.</div></div>"
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
            if pv < 0.001: return "***"
            if pv < 0.01:  return "**"
            if pv < 0.05:  return "*"
            if pv < 0.1:   return "·"
            return ""

        def pval_color(pv):
            if np.isnan(pv): return TEXT_SEC
            if pv < 0.05: return "#4ade80"
            if pv < 0.1:  return "#facc15"
            return "#f87171"

        coef_rows = ""
        for name, c, s, ti, pv in zip(coef_names, coefs, se, t, p):
            coef_rows += (
                f"<tr style='border-bottom:1px solid {BORDER};transition:background 0.1s;'"
                f" onmouseover=\"this.style.background='rgba(14,116,144,0.08)'\""
                f" onmouseout=\"this.style.background='transparent'\">"
                f"<td style='padding:7px 10px;color:{TEXT_ACC};font-family:monospace;font-size:11px;'>{name}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_PRI};text-align:right;font-family:monospace;font-size:11px;'>{fmt_number(c, decimals=4)}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_SEC};text-align:right;font-family:monospace;font-size:11px;'>{fmt_number(s, decimals=4)}</td>"
                f"<td style='padding:7px 10px;color:{TEXT_SEC};text-align:right;font-family:monospace;font-size:11px;'>{ti:,.3f}</td>"
                f"<td style='padding:7px 10px;color:{pval_color(pv)};text-align:right;font-family:monospace;font-size:11px;'>"
                f"{'<0.001' if pv < 0.001 else f'{pv:.3f}'} {sig(pv)}</td>"
                f"</tr>"
            )

        r2_color  = "#4ade80" if r2 > 0.5 else ("#facc15" if r2 > 0.25 else "#f87171")
        stat_cards = "".join([
            f"<div style='flex:1;min-width:120px;padding:12px 16px;background:{CARD_BG};"
            f"border-radius:8px;border-top:3px solid {col};"
            f"box-shadow:0 2px 10px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.04);'>"
            f"<div style='font-size:9px;color:{TEXT_SEC};font-family:monospace;"
            f"letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:22px;font-weight:700;color:{col};font-family:monospace;"
            f"letter-spacing:-0.02em;'>{val}</div>"
            f"</div>"
            for label, val, col in [
                ("R²",      f"{r2:.4f}",    r2_color),
                ("Adj. R²", f"{r2_adj:.4f}", r2_color),
                ("RMSE",    fmt_number(rmse), TEXT_ACC),
                ("N",       str(n),         TEXT_SEC),
            ]
        ])

        r2_qual = ("strong — the model explains most variation in the outcome" if r2 > 0.6
                   else "moderate — the model captures some but not all variation" if r2 > 0.3
                   else "weak — the predictors explain little of the outcome's variation")
        r2_col2 = "#4ade80" if r2 > 0.6 else ("#facc15" if r2 > 0.3 else "#f87171")
        yn_short = y_var.split("(")[0].strip()

        sig_pos = [(x_vars[i-1] if coef_names[i]!="Intercept" else None, coefs[i], p[i])
                   for i, name in enumerate(coef_names)
                   if name != "Intercept" and not np.isnan(p[i]) and p[i] < 0.05 and coefs[i] > 0]
        sig_neg = [(x_vars[i-1] if coef_names[i]!="Intercept" else None, coefs[i], p[i])
                   for i, name in enumerate(coef_names)
                   if name != "Intercept" and not np.isnan(p[i]) and p[i] < 0.05 and coefs[i] < 0]
        sig_pos = [(n2,c2,p2) for n2,c2,p2 in sig_pos if n2]
        sig_neg = [(n2,c2,p2) for n2,c2,p2 in sig_neg if n2]

        interp_lines = []
        if sig_pos:
            names_pos = ", ".join(f"<b>{v.split('(')[0].strip()}</b>" for v,c2,p2 in sig_pos[:3])
            interp_lines.append(f"↑ {names_pos} are significantly associated with <b>higher</b> {yn_short} (p&lt;0.05).")
        if sig_neg:
            names_neg = ", ".join(f"<b>{v.split('(')[0].strip()}</b>" for v,c2,p2 in sig_neg[:3])
            interp_lines.append(f"↓ {names_neg} are significantly associated with <b>lower</b> {yn_short} (p&lt;0.05).")
        if not sig_pos and not sig_neg:
            interp_lines.append("No predictors reach statistical significance at the 5% level.")
        interp_lines.append(f"The model uses {n} ZIP codes and explains <b>{r2*100:.1f}%</b> of variation in {yn_short}.")
        interp_html = "<br>".join(interp_lines)

        html = f"""
        <div style="padding:4px;font-family:'DM Sans',sans-serif;">
          <div style="display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;">{stat_cards}</div>
          <div style="margin-bottom:16px;padding:13px 16px;
                      background:rgba(34,211,238,0.06);
                      border:1px solid rgba(34,211,238,0.18);
                      border-radius:8px;font-size:13px;
                      color:{TEXT_PRI};line-height:1.75;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         color:{TEXT_ACC};letter-spacing:0.1em;text-transform:uppercase;
                         display:block;margin-bottom:6px;">✦ What this means</span>
            <span style="color:{r2_col2};font-weight:600;">R² = {r2:.3f}</span>
            — fit quality is <em>{r2_qual}</em>.<br>
            {interp_html}
          </div>
          <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;min-width:480px;">
            <thead>
              <tr style="border-bottom:2px solid {MAROON};background:{PANEL_BG};">
                <th style="padding:8px 12px;color:{TEXT_SEC};text-align:left;font-size:9px;
                           font-family:monospace;letter-spacing:0.1em;text-transform:uppercase;
                           position:sticky;top:0;background:{PANEL_BG};">Variable</th>
                <th style="padding:8px 12px;color:{TEXT_SEC};text-align:right;font-size:9px;
                           font-family:monospace;position:sticky;top:0;background:{PANEL_BG};">Coef</th>
                <th style="padding:8px 12px;color:{TEXT_SEC};text-align:right;font-size:9px;
                           font-family:monospace;position:sticky;top:0;background:{PANEL_BG};">Std Err</th>
                <th style="padding:8px 12px;color:{TEXT_SEC};text-align:right;font-size:9px;
                           font-family:monospace;position:sticky;top:0;background:{PANEL_BG};">t-stat</th>
                <th style="padding:8px 12px;color:{TEXT_SEC};text-align:right;font-size:9px;
                           font-family:monospace;position:sticky;top:0;background:{PANEL_BG};">p-value</th>
              </tr>
            </thead>
            <tbody>{coef_rows}</tbody>
          </table>
          </div>
          <div style="margin-top:10px;font-size:10px;color:{TEXT_SEC};
                      font-family:monospace;padding:0 2px;">
            Significance codes:
            <span style="color:#4ade80;">***</span> p&lt;0.001 &nbsp;
            <span style="color:#86efac;">**</span> p&lt;0.01 &nbsp;
            <span style="color:#facc15;">*</span> p&lt;0.05 &nbsp;
            <span style="color:{TEXT_SEC};">·</span> p&lt;0.1
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
        y_hat     = X @ coefs
        residuals = y - y_hat
        ss_res = float(np.sum(residuals**2))
        ss_tot = float(np.sum((y - y.mean())**2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        fig, ax = plt.subplots(figsize=(6, 4.2))
        setup_ax(ax, fig)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        res_abs  = np.abs(residuals)
        res_norm = mcolors.Normalize(vmin=0, vmax=np.percentile(res_abs, 95))
        sc = ax.scatter(y_hat, y, c=res_abs, cmap="YlOrRd", norm=res_norm,
                        alpha=0.78, edgecolors=DARK_BG, linewidths=0.4, s=50, zorder=3)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.028, pad=0.01, shrink=0.8)
        cbar.ax.tick_params(colors=TEXT_SEC, labelsize=7)
        cbar.outline.set_edgecolor(BORDER)
        cbar.set_label("|residual|", color=TEXT_SEC, fontsize=7.5)

        mn, mx = min(y.min(), y_hat.min()), max(y.max(), y_hat.max())
        ax.plot([mn, mx], [mn, mx], color=TEXT_ACC, linewidth=1.8,
                linestyle="--", alpha=0.9, zorder=5, label="y = ŷ  (perfect fit)")

        r2_col = "#4ade80" if r2 > 0.5 else ("#facc15" if r2 > 0.25 else "#f87171")
        ax.annotate(f"R² = {r2:.3f}", xy=(0.05, 0.93), xycoords="axes fraction",
                    color=r2_col, fontsize=10, fontfamily="monospace", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.4", fc=DARK_BG, ec=r2_col, alpha=0.92, lw=1.2))

        short_y = y_var if len(y_var) <= 30 else y_var[:29]+"…"
        ax.set_xlabel("Fitted  ŷ", color=TEXT_SEC, fontsize=9, labelpad=8)
        ax.set_ylabel(f"Actual  {short_y}", color=TEXT_SEC, fontsize=9, labelpad=8)
        ax.xaxis.set_major_formatter(smart_axis_formatter(y_var))
        ax.yaxis.set_major_formatter(smart_axis_formatter(y_var))
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
        ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI, fontsize=8)
        ax.grid(color=BORDER, linewidth=0.35, linestyle="--", alpha=0.45)
        plt.tight_layout(pad=1.3)
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

        fig, ax = plt.subplots(figsize=(6, 4.2))
        setup_ax(ax, fig)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        pos = residuals >= 0
        ax.scatter(y_hat[pos],  residuals[pos],  color="#4ade80", alpha=0.65,
                   edgecolors=DARK_BG, linewidths=0.3, s=44, zorder=3, label="Over-predicted")
        ax.scatter(y_hat[~pos], residuals[~pos], color="#f87171", alpha=0.65,
                   edgecolors=DARK_BG, linewidths=0.3, s=44, zorder=3, label="Under-predicted")

        try:
            sort_idx = np.argsort(y_hat)
            xsrt, rsrt = y_hat[sort_idx], residuals[sort_idx]
            window = max(3, len(xsrt)//6)
            smooth = np.convolve(rsrt, np.ones(window)/window, mode="valid")
            xsmooth = xsrt[window//2: window//2 + len(smooth)]
            ax.plot(xsmooth, smooth, color=TEXT_ACC, linewidth=1.6, alpha=0.7, zorder=5)
        except Exception:
            pass

        ax.axhline(0, color=BORDER, linewidth=1.2, linestyle="-", alpha=0.7, zorder=4)
        sd = residuals.std()
        ax.axhline( sd, color=BORDER, linewidth=0.8, linestyle=":", alpha=0.5)
        ax.axhline(-sd, color=BORDER, linewidth=0.8, linestyle=":", alpha=0.5)
        ax.annotate("±1 SD", xy=(ax.get_xlim()[1], sd), xytext=(-4, 3),
                    textcoords="offset points", color=TEXT_SEC, fontsize=7,
                    fontfamily="monospace", ha="right", alpha=0.6)

        ax.set_xlabel("Fitted  ŷ",  color=TEXT_SEC, fontsize=9, labelpad=8)
        ax.set_ylabel("Residuals",  color=TEXT_SEC, fontsize=9, labelpad=8)
        ax.xaxis.set_major_formatter(smart_axis_formatter(y_var))
        ax.yaxis.set_major_formatter(smart_axis_formatter("residuals"))
        plt.setp(ax.get_xticklabels(), rotation=20, ha="right", fontsize=8)
        ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI,
                  fontsize=8, framealpha=0.9)
        ax.grid(color=BORDER, linewidth=0.35, linestyle="--", alpha=0.45)
        plt.tight_layout(pad=1.3)
        return ui.HTML(fig_to_html(fig))

    # ── PCA ───────────────────────────────────────────────────────────────────
    @reactive.Calc
    def _pca_result():
        try:
            vars_ = list(input.pca_vars())
        except:
            return None
        if len(vars_) < 2:
            return None

        cols = [v for v in vars_ if v in cities_df.columns]
        if len(cols) < 2:
            return None

        df = cities_df[cols + (["Zip Code"] if "Zip Code" in cities_df.columns else [])].copy()
        df = df.dropna(subset=cols).reset_index(drop=True)
        X  = df[cols].to_numpy().astype(float)

        if input.pca_scale():
            mu  = X.mean(axis=0)
            std = X.std(axis=0)
            std[std == 0] = 1
            X = (X - mu) / std

        X_c = X - X.mean(axis=0)
        U, s, Vt = np.linalg.svd(X_c, full_matrices=False)
        eigenvals  = (s ** 2) / (X_c.shape[0] - 1)
        expl_var   = eigenvals / eigenvals.sum()
        scores     = X_c @ Vt.T
        loadings   = Vt.T

        return {
            "df":        df,
            "cols":      cols,
            "scores":    scores,
            "loadings":  loadings,
            "expl_var":  expl_var,
            "eigenvals": eigenvals,
            "n_comp":    min(len(cols), X_c.shape[0]),
        }

    def _no_data_msg(msg="Select ≥ 2 variables to run PCA."):
        return ui.HTML(
            f"<div class='empty-state'><div>{msg}</div></div>"
        )

    @render.ui
    def pca_scree():
        res = _pca_result()
        if res is None:
            return _no_data_msg()

        expl = res["expl_var"]
        n    = len(expl)
        labels = [f"PC{i+1}" for i in range(n)]
        cumul  = np.cumsum(expl)

        fig, ax = plt.subplots(figsize=(5, 3.8))
        setup_ax(ax, fig)
        colors_bar = plt.get_cmap("plasma")(np.linspace(0.2, 0.85, n))
        bars = ax.bar(labels, expl * 100, color=colors_bar,
                      edgecolor=DARK_BG, linewidth=0.5, zorder=3)
        ax2 = ax.twinx()
        ax2.set_facecolor(CARD_BG)
        ax2.plot(labels, cumul * 100, color=TEXT_ACC, linewidth=2,
                 marker="o", markersize=5, markerfacecolor=TEXT_ACC,
                 markeredgecolor=DARK_BG, markeredgewidth=1, zorder=4)
        ax2.axhline(80, color=TEXT_SEC, linewidth=0.8, linestyle=":", alpha=0.6)
        ax2.set_ylabel("Cumulative %", color=TEXT_SEC, fontsize=8)
        ax2.tick_params(colors=TEXT_SEC, labelsize=8)
        ax2.spines["right"].set_edgecolor(BORDER)
        ax2.set_ylim(0, 105)
        for bar, v in zip(bars, expl):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{v*100:.1f}%", ha="center", va="bottom",
                    color=TEXT_PRI, fontsize=7.5, fontfamily="monospace")
        ax.set_ylabel("Explained Variance %", color=TEXT_SEC, fontsize=9)
        ax.set_ylim(0, max(expl) * 100 * 1.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout(pad=1.2)

        chart_html = fig_to_html(fig)

        diffs = np.diff(expl)
        elbow = int(np.argmax(np.abs(diffs[1:]) < 0.02)) + 2 if len(diffs) > 1 else 1
        n80 = int(np.searchsorted(cumul, 0.80)) + 1
        note = (f"The scree plot suggests retaining <b>{min(elbow, n80)} components</b> "
                f"(covers ~{cumul[min(elbow,n80)-1]*100:.0f}% of variance). "
                f"Cross the 80% mark at PC{n80}.")
        note_html = f"""
        <div style="padding:10px 14px 4px;font-family:'DM Sans',sans-serif;
                    font-size:12px;color:{TEXT_SEC};line-height:1.6;
                    border-top:1px solid {BORDER};margin-top:6px;">
          <span style="color:{TEXT_ACC};font-family:monospace;font-size:9px;
                       letter-spacing:0.1em;text-transform:uppercase;">✦ Note</span><br>
          {note}
        </div>"""
        return ui.HTML(chart_html + note_html)

    @render.ui
    def pca_scores():
        res = _pca_result()
        if res is None:
            return _no_data_msg()

        scores   = res["scores"]
        expl     = res["expl_var"]
        df       = res["df"]
        pc1, pc2 = scores[:, 0], scores[:, 1]

        try:
            cvar = input.pca_color_var()
        except:
            cvar = "none"

        fig, ax = plt.subplots(figsize=(7, 5.2))
        setup_ax(ax, fig)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        if cvar != "none" and cvar in df.columns:
            cvals = pd.to_numeric(df[cvar], errors="coerce").to_numpy()
            mask  = ~np.isnan(cvals)
            sc = ax.scatter(pc1[mask], pc2[mask], c=cvals[mask], cmap="plasma",
                            alpha=0.78, edgecolors=DARK_BG, linewidths=0.35,
                            s=56, zorder=3)
            if (~mask).sum() > 0:
                ax.scatter(pc1[~mask], pc2[~mask], color=BORDER, alpha=0.35,
                           edgecolors="none", s=28, zorder=2)
            cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.01, shrink=0.8)
            cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
            cbar.outline.set_edgecolor(BORDER)
            short_cv = cvar if len(cvar) <= 28 else cvar[:27]+"…"
            cbar.set_label(short_cv, color=TEXT_SEC, fontsize=8)
        else:
            dist = np.sqrt(pc1**2 + pc2**2)
            sc = ax.scatter(pc1, pc2, c=dist, cmap="plasma",
                            alpha=0.72, edgecolors=DARK_BG, linewidths=0.3, s=52, zorder=3)
            cbar = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.01, shrink=0.8)
            cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
            cbar.outline.set_edgecolor(BORDER)
            cbar.set_label("Distance from origin", color=TEXT_SEC, fontsize=8)

        if "Zip Code" in df.columns:
            dist  = np.sqrt(pc1**2 + pc2**2)
            top_n = min(6, len(dist))
            top_i = np.argsort(dist)[-top_n:]
            for i in top_i:
                ax.annotate(str(df["Zip Code"].iloc[i]),
                    xy=(pc1[i], pc2[i]), xytext=(4, 3), textcoords="offset points",
                    fontsize=7, color=TEXT_ACC, fontfamily="monospace", alpha=0.85,
                    bbox=dict(boxstyle="round,pad=0.2", fc=DARK_BG, ec=BORDER,
                              alpha=0.7, linewidth=0.5))

        ax.axhline(0, color=BORDER, linewidth=0.8, linestyle="--", alpha=0.5)
        ax.axvline(0, color=BORDER, linewidth=0.8, linestyle="--", alpha=0.5)
        ax.set_xlabel(f"PC1  ({expl[0]*100:.1f}% explained)", color=TEXT_SEC, fontsize=10, labelpad=8)
        ax.set_ylabel(f"PC2  ({expl[1]*100:.1f}% explained)", color=TEXT_SEC, fontsize=10, labelpad=8)
        ax.grid(color=BORDER, linewidth=0.3, linestyle="--", alpha=0.4)
        plt.tight_layout(pad=1.3)
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def pca_loadings():
        res = _pca_result()
        if res is None:
            return _no_data_msg()

        loadings = res["loadings"]
        cols     = res["cols"]
        expl     = res["expl_var"]
        n_show   = min(2, loadings.shape[1])

        def shorten(s):
            replacements = {
                "Median Home Value": "Home Value",
                "Electricity: % Paying": "Elec %",
                "Water & Sewer: % Paying": "Water %",
                "Broadband Adoption Rate (%)": "Broadband %",
                "Renter-Occupied Share (%)": "Renter Share",
                "Population Density (per sq km)": "Pop Density",
                "Median Household Income": "HH Income",
                "Data Centers per 100,000 Residents": "DC per 100k",
                "Total Data Centers": "Total DCs",
                "Unemployment Rate (%)": "Unemployment",
                "Poverty Rate (%)": "Poverty Rate",
                "Household Cost Score": "HHC Score",
            }
            for k, v in replacements.items():
                s = s.replace(k, v)
            return s[:32]

        short = [shorten(c) for c in cols]
        x     = np.arange(len(cols))
        width = 0.36

        fig, ax = plt.subplots(figsize=(8, max(3.8, len(cols) * 0.46)))
        setup_ax(ax, fig)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for i in range(n_show):
            offset = (i - (n_show - 1) / 2) * width
            vals_i = loadings[:, i]
            bar_colors = [("#4ade80" if v > 0 else "#f87171") if i == 0
                          else ("#60a5fa" if v > 0 else "#f97316")
                          for v in vals_i]
            bars = ax.barh(x + offset, vals_i, height=width,
                           color=bar_colors, alpha=0.82,
                           edgecolor=DARK_BG, linewidth=0.3,
                           label=f"PC{i+1}  ({expl[i]*100:.1f}% var)")
            for bar, v in zip(bars, vals_i):
                if abs(v) > 0.15:
                    ax.text(v + (0.01 if v >= 0 else -0.01), bar.get_y() + bar.get_height()/2,
                            f"{v:.2f}", va="center",
                            ha="left" if v >= 0 else "right",
                            fontsize=7, color=TEXT_SEC, fontfamily="monospace")

        ax.set_yticks(x)
        ax.set_yticklabels(short, fontsize=8.5, color=TEXT_PRI)
        ax.axvline(0, color=BORDER, linewidth=1, alpha=0.8)
        ax.set_xlabel("Loading magnitude", color=TEXT_SEC, fontsize=9, labelpad=8)
        ax.legend(facecolor=CARD_BG, edgecolor=BORDER, labelcolor=TEXT_PRI,
                  fontsize=9, framealpha=0.92, loc="lower right")
        ax.invert_yaxis()
        ax.grid(axis="x", color=BORDER, linewidth=0.3, linestyle="--", alpha=0.4)
        plt.tight_layout(pad=1.3)
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def pca_corr_heat():
        res = _pca_result()
        if res is None:
            return _no_data_msg()

        loadings = res["loadings"]
        expl     = res["expl_var"]
        cols     = res["cols"]
        n_show   = min(5, loadings.shape[1])
        short    = [c[:22] for c in cols]

        corr_mat = loadings[:, :n_show]

        fig, ax = plt.subplots(figsize=(max(4, n_show * 0.9), max(3.5, len(cols) * 0.45)))
        fig.patch.set_facecolor(DARK_BG)
        ax.set_facecolor(CARD_BG)

        cmap = plt.get_cmap("RdYlGn")
        im = ax.imshow(corr_mat, aspect="auto", cmap=cmap, vmin=-1, vmax=1)
        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cbar.ax.tick_params(colors=TEXT_SEC, labelsize=8)
        cbar.outline.set_edgecolor(BORDER)

        ax.set_xticks(range(n_show))
        ax.set_xticklabels([f"PC{i+1}\n{expl[i]*100:.1f}%" for i in range(n_show)],
                           color=TEXT_PRI, fontsize=8.5)
        ax.set_yticks(range(len(cols)))
        ax.set_yticklabels(short, color=TEXT_PRI, fontsize=8.5)
        ax.tick_params(colors=TEXT_SEC)

        for i in range(len(cols)):
            for j in range(n_show):
                val = corr_mat[i, j]
                text_c = "#000" if abs(val) < 0.6 else "#fff"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        color=text_c, fontsize=7.5, fontfamily="monospace")

        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        plt.tight_layout(pad=1.2)
        chart_html = fig_to_html(fig)
        note_html = f"""
        <div style="padding:8px 14px 2px;font-family:'DM Sans',sans-serif;
                    font-size:12px;color:{TEXT_SEC};line-height:1.6;
                    border-top:1px solid {BORDER};margin-top:4px;">
          Cell values show each variable's <b style="color:{TEXT_PRI};">loading</b> on each principal
          component — how much that variable contributes. Values near ±1 (dark cells) indicate
          strong alignment; values near 0 (light cells) indicate little contribution.
        </div>"""
        return ui.HTML(chart_html + note_html)

    @render.ui
    def pca_table():
        res = _pca_result()
        if res is None:
            return _no_data_msg()

        expl     = res["expl_var"]
        eigenvals= res["eigenvals"]
        cumul    = np.cumsum(expl)
        n_show   = min(10, len(expl))

        header = (
            f"<tr style='border-bottom:2px solid {MAROON};'>"
            f"<th style='padding:8px 14px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.12em;text-transform:uppercase;text-align:center;'>Component</th>"
            f"<th style='padding:8px 14px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.12em;text-transform:uppercase;text-align:right;'>Eigenvalue</th>"
            f"<th style='padding:8px 14px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.12em;text-transform:uppercase;text-align:right;'>Explained Var %</th>"
            f"<th style='padding:8px 14px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.12em;text-transform:uppercase;text-align:right;'>Cumulative %</th>"
            f"<th style='padding:8px 14px;color:{TEXT_SEC};font-family:monospace;"
            f"font-size:9px;letter-spacing:0.12em;text-transform:uppercase;text-align:left;'>Bar</th>"
            f"</tr>"
        )

        rows = ""
        for i in range(n_show):
            bar_w  = int(expl[i] * 200)
            bar_color = TEXT_ACC if i < 2 else (MAROON_MID if i < 4 else BORDER)
            cum_color = "#4ade80" if cumul[i] >= 0.8 else ("#facc15" if cumul[i] >= 0.6 else TEXT_PRI)
            rows += (
                f"<tr style='border-bottom:1px solid {BORDER};transition:background 0.1s;'"
                f" onmouseover=\"this.style.background='rgba(14,116,144,0.08)'\""
                f" onmouseout=\"this.style.background='transparent'\">"
                f"<td style='padding:8px 14px;color:{TEXT_ACC};font-family:monospace;"
                f"font-size:11px;text-align:center;font-weight:600;'>PC{i+1}</td>"
                f"<td style='padding:8px 14px;color:{TEXT_PRI};font-family:monospace;"
                f"font-size:11px;text-align:right;'>{eigenvals[i]:.4f}</td>"
                f"<td style='padding:8px 14px;color:{TEXT_PRI};font-family:monospace;"
                f"font-size:11px;text-align:right;'>{expl[i]*100:.2f}%</td>"
                f"<td style='padding:8px 14px;color:{cum_color};font-family:monospace;"
                f"font-size:11px;text-align:right;font-weight:600;'>{cumul[i]*100:.2f}%</td>"
                f"<td style='padding:8px 14px;'>"
                f"<div style='width:{bar_w}px;height:8px;background:{bar_color};"
                f"border-radius:3px;opacity:0.85;'></div></td>"
                f"</tr>"
            )

        n80      = int(np.searchsorted(cumul, 0.80)) + 1
        n60      = int(np.searchsorted(cumul, 0.60)) + 1
        top_var  = expl[0] * 100
        top2_var = expl[:2].sum() * 100 if len(expl) >= 2 else top_var

        if top_var > 50:
            dim_interp = (f"PC1 alone captures <b>{top_var:.1f}%</b> of total variance — "
                          f"a single dominant axis explains most variation across ZIP codes.")
        else:
            dim_interp = (f"Variance is spread across multiple components — "
                          f"PC1 + PC2 together explain <b>{top2_var:.1f}%</b>.")

        html = f"""
        <div style="padding:4px;font-family:'DM Sans',sans-serif;">
          <div style="margin-bottom:14px;padding:13px 16px;
                      background:rgba(34,211,238,0.06);
                      border:1px solid rgba(34,211,238,0.18);
                      border-radius:8px;font-size:13px;
                      color:{TEXT_PRI};line-height:1.7;">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;
                         color:{TEXT_ACC};letter-spacing:0.1em;text-transform:uppercase;
                         display:block;margin-bottom:5px;">✦ Dimensionality</span>
            {dim_interp}<br>
            You need <b>{n60} component{'s' if n60>1 else ''}</b> to reach 60% explained variance,
            and <b>{n80} component{'s' if n80>1 else ''}</b> for 80%.
          </div>
          <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;min-width:380px;">
            <thead>{header}</thead>
            <tbody>{rows}</tbody>
          </table>
          </div>
          <div style="margin-top:10px;font-size:10px;color:{TEXT_SEC};
                      font-family:monospace;padding:0 2px;">
            Cumulative thresholds:
            <span style="color:#facc15;">▌ 60%</span> &nbsp;
            <span style="color:#4ade80;">▌ 80%</span>
            &nbsp;·&nbsp;
            <span style="color:{TEXT_SEC};">Press keys 1–5 to switch tabs quickly</span>
          </div>
        </div>
        """
        return ui.HTML(html)


# =============================================================================
# App
# =============================================================================
www_dir = os.path.join(os.path.dirname(__file__), "Data")
app = App(app_ui, server, static_assets=www_dir)