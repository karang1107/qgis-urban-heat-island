"""
risk_score_normalize.py
-----------------------
Reads the zonal statistics GeoPackage (output of zonal_stats_batch.py),
applies min-max normalization to three variables, computes a weighted
composite risk score (0-100), assigns risk tier labels, and writes the
final scored layer back to a new GeoPackage layer.

Composite score formula:
    score = (lst_dev_norm * 0.50)
          + (imperv_norm  * 0.30)
          + (ndvi_inv_norm * 0.20)
    score_0_100 = score * 100

Weight rationale:
    - LST deviation (50%): direct measure of heat stress; primary output
      variable for this analysis.
    - Impervious surface % (30%): structural driver of UHI — represents
      the land cover characteristic most correlated with heat retention.
    - Inverted NDVI (20%): absence of vegetation as a proxy for reduced
      evapotranspirative cooling. Lower weight because it partially
      co-varies with impervious surface.

Risk tiers:
    Very High : score >= 75
    High      : score >= 50
    Moderate  : score >= 25
    Low       : score <  25

Usage:
    python risk_score_normalize.py

Dependencies:
    - geopandas  (pip install geopandas)
    - pandas     (pip install pandas)
    - numpy      (pip install numpy)

Note on running environment:
    This script uses geopandas rather than PyQGIS, so it runs standalone
    without a QGIS installation. The output GPKG can be loaded directly
    into QGIS or ArcGIS Pro for styling.
"""

import os
import numpy as np
import pandas as pd
import geopandas as gpd

# ── CONFIG ────────────────────────────────────────────────────────────────────

INPUT_GPKG  = "data/processed/tracts_zonal_stats.gpkg"
INPUT_LAYER = "tracts_zonal_stats"
OUTPUT_GPKG = "data/processed/tracts_risk_scores.gpkg"
OUTPUT_CSV  = "outputs/data/tract_risk_scores.csv"

# Fields from the zonal stats output
FIELD_LST_DEV  = "lst_deviation"   # °C deviation from county mean
FIELD_IMPERV   = "imperv_pct"      # 0-100 impervious surface %
FIELD_NDVI     = "ndvi_mean"       # NDVI mean (higher = more vegetation)

NODATA_VAL = -9999.0

WEIGHTS = {
    "lst_deviation": 0.50,
    "imperv_pct":    0.30,
    "ndvi_inverted": 0.20,
}

RISK_TIERS = [
    (75, "Very High"),
    (50, "High"),
    (25, "Moderate"),
    (0,  "Low"),
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def replace_nodata(series: pd.Series, nodata: float = NODATA_VAL) -> pd.Series:
    """Replace nodata sentinel values with NaN."""
    return series.replace(nodata, np.nan)


def minmax_normalize(series: pd.Series) -> pd.Series:
    """
    Min-max normalize a series to [0, 1].
    NaN values are preserved (not filled) so they don't skew the range.
    """
    vmin = series.min()
    vmax = series.max()
    if vmax == vmin:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - vmin) / (vmax - vmin)


def assign_risk_tier(score: float) -> str:
    if pd.isna(score):
        return "No Data"
    for threshold, label in RISK_TIERS:
        if score >= threshold:
            return label
    return "Low"


