import pandas as pd
import geopandas as gpd
import os
from pathlib import Path

# To run:
#   uv run python -m data_centers_next_door.data_preparation.processing_water_energy
ROOT = Path(__file__).resolve().parents[2]

# ── Column label mappings (suffix → readable name) ───────────────────────────
ELEC_COLS = {
    "E001": "elec_total",
    "E002": "elec_not_charged",
    "E003": "elec_charged",
    "E004": "elec_lt_50",
    "E005": "elec_50_99",
    "E006": "elec_100_149",
    "E007": "elec_150_199",
    "E008": "elec_200_249",
    "E009": "elec_250_plus",
    "M001": "elec_total_moe",
    "M002": "elec_not_charged_moe",
    "M003": "elec_charged_moe",
    "M004": "elec_lt_50_moe",
    "M005": "elec_50_99_moe",
    "M006": "elec_100_149_moe",
    "M007": "elec_150_199_moe",
    "M008": "elec_200_249_moe",
    "M009": "elec_250_plus_moe",
}

WATER_COLS = {
    "E001": "water_total",
    "E002": "water_not_charged",
    "E003": "water_charged",
    "E004": "water_lt_125",
    "E005": "water_125_249",
    "E006": "water_250_499",
    "E007": "water_500_749",
    "E008": "water_750_999",
    "E009": "water_1000_plus",
    "M001": "water_total_moe",
    "M002": "water_not_charged_moe",
    "M003": "water_charged_moe",
    "M004": "water_lt_125_moe",
    "M005": "water_125_249_moe",
    "M006": "water_250_499_moe",
    "M007": "water_500_749_moe",
    "M008": "water_750_999_moe",
    "M009": "water_1000_plus_moe",
}

KEEP_CONTEXT = ["GISJOIN", "ZCTA5A", "STUSAB", "NAME_E"]

FILES = [
    {
        "path": ROOT / "data/energy and water data/nhgis0003_ds255_20215_zcta.csv",
        "year": "2021",
        "elec_prefix": "APCX",
        "water_prefix": "APCZ",
    },
    {
        "path": ROOT / "data/energy and water data/nhgis0003_ds263_20225_zcta.csv",
        "year": "2022",
        "elec_prefix": "AREA",
        "water_prefix": "AREC",
    },
    {
        "path": ROOT / "data/energy and water data/nhgis0003_ds268_20235_zcta.csv",
        "year": "2023",
        "elec_prefix": "ATE7",
        "water_prefix": "ATE9",
    },
    {
        "path": ROOT / "data/energy and water data/nhgis0003_ds273_20245_zcta.csv",
        "year": "2024",
        "elec_prefix": "AVGI",
        "water_prefix": "AVGK",
    },
]

MAP_PATH   = ROOT / "data/spatial_data/cities/ChicagoMetroArea.parquet"
OUTPUT_PATH = ROOT / "data/energy and water data/nhgis_energy_water_wide.csv"


def main():
    # ── Load master ZIP list from parquet (source of truth) ──────────────────
    gdf = gpd.read_parquet(MAP_PATH)
    gdf["ZCTA5CE20"] = gdf["ZCTA5CE20"].astype(str)
    chicago_zips = set(gdf["ZCTA5CE20"].dropna().unique())
    print(f"Loaded {len(chicago_zips)} Chicago metro ZIP codes from parquet")

    # Anchor: full ZIP list — every row in the final output is guaranteed to exist here
    anchor = (
        gdf[["ZCTA5CE20"]]
        .drop_duplicates()
        .rename(columns={"ZCTA5CE20": "ZCTA5A"})
        .copy()
    )

    # ── Process each ACS file ─────────────────────────────────────────────────
    frames = []

    for cfg in FILES:
        year = cfg["year"]
        print(f"Reading {cfg['path'].name} ({year}) …")
        df = pd.read_csv(cfg["path"], encoding="latin-1", dtype={"ZCTA5A": str})

        ep = cfg["elec_prefix"]
        wp = cfg["water_prefix"]

        rename = {}
        for suffix, label in ELEC_COLS.items():
            rename[ep + suffix] = f"{label}_{year}"
        for suffix, label in WATER_COLS.items():
            rename[wp + suffix] = f"{label}_{year}"

        ctx_cols  = [c for c in KEEP_CONTEXT if c in df.columns]
        data_cols = [c for c in rename.keys() if c in df.columns]
        df = df[ctx_cols + data_cols].rename(columns=rename)

        before = len(df)
        df = df[df["ZCTA5A"].isin(chicago_zips)].copy()
        print(f"  → {len(df):,} ZCTAs matched (from {before:,} national)")

        frames.append(df)

    # ── Merge ACS years together ──────────────────────────────────────────────
    print("\nMerging ACS years …")
    acs_merged = frames[0]
    for df in frames[1:]:
        data_cols = [c for c in df.columns if c not in KEEP_CONTEXT or c == "ZCTA5A"]
        acs_merged = acs_merged.merge(df[data_cols], on="ZCTA5A", how="outer")

    # ── Left join onto anchor so ALL parquet ZIPs are present ────────────────
    merged = anchor.merge(acs_merged, on="ZCTA5A", how="left")

    # ── Validate ──────────────────────────────────────────────────────────────
    print(f"\nFinal dataset: {len(merged):,} rows × {merged.shape[1]} columns")
    assert len(merged) == len(anchor), "ERROR: row count doesn't match parquet ZIP count!"
    assert merged["ZCTA5A"].nunique() == len(merged), "ERROR: duplicate ZCTAs detected!"

    missing = merged[merged["elec_total_2024"].isna()]["ZCTA5A"].tolist()
    print(f"✓ All {len(anchor):,} parquet ZIPs present")
    print(f"  ZIPs with no ACS match (NaN data): {len(missing)}")
    if missing:
        print(f"  {missing}")

    # ── Save ──────────────────────────────────────────────────────────────────
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved → {OUTPUT_PATH}")
    print("\nColumns in output:")
    for col in merged.columns:
        print(f"  {col}")


if __name__ == "__main__":
    main()