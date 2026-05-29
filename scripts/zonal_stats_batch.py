"""
zonal_stats_batch.py
--------------------
Runs zonal statistics for LST and NDVI rasters against Hillsborough
County census tracts, then joins the results into a single GeoPackage.

Also runs a separate pass for NLCD 2021 impervious surface percentage.

This script is written to run either:
  (a) Inside the QGIS Python console (PyQGIS available)
  (b) Standalone via qgis_process or a headless QGIS session

The output GeoPackage (tracts_zonal_stats.gpkg) contains the tract
polygons with these new fields appended:
  lst_mean      — mean LST (°C) per tract
  lst_stddev    — std dev of LST within tract
  ndvi_mean     — mean NDVI per tract
  imperv_pct    — mean impervious surface % per tract (from NLCD)

Usage (QGIS Python console):
    exec(open('scripts/zonal_stats_batch.py').read())

Usage (standalone via qgis_process):
    qgis_process run native:zonalstatisticsfb ...
    (see individual function calls below for parameter mapping)

Notes:
    - PyQGIS processing algorithms add a prefix to new field names by
      default (e.g. '_mean', '_stdev'). This script renames them to
      clean names immediately after each run — learned this the hard
      way when a downstream join broke because the field was called
      '_lst_mean' instead of 'lst_mean'. See workflow_notes.md.
    - NLCD is in Albers Equal Area (EPSG:5070). It gets reprojected
      on the fly inside the zonal stats call. No separate step needed
      here, but confirm the NLCD layer CRS before running.
"""

import os

try:
    import processing
    from qgis.core import (
        QgsVectorLayer, QgsRasterLayer, QgsProject,
        QgsVectorFileWriter, QgsCoordinateReferenceSystem,
        QgsField, QgsExpression, QgsExpressionContext,
        QgsExpressionContextUtils, edit
    )
    from PyQt5.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    print("PyQGIS not available. Run this inside QGIS Python console.")

# ── CONFIG ────────────────────────────────────────────────────────────────────

TRACTS_SHP   = "data/raw/census/tl_2022_12057_tract.shp"
LST_RASTER   = "data/processed/LST_celsius.tif"
NDVI_RASTER  = "data/processed/NDVI.tif"
NLCD_RASTER  = "data/raw/nlcd/nlcd_2021_impervious_l48_20230630.img"
OUTPUT_GPKG  = "data/processed/tracts_zonal_stats.gpkg"

NODATA_LST  = -9999.0
NODATA_NDVI = -9999.0
TARGET_EPSG = "EPSG:2236"

# ── HELPERS ───────────────────────────────────────────────────────────────────

def load_and_reproject_tracts(shp_path: str, target_epsg: str) -> QgsVectorLayer:
    """Load tracts shapefile and reproject to target CRS if needed."""
    layer = QgsVectorLayer(shp_path, "tracts_raw", "ogr")
    if not layer.isValid():
        raise ValueError(f"Could not load layer: {shp_path}")

    if layer.crs().authid() != target_epsg:
        print(f"  Reprojecting tracts from {layer.crs().authid()} → {target_epsg}")
        result = processing.run("native:reprojectlayer", {
            "INPUT": layer,
            "TARGET_CRS": QgsCoordinateReferenceSystem(target_epsg),
            "OUTPUT": "memory:"
        })
        layer = result["OUTPUT"]

    print(f"  Tracts loaded: {layer.featureCount()} features, CRS: {layer.crs().authid()}")
    return layer


def run_zonal_stats(
    vector_layer,
    raster_path: str,
    column_prefix: str,
    stats: list,
    nodata_val: float
):
    """
    Run native:zonalstatisticsfb and return the result layer.
    stats: list of integers — QGIS stat codes:
        1=count, 2=sum, 3=mean, 4=median, 5=stdev, 6=min, 7=max
    """
    print(f"  Running zonal stats: {column_prefix} ({raster_path})")
    result = processing.run("native:zonalstatisticsfb", {
        "INPUT":       vector_layer,
        "INPUT_RASTER": raster_path,
        "RASTER_BAND": 1,
        "COLUMN_PREFIX": column_prefix,
        "STATISTICS":  stats,
        "OUTPUT":      "memory:"
    })
    return result["OUTPUT"]


