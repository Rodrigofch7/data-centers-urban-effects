import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path

# To run:
#   uv run python -m data_centers_next_door.data_preparation.zillow_data
ROOT = Path(__file__).resolve().parents[2]

MAP_PATH = ROOT / "data/spatial_data/cities/ChicagoMetroArea.parquet"
INPUT_PATH = ROOT / "data/housing_and_data_centers_data/zillow_chicago_metro_region.csv"
OUTPUT_PATH = ROOT / "data/housing_and_data_centers_data/zillow_yearly_estimates_chicago_metro.csv"


# ── Core processing function (importable for tests) ───────────────────────────
def process_zillow_yearly(df):
    metadata_cols = [col for col in df.columns if not col.startswith("X")]
    date_cols = [col for col in df.columns if col.startswith("X")]

    df_long = pd.melt(
        df, id_vars=metadata_cols, value_vars=date_cols, var_name="Date_Str", value_name="Estimate"
    )

    df_long["Year"] = df_long["Date_Str"].str.lstrip("X").str.split(".").str[0]
    df_long["Estimate"] = pd.to_numeric(df_long["Estimate"], errors="coerce")

    yearly_grouped = df_long.groupby(metadata_cols + ["Year"])["Estimate"].mean().reset_index()

    final_df = yearly_grouped.pivot(
        index=metadata_cols, columns="Year", values="Estimate"
    ).reset_index()
    final_df.columns.name = None
    return final_df


def main():
    # 1. Load the parquet to get the full ZIP anchor
    gdf = gpd.read_parquet(MAP_PATH)
    gdf["ZCTA5CE20"] = gdf["ZCTA5CE20"].astype(str)
    anchor = gdf[["ZCTA5CE20"]].drop_duplicates().copy()
    print(f"Parquet anchor: {len(anchor):,} unique ZIP codes")

    # 2. Load and process the Zillow data
    df = pd.read_csv(INPUT_PATH)
    processed_df = process_zillow_yearly(df)

    if "ZCTA5CE20" in processed_df.columns:
        processed_df["ZCTA5CE20"] = processed_df["ZCTA5CE20"].astype(str)

    # 3. Left join onto anchor so ALL parquet ZIPs are present
    merged = anchor.merge(processed_df, on="ZCTA5CE20", how="left")

    # 4. Validate
    print(f"Processed Zillow rows: {len(processed_df):,}")
    print(f"Final merged rows:     {len(merged):,}")
    assert len(merged) == len(anchor), "ERROR: row count doesn't match parquet ZIP count!"
    assert merged["ZCTA5CE20"].nunique() == len(merged), "ERROR: duplicate ZCTAs detected!"

    missing = merged[merged.iloc[:, 1].isna()]["ZCTA5CE20"].tolist()
    print(f"✓ All {len(anchor):,} parquet ZIPs present")
    print(f"  ZIPs with no Zillow match (NaN data): {len(missing)}")
    if missing:
        print(f"  {missing}")

    # 5. Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_PATH, index=False)
    print(f"\nFile successfully saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
