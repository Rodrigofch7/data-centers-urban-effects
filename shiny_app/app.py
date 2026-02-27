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
import io, base64

# To run use in the terminal: shiny run --reload app.py

# -----------------------------
# UChicago Brand Constants
# -----------------------------
UCHICAGO_MAROON = "#800000"
DARK_BG  = "#0f172a"
CARD_BG  = "#1e293b"
TEXT_COL = "#f1f5f9"
ACC_COL  = "#800000"  # Swapped to Maroon

# -----------------------------
# Load data
# -----------------------------
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

# ── Rename year columns in cities_gdf for the map ────────────────────────────
year_rename   = {str(y): f"Home Value {y}" for y in range(2000, 2026)}
cities_gdf    = cities_gdf.rename(columns=year_rename)
YEAR_COLS_NEW = [f"Home Value {y}" for y in range(2000, 2026)]

# ── Build a clean flat DataFrame using fiona — bypasses geopandas internals ───
with fiona.open(cities_path) as src:
    records = [feat["properties"] for feat in src]
cities_df = pd.DataFrame(records)
cities_df = cities_df.rename(columns=year_rename)

# ── Column groups ─────────────────────────────────────────────────────────────
ZILLOW_COLS = [c for c in YEAR_COLS_NEW if c in cities_df.columns]

CENSUS_COLS = [c for c in [
    "Total Population", "Median Age", "Median Household Income",
    "Median Home Value", "Gini Index", "Broadband %",
    "Poverty %", "Unemployment Rate %", "Renter %",
    "Black Population", "Asian Population", "Hispanic Population",
] if c in cities_df.columns]

DC_COLS = [c for c in ["Total Data Centers"] if c in cities_df.columns]

for col in ZILLOW_COLS + CENSUS_COLS + DC_COLS:
    cities_df[col]  = pd.to_numeric(cities_df[col],  errors="coerce")
    cities_gdf[col] = pd.to_numeric(cities_gdf[col], errors="coerce")

ALL_NUMERIC = ZILLOW_COLS + CENSUS_COLS + DC_COLS

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_colormap(values, metric):
    clean   = values.dropna()
    col_min = float(clean.min())
    col_max = float(clean.max())
    spread  = col_max - col_min
    mean_v  = float(clean.mean())
    if mean_v != 0 and spread / abs(mean_v) < 0.1:
        col_min = float(np.percentile(clean, 2))
        col_max = float(np.percentile(clean, 98))
    colormap         = cm.linear.YlOrRd_09.scale(col_min, col_max)
    colormap.caption = metric
    return colormap, col_min, col_max

def dc_tooltip_html(row):
    zip_code   = str(row.get("ZCTA5CE20", "—") or "—").strip()
    year_built = str(row.get("year_as_datacenter", "—") or "—").strip()
    operator   = str(row.get("operator", "—") or "—").strip()
    facility   = str(row.get("facility", "") or "").strip()

    if zip_code   in ("", "nan"): zip_code   = "—"
    if year_built in ("", "nan"): year_built = "Unknown"
    if operator   in ("", "nan"): operator   = "—"

    header = f"<b>🏢 {facility}</b>" if facility and facility != "nan" else "<b>🏢 Data Center</b>"
    return (
        f"{header}<br>"
        f"<span style='color:#94a3b8;'>ZIP Code:</span> {zip_code}<br>"
        f"<span style='color:#94a3b8;'>Est. Year Built:</span> {year_built}<br>"
        f"<span style='color:#94a3b8;'>Operator:</span> {operator}"
    )