def rename_zonal_fields(layer, prefix: str, rename_map: dict):
    """
    Rename fields created by zonal stats (which add the prefix literally).
    rename_map: { "old_field_name": "new_field_name" }
    E.g. { "_lst_mean": "lst_mean" }
    """
    with edit(layer):
        for old_name, new_name in rename_map.items():
            idx = layer.fields().indexFromName(old_name)
            if idx >= 0:
                layer.renameAttribute(idx, new_name)
                print(f"    Renamed field: {old_name} → {new_name}")
            else:
                print(f"    WARNING: field not found: {old_name}")


def add_deviation_field(layer, mean_field: str, deviation_field: str):
    """
    Add a field for LST deviation from county mean.
    deviation = tract_mean - county_mean
    """
    # Calculate county mean from all tract means
    values = [f[mean_field] for f in layer.getFeatures()
              if f[mean_field] is not None and f[mean_field] != NODATA_LST]
    if not values:
        print("  WARNING: no valid LST mean values found for deviation calc.")
        return

    county_mean = sum(values) / len(values)
    print(f"  County mean LST: {county_mean:.2f}°C  (n={len(values)} tracts)")

    with edit(layer):
        layer.addAttribute(QgsField(deviation_field, QVariant.Double, "double", 10, 4))
        layer.updateFields()
        for feature in layer.getFeatures():
            val = feature[mean_field]
            if val is not None and val != NODATA_LST:
                deviation = round(val - county_mean, 4)
            else:
                deviation = None
            layer.changeAttributeValue(
                feature.id(),
                layer.fields().indexFromName(deviation_field),
                deviation
            )
    print(f"  Added field: {deviation_field}")


def save_to_gpkg(layer, output_path: str, layer_name: str = "tracts_zonal_stats"):
    """Save vector layer to GeoPackage."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName  = layer_name
    options.fileEncoding = "UTF-8"

    error, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, output_path,
        QgsProject.instance().transformContext(),
        options
    )
    if error != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write GeoPackage: {msg}")
    print(f"  Saved → {output_path}  (layer: {layer_name})")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not QGIS_AVAILABLE:
        print("This script requires PyQGIS. Open QGIS, go to Plugins > Python Console,")
        print("and run: exec(open('scripts/zonal_stats_batch.py').read())")
        return

    print("=== Zonal Statistics: LST + NDVI + Impervious Surface ===\n")

    # Step 1: Load and reproject tracts
    print("Step 1: Loading and reprojecting census tracts...")
    tracts = load_and_reproject_tracts(TRACTS_SHP, TARGET_EPSG)

    # Step 2: LST zonal stats (mean + stdev)
    print("\nStep 2: LST zonal statistics (mean + stdev)...")
    tracts = run_zonal_stats(tracts, LST_RASTER, "_lst_", [3, 5], NODATA_LST)
    rename_zonal_fields(tracts, "_lst_", {
        "_lst_mean":  "lst_mean",
        "_lst_stdev": "lst_stddev"
    })

    # Step 3: NDVI zonal stats (mean only)
    print("\nStep 3: NDVI zonal statistics (mean)...")
    tracts = run_zonal_stats(tracts, NDVI_RASTER, "_ndvi_", [3], NODATA_NDVI)
    rename_zonal_fields(tracts, "_ndvi_", {
        "_ndvi_mean": "ndvi_mean"
    })

    # Step 4: NLCD impervious surface zonal stats
    # NLCD values are already in % (0-100 integer), so mean gives avg imperv %
    print("\nStep 4: NLCD impervious surface zonal statistics (mean)...")
    tracts = run_zonal_stats(tracts, NLCD_RASTER, "_imperv_", [3], 127)
    rename_zonal_fields(tracts, "_imperv_", {
        "_imperv_mean": "imperv_pct"
    })

    # Step 5: Calculate LST deviation from county mean
    print("\nStep 5: Calculating LST deviation from county mean...")
    add_deviation_field(tracts, "lst_mean", "lst_deviation")

    # Step 6: Save output
    print(f"\nStep 6: Saving to GeoPackage...")
    save_to_gpkg(tracts, OUTPUT_GPKG)

    # Step 7: Summary
    feat_count = tracts.featureCount()
    fields = [f.name() for f in tracts.fields()]
    print(f"\n  Done. {feat_count} tracts, fields: {fields}")
    print(f"\nOutput: {OUTPUT_GPKG}")


if __name__ == "__main__":
    main()