def print_score_summary(gdf: gpd.GeoDataFrame) -> None:
    print("\n  Risk tier distribution:")
    tier_counts = gdf["risk_tier"].value_counts()
    for tier in ["Very High", "High", "Moderate", "Low", "No Data"]:
        count = tier_counts.get(tier, 0)
        pct = count / len(gdf) * 100
        bar = "█" * int(pct / 2)
        print(f"    {tier:<12} {count:>4} tracts  ({pct:5.1f}%)  {bar}")

    print(f"\n  Score stats (0-100):")
    valid = gdf["risk_score"].dropna()
    print(f"    Min    : {valid.min():.1f}")
    print(f"    Max    : {valid.max():.1f}")
    print(f"    Mean   : {valid.mean():.1f}")
    print(f"    Median : {valid.median():.1f}")

    print(f"\n  Top 5 tracts by risk score:")
    top5 = gdf[["GEOID", "lst_deviation", "imperv_pct", "ndvi_mean", "risk_score", "risk_tier"]] \
               .sort_values("risk_score", ascending=False).head(5)
    print(top5.to_string(index=False))

    print(f"\n  Bottom 5 tracts by risk score:")
    bot5 = gdf[["GEOID", "lst_deviation", "imperv_pct", "ndvi_mean", "risk_score", "risk_tier"]] \
               .sort_values("risk_score").head(5)
    print(bot5.to_string(index=False))


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Risk Score Normalization and Composite Scoring ===\n")

    if not os.path.exists(INPUT_GPKG):
        raise FileNotFoundError(
            f"Input not found: {INPUT_GPKG}\n"
            "Run zonal_stats_batch.py first."
        )

    # Step 1: Load
    print("Step 1: Loading zonal stats layer...")
    gdf = gpd.read_file(INPUT_GPKG, layer=INPUT_LAYER)
    print(f"  Loaded {len(gdf)} tracts, CRS: {gdf.crs}")

    # Step 2: Clean nodata
    print("\nStep 2: Replacing nodata sentinel values with NaN...")
    for field in [FIELD_LST_DEV, FIELD_IMPERV, FIELD_NDVI]:
        before = gdf[field].isna().sum()
        gdf[field] = replace_nodata(gdf[field])
        after = gdf[field].isna().sum()
        if after > before:
            print(f"  {field}: {after - before} nodata values replaced with NaN")

    null_counts = gdf[[FIELD_LST_DEV, FIELD_IMPERV, FIELD_NDVI]].isna().sum()
    if null_counts.any():
        print(f"  NaN counts after cleaning:\n{null_counts}")

    # Step 3: Normalize
    print("\nStep 3: Min-max normalizing each variable...")
    gdf["lst_dev_norm"]  = minmax_normalize(gdf[FIELD_LST_DEV])
    gdf["imperv_norm"]   = minmax_normalize(gdf[FIELD_IMPERV])

    # NDVI is inverted: low vegetation = high risk
    gdf["ndvi_inv"]      = 1.0 - gdf[FIELD_NDVI].clip(0, 1)
    gdf["ndvi_inv_norm"] = minmax_normalize(gdf["ndvi_inv"])

    print(f"  lst_dev_norm  range: [{gdf['lst_dev_norm'].min():.3f}, {gdf['lst_dev_norm'].max():.3f}]")
    print(f"  imperv_norm   range: [{gdf['imperv_norm'].min():.3f}, {gdf['imperv_norm'].max():.3f}]")
    print(f"  ndvi_inv_norm range: [{gdf['ndvi_inv_norm'].min():.3f}, {gdf['ndvi_inv_norm'].max():.3f}]")

    # Step 4: Weighted composite score
    print("\nStep 4: Computing weighted composite score (0-100)...")
    gdf["risk_score"] = (
        gdf["lst_dev_norm"]  * WEIGHTS["lst_deviation"] +
        gdf["imperv_norm"]   * WEIGHTS["imperv_pct"]    +
        gdf["ndvi_inv_norm"] * WEIGHTS["ndvi_inverted"]
    ) * 100

    gdf["risk_score"] = gdf["risk_score"].round(2)

    # Step 5: Assign tiers
    print("Step 5: Assigning risk tier labels...")
    gdf["risk_tier"] = gdf["risk_score"].apply(assign_risk_tier)

    # Step 6: Drop intermediate normalization columns before saving
    drop_cols = ["lst_dev_norm", "imperv_norm", "ndvi_inv", "ndvi_inv_norm"]
    gdf = gdf.drop(columns=[c for c in drop_cols if c in gdf.columns])

    # Step 7: Save GeoPackage
    print(f"\nStep 6: Saving scored GeoPackage → {OUTPUT_GPKG}")
    os.makedirs(os.path.dirname(OUTPUT_GPKG), exist_ok=True)
    gdf.to_file(OUTPUT_GPKG, layer="tracts_risk_scores", driver="GPKG")

    # Step 8: Export CSV (no geometry)
    print(f"Step 7: Exporting CSV → {OUTPUT_CSV}")
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    export_cols = [
        "GEOID", "NAMELSAD",
        "lst_mean", "lst_stddev", "lst_deviation",
        "ndvi_mean", "imperv_pct",
        "risk_score", "risk_tier"
    ]
    export_cols = [c for c in export_cols if c in gdf.columns]
    gdf[export_cols].to_csv(OUTPUT_CSV, index=False)

    # Step 9: Summary
    print_score_summary(gdf)
    print(f"\nDone.")
    print(f"  GeoPackage : {OUTPUT_GPKG}")
    print(f"  CSV        : {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