def fig_to_html(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return f'<img src="data:image/png;base64,{b64}" style="width:100%;border-radius:8px;">'

METRIC_GROUP_CHOICES = {}
if ZILLOW_COLS:
    METRIC_GROUP_CHOICES["zillow"]  = "🏠 Zillow Home Values (by year)"
if CENSUS_COLS:
    METRIC_GROUP_CHOICES["census"]  = "👥 Census & Demographics"
if DC_COLS:
    METRIC_GROUP_CHOICES["centers"] = "🏢 Data Centers"

# =============================================================================
# UI
# =============================================================================
app_ui = ui.page_navbar(
    ui.nav_panel(
        "🗺️ Map",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Map Controls", style="color:#f1f5f9;"),
                ui.input_select(
                    "metric_group", "Metric Group",
                    choices=METRIC_GROUP_CHOICES,
                    selected=list(METRIC_GROUP_CHOICES.keys())[0],
                ),
                ui.output_ui("metric_selector"),
                ui.hr(),
                ui.input_checkbox("show_centers", "Show Data Centers", value=True),
                ui.hr(),
                ui.markdown("**Chicago ZIP-level analysis**\n\nSources: Zillow · ACS 2022 · Manual DC inventory"),
                style=f"background:{DARK_BG}; color:{TEXT_COL}; border-right: 2px solid {UCHICAGO_MAROON};",
            ),
            ui.card(
                ui.card_header("Chicago — ZIP Code Choropleth"),
                ui.output_ui("map_plot"),
            ),
        ),
    ),

    ui.nav_panel(
        "📊 Explore Relationships",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Variable Selection", style="color:#f1f5f9;"),
                ui.input_select(
                    "x_var", "X-axis Variable",
                    choices={c: c for c in ALL_NUMERIC},
                    selected=ALL_NUMERIC[0] if ALL_NUMERIC else None,
                ),
                ui.input_select(
                    "y_var", "Y-axis Variable",
                    choices={c: c for c in ALL_NUMERIC},
                    selected=ALL_NUMERIC[1] if len(ALL_NUMERIC) > 1 else ALL_NUMERIC[0],
                ),
                ui.hr(),
                ui.input_checkbox("color_by_dc", "Color by Data Center presence", value=False),
                ui.hr(),
                ui.markdown("Select any two numeric variables to explore their relationship across Chicago ZIP codes."),
                style=f"background:{DARK_BG}; color:{TEXT_COL}; border-right: 2px solid {UCHICAGO_MAROON};",
            ),
            ui.layout_columns(
                ui.card(ui.card_header("Scatter Plot"),          ui.output_ui("scatter_plot")),
                ui.card(ui.card_header("Distributions"),         ui.output_ui("dist_plot")),
                ui.card(ui.card_header("Correlation & Summary"), ui.output_ui("summary_stats")),
                col_widths=(12, 12, 12),
            ),
        ),
    ),

    ui.nav_panel(
        "📈 Data Analysis",
        ui.page_sidebar(
            ui.sidebar(
                ui.h4("Analysis Controls", style="color:#f1f5f9;"),
                ui.hr(),
                ui.markdown("**Coming soon**\n\nAnalysis tools will appear here."),
                style=f"background:{DARK_BG}; color:{TEXT_COL}; border-right: 2px solid {UCHICAGO_MAROON};",
            ),
            ui.card(
                ui.card_header("Data Analysis"),
                ui.div(
                    ui.tags.i(class_="fa fa-chart-line", style=f"font-size:48px; color:{UCHICAGO_MAROON}; margin-bottom:16px;"),
                    ui.h3("Coming Soon", style=f"color:{TEXT_COL}; margin-bottom:8px;"),
                    ui.p("This section is under construction. Data analysis tools and visualizations will be available here.", 
                         style="color:#94a3b8; max-width:400px;"),
                    style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:500px; text-align:center;",
                ),
            ),
        ),
    ),

    ui.nav_spacer(),
    ui.nav_control(
        ui.tags.img(
            src="uchicago_logo.png",
            class_="uchicago-logo-nav"
        )
    ),

    # --- BRANDING & GLOBAL CSS ---
    header=ui.tags.head(
        ui.tags.style(f"""
            /* ── Navbar ── */
            .navbar {{ background-color: {UCHICAGO_MAROON} !important; border-bottom: 2px solid #000; }}
            .navbar-brand {{ flex-shrink: 0; margin-right: 24px; }}
            .navbar-nav .nav-link {{
                color: rgba(255,255,255,0.85) !important;
                font-weight: 500;
                font-size: 15px;
                padding: 0 16px !important;
            }}
            .navbar-nav .nav-link:hover,
            .navbar-nav .nav-link.active {{
                color: #ffffff !important;
                border-bottom: 2px solid #ffffff;
            }}
            .uchicago-logo-nav {{
                height: 42px;
                display: block;
                margin: 0 8px;
            }}
            .navbar-nav.ms-auto {{
                align-items: center;
            }}

            /* ── Full page background ── */
            body, .bslib-page-sidebar, .bslib-sidebar-layout {{
                background-color: {DARK_BG} !important;
            }}

            /* ── Sidebar panel ── */
            .sidebar,
            .bslib-sidebar-layout > .sidebar,
            .bslib-sidebar-layout > .sidebar > .sidebar-content,
            aside.sidebar {{
                background-color: {DARK_BG} !important;
                border-right: 2px solid {UCHICAGO_MAROON} !important;
                color: {TEXT_COL} !important;
            }}

            /* ── Card headers ── */
            .card-header {{
                background-color: {UCHICAGO_MAROON} !important;
                color: #ffffff !important;
                border-bottom: 1px solid #5a0000 !important;
                font-weight: 600;
            }}

            /* ── Cards ── */
            .card {{
                background-color: {CARD_BG} !important;
                border: 1px solid #334155 !important;
            }}

            /* ── All labels in sidebar ── */
            .sidebar label,
            .sidebar .control-label,
            .sidebar .form-check-label,
            .sidebar p,
            .sidebar strong,
            .sidebar h4 {{
                color: {TEXT_COL} !important;
            }}

            /* ── Select / input boxes ── */
            .sidebar .form-select,
            .sidebar .form-control,
            .sidebar select {{
                background-color: {CARD_BG} !important;
                color: {TEXT_COL} !important;
                border: 1px solid {UCHICAGO_MAROON} !important;
            }}

            /* ── Selectize dropdowns ── */
            .sidebar .selectize-input,
            .sidebar .selectize-input input {{
                background-color: {CARD_BG} !important;
                color: {TEXT_COL} !important;
                border: 1px solid {UCHICAGO_MAROON} !important;
                box-shadow: none !important;
            }}
            .sidebar .selectize-dropdown,
            .sidebar .selectize-dropdown .option {{
                background-color: {CARD_BG} !important;
                color: {TEXT_COL} !important;
            }}
            .sidebar .selectize-dropdown .option:hover,
            .sidebar .selectize-dropdown .option.active {{
                background-color: {UCHICAGO_MAROON} !important;
                color: #ffffff !important;
            }}

            /* ── Checkbox ── */
            .sidebar .form-check-input {{
                border-color: {UCHICAGO_MAROON} !important;
                background-color: {CARD_BG} !important;
            }}
            .sidebar .form-check-input:checked {{
                background-color: {UCHICAGO_MAROON} !important;
                border-color: {UCHICAGO_MAROON} !important;
            }}
            .sidebar .form-check-input:focus {{
                box-shadow: 0 0 0 0.2rem rgba(128,0,0,0.35) !important;
            }}

            /* ── HR dividers ── */
            .sidebar hr {{
                border-color: {UCHICAGO_MAROON} !important;
                opacity: 0.5;
            }}
        """)
    ),

    title=ui.tags.span(
        "Chicago Data Center Dashboard",
        style="font-weight: bold; font-size: 22px; color: white; white-space: nowrap;"
    ),
    bg=UCHICAGO_MAROON,
    inverse=True,
)


# =============================================================================
# Server
# =============================================================================
def server(input, output, session):

    @render.ui
    def metric_selector():
        group = input.metric_group()
        if group == "zillow":
            cols = ZILLOW_COLS
        elif group == "census":
            cols = CENSUS_COLS
        else:
            cols = DC_COLS
        if not cols:
            return ui.p("No columns found.", style="color:#f87171;")
        return ui.input_select(
            "metric", "Select Metric",
            choices={c: c for c in cols},
            selected=cols[-1] if group == "zillow" else cols[0],
        )

    @render.ui
    def map_plot():
        metric = input.metric()
        if not metric or metric not in cities_gdf.columns:
            fallback = [c for c in ALL_NUMERIC if c in cities_gdf.columns]
            if not fallback:
                return ui.HTML("")
            metric = fallback[0]

        gdf = cities_gdf.copy()

        tt_fields, tt_aliases = [], []
        if "Zip Code" in gdf.columns:
            tt_fields.append("Zip Code")
            tt_aliases.append("ZIP Code")
        tt_fields.append(metric)
        tt_aliases.append(metric)

        centroids  = gdf.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
        center_lat = centroids.y.mean()
        center_lon = centroids.x.mean()

        m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="CartoDB dark_matter")
        colormap, col_min, col_max = make_colormap(gdf[metric], metric)

        def style_fn(feature):
            val = feature["properties"].get(metric)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return {"fillColor": "#333333", "color": "#444444", "weight": 0.5, "fillOpacity": 0.4}
            clamped = max(col_min, min(col_max, val))
            return {"fillColor": colormap(clamped), "color": "#111111", "weight": 0.5, "fillOpacity": 0.75}

        def highlight_fn(feature):
            return {"fillOpacity": 0.95, "weight": 2, "color": "white"}

        folium.GeoJson(
            gdf.__geo_interface__,
            style_function=style_fn,
            highlight_function=highlight_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=tt_fields, aliases=tt_aliases,
                localize=True, sticky=True,
                style=(
                    "background-color:#1e293b; color:#f1f5f9;"
                    "font-family:monospace; font-size:13px;"
                    "padding:6px 10px; border-radius:4px; border:1px solid #475569;"
                ),
            ),
        ).add_to(m)

        colormap.add_to(m)

        if input.show_centers():
            for _, row in centers_gdf.iterrows():
                geom = row.geometry
                if geom.geom_type == "MultiPoint":
                    geom = list(geom.geoms)[0]
                folium.Marker(
                    location=[geom.y, geom.x],
                    icon=folium.Icon(color="white", icon_color=UCHICAGO_MAROON, icon="building", prefix="fa"),
                    tooltip=folium.Tooltip(
                        dc_tooltip_html(row),
                        sticky=True,
                        style=(
                            "background-color:#1e293b; color:#f1f5f9;"
                            "font-family:monospace; font-size:12px;"
                            "padding:8px 12px; border-radius:4px;"
                            "border:1px solid #475569; line-height:1.8;"
                        ),
                    ),
                ).add_to(m)

        return ui.HTML(f'<div style="height:620px; width:100%;">{m._repr_html_()}</div>')

    @reactive.Calc
    def plot_data():
        x_var = input.x_var()
        y_var = input.y_var()
        raw_cols = [x_var, y_var, "Zip Code", "Total Data Centers"]
        cols_needed = [c for c in raw_cols if c in cities_df.columns]
        cols_needed = list(dict.fromkeys(cols_needed))
        df = cities_df[cols_needed].copy().reset_index(drop=True)
        df[x_var] = pd.to_numeric(df[x_var], errors="coerce")
        df[y_var] = pd.to_numeric(df[y_var], errors="coerce")
        df = df.dropna(subset=[x_var, y_var]).reset_index(drop=True)
        return df, x_var, y_var

    @render.ui
    def scatter_plot():
        df, x_var, y_var = plot_data()
        if df.empty:
            return ui.HTML("<p style='color:#f87171;'>No data available.</p>")

        x = df[x_var].to_numpy().astype(float)
        y = df[y_var].to_numpy().astype(float)

        fig, ax = plt.subplots(figsize=(9, 5))
        fig.patch.set_facecolor(DARK_BG)
        ax.set_facecolor(CARD_BG)

        color_by = input.color_by_dc() and "Total Data Centers" in df.columns
        if color_by:
            has_dc = pd.to_numeric(df["Total Data Centers"], errors="coerce").fillna(0).to_numpy() > 0
            ax.scatter(x[~has_dc], y[~has_dc], color="#38bdf8", alpha=0.7,
                       edgecolors="#0f172a", linewidths=0.5, s=60, label="No Data Center", zorder=3)
            ax.scatter(x[has_dc],  y[has_dc],  color=UCHICAGO_MAROON, alpha=0.9,
                       edgecolors="#f1f5f9", linewidths=0.5, s=90, label="Has Data Center",
                       zorder=4, marker="*")
            ax.legend(facecolor=CARD_BG, edgecolor="#475569", labelcolor=TEXT_COL, fontsize=9)
        else:
            ax.scatter(x, y, color=UCHICAGO_MAROON, alpha=0.7,
                       edgecolors="#0f172a", linewidths=0.5, s=60, zorder=3)

        try:
            m_coef, b_coef = np.polyfit(x, y, 1)
            x_line = np.linspace(x.min(), x.max(), 200)
            ax.plot(x_line, m_coef * x_line + b_coef, color="#fb923c",
                    linewidth=1.5, linestyle="--", alpha=0.8, zorder=5)
        except Exception:
            pass

        corr = float(np.corrcoef(x, y)[0, 1])
        ax.annotate(f"r = {corr:.3f}", xy=(0.97, 0.05), xycoords="axes fraction",
                    ha="right", color=TEXT_COL, fontsize=10,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="#0f172a", edgecolor="#475569"))

        ax.set_xlabel(x_var, color=TEXT_COL, fontsize=10)
        ax.set_ylabel(y_var, color=TEXT_COL, fontsize=10)
        ax.tick_params(colors=TEXT_COL)
        for spine in ax.spines.values():
            spine.set_edgecolor("#475569")
        ax.grid(True, color="#334155", linewidth=0.4, linestyle="--")
        plt.tight_layout()
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def dist_plot():
        df, x_var, y_var = plot_data()
        if df.empty:
            return ui.HTML("<p style='color:#f87171;'>No data available.</p>")

        fig, axes = plt.subplots(1, 2, figsize=(9, 4))
        fig.patch.set_facecolor(DARK_BG)

        for ax, var, color in zip(axes, [x_var, y_var], [UCHICAGO_MAROON, "#a78bfa"]):
            vals = pd.to_numeric(df[var], errors="coerce").dropna().to_numpy().astype(float)
            ax.set_facecolor(CARD_BG)
            ax.hist(vals, bins=20, color=color, alpha=0.8, edgecolor="#0f172a")
            mean_v = float(vals.mean())
            ax.axvline(mean_v, color="#fb923c", linewidth=1.5, linestyle="--",
                       label=f"Mean: {mean_v:,.1f}")
            ax.set_title(var, color=TEXT_COL, fontsize=9)
            ax.tick_params(colors=TEXT_COL, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#475569")
            ax.grid(True, color="#334155", linewidth=0.3, linestyle="--")
            ax.legend(facecolor=CARD_BG, edgecolor="#475569", labelcolor=TEXT_COL, fontsize=8)

        plt.tight_layout()
        return ui.HTML(fig_to_html(fig))

    @render.ui
    def summary_stats():
        df, x_var, y_var = plot_data()
        if df.empty:
            return ui.HTML("<p style='color:#f87171;'>No data available.</p>")

        x    = df[x_var].to_numpy().astype(float)
        y    = df[y_var].to_numpy().astype(float)
        corr = float(np.corrcoef(x, y)[0, 1])
        n    = len(df)

        def stat_row(label, x_val, y_val):
            return (
                f"<tr>"
                f"<td style='padding:6px 10px; color:#94a3b8;'>{label}</td>"
                f"<td style='padding:6px 10px; color:{TEXT_COL}; text-align:right;'>{x_val}</td>"
                f"<td style='padding:6px 10px; color:{TEXT_COL}; text-align:right;'>{y_val}</td>"
                f"</tr>"
            )

        rows = "".join([
            stat_row("N (ZIP codes)", f"{n}",                 f"{n}"),
            stat_row("Mean",          f"{x.mean():,.2f}",     f"{y.mean():,.2f}"),
            stat_row("Median",        f"{np.median(x):,.2f}", f"{np.median(y):,.2f}"),
            stat_row("Std Dev",       f"{x.std():,.2f}",      f"{y.std():,.2f}"),
            stat_row("Min",           f"{x.min():,.2f}",      f"{y.min():,.2f}"),
            stat_row("Max",           f"{x.max():,.2f}",      f"{y.max():,.2f}"),
        ])

        corr_color = "#4ade80" if abs(corr) > 0.5 else ("#facc15" if abs(corr) > 0.25 else "#f87171")
        corr_label = "Strong" if abs(corr) > 0.5 else ("Moderate" if abs(corr) > 0.25 else "Weak")
        direction  = "positive" if corr > 0 else "negative"

        html = f"""
        <div style="background:{DARK_BG}; padding:16px; border-radius:8px; font-family:monospace;">
            <div style="margin-bottom:14px; padding:10px; background:{CARD_BG};
                        border-radius:6px; border-left:4px solid {UCHICAGO_MAROON};">
                <span style="color:#94a3b8; font-size:12px;">Pearson Correlation</span><br>
                <span style="color:{corr_color}; font-size:22px; font-weight:bold;">r = {corr:.4f}</span><br>
                <span style="color:#94a3b8; font-size:11px;">{corr_label} {direction} relationship</span>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
                <thead>
                    <tr>
                        <th style="padding:6px 10px; color:#64748b; text-align:left;">Statistic</th>
                        <th style="padding:6px 10px; color:{UCHICAGO_MAROON}; text-align:right;">{x_var[:28]}</th>
                        <th style="padding:6px 10px; color:#a78bfa; text-align:right;">{y_var[:28]}</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """
        return ui.HTML(html)


# =============================================================================
# Set path to the Data folder for local assets
# =============================================================================
www_dir = os.path.join(os.path.dirname(__file__), "Data")
app = App(app_ui, server, static_assets=www_dir)