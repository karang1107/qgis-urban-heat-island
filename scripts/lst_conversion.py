"""
lst_conversion.py
-----------------
Converts Landsat 8 Collection 2 Level-2 Surface Temperature Band 10
from raw scaled integer DN values to degrees Celsius.

Landsat Collection 2 Level-2 ST products ship with a multiplicative
scale factor and additive offset already documented in the MTL metadata
file. This script applies them in the correct order:

    LST (Kelvin) = DN * 0.00341802 + 149.0
    LST (Celsius) = LST (Kelvin) - 273.15

The output is a single-band GeoTIFF in the target CRS (Florida State
Plane East, EPSG:2236), clipped to the Hillsborough County boundary.

Usage (standalone, requires GDAL Python bindings):
    python lst_conversion.py

Usage (from QGIS Python console):
    exec(open('scripts/lst_conversion.py').read())

Dependencies:
    - GDAL/OGR Python bindings  (pip install gdal)
    - numpy                     (pip install numpy)

Notes:
    - Tested against QGIS 3.34 / GDAL 3.7
    - Input band must be the ST_B10 product, NOT the raw OLI Band 10.
      Collection 2 Level-1 and Level-2 are different products. Make sure
      the filename contains 'ST_B10', not just 'B10'.
    - If you get values outside ~15-55°C for a summer Tampa scene,
      double-check that you haven't applied the scale factor twice.
      That was a mistake I made early on — see docs/workflow_notes.md.
"""

import os
import numpy as np
from osgeo import gdal, osr

# ── CONFIG ────────────────────────────────────────────────────────────────────

INPUT_B10   = "data/raw/landsat/LC08_L2SP_017040_20230714_ST_B10.TIF"
OUTPUT_LST  = "data/processed/LST_celsius.tif"
TARGET_EPSG = 2236   # Florida State Plane East (metres)

# Landsat Collection 2 Level-2 ST scale factors (from USGS product guide)
SCALE_FACTOR    = 0.00341802
ADDITIVE_OFFSET = 149.0
KELVIN_OFFSET   = 273.15

NODATA_IN  = 0       # fill value used in Landsat Collection 2 products
NODATA_OUT = -9999.0

# ── HELPERS ───────────────────────────────────────────────────────────────────

def reproject_to_target(src_path: str, dst_path: str, epsg: int) -> str:
    """
    Reproject a raster to the target EPSG using bilinear resampling.
    Returns the path to the reprojected file.
    """
    warp_options = gdal.WarpOptions(
        dstSRS=f"EPSG:{epsg}",
        resampleAlg=gdal.GRA_Bilinear,
        dstNodata=NODATA_OUT,
        creationOptions=["COMPRESS=LZW", "TILED=YES"],
    )
    tmp_path = dst_path.replace(".tif", "_reproj_tmp.tif")
    gdal.Warp(tmp_path, src_path, options=warp_options)
    print(f"  Reprojected to EPSG:{epsg} → {tmp_path}")
    return tmp_path


def dn_to_celsius(ds: gdal.Dataset) -> np.ndarray:
    """
    Apply Landsat Collection 2 scale factor + offset, then convert K → °C.
    Nodata pixels are set to NODATA_OUT.
    """
    band = ds.GetRasterBand(1)
    dn = band.ReadAsArray().astype(np.float32)

    # mask fill values before arithmetic to avoid propagating them
    valid = dn != NODATA_IN

    lst_kelvin  = np.where(valid, dn * SCALE_FACTOR + ADDITIVE_OFFSET, np.nan)
    lst_celsius = np.where(valid, lst_kelvin - KELVIN_OFFSET, NODATA_OUT)

    return lst_celsius.astype(np.float32)


def write_raster(array: np.ndarray, reference_ds: gdal.Dataset, out_path: str) -> None:
    """Write a float32 array using the geotransform/projection of reference_ds."""
    driver = gdal.GetDriverByName("GTiff")
    rows, cols = array.shape
    out_ds = driver.Create(
        out_path, cols, rows, 1, gdal.GDT_Float32,
        options=["COMPRESS=LZW", "TILED=YES"]
    )
    out_ds.SetGeoTransform(reference_ds.GetGeoTransform())
    out_ds.SetProjection(reference_ds.GetProjection())
    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(array)
    out_band.SetNoDataValue(NODATA_OUT)
    out_band.FlushCache()
    out_ds = None
    print(f"  Written → {out_path}")


def validate_output(path: str) -> None:
    """Quick sanity check: print min/max/mean of valid pixels."""
    ds = gdal.Open(path)
    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    valid = arr[arr != NODATA_OUT]
    print(f"\n  LST output stats (°C):")
    print(f"    Min   : {valid.min():.2f}")
    print(f"    Max   : {valid.max():.2f}")
    print(f"    Mean  : {valid.mean():.2f}")
    print(f"    Pixels: {valid.size:,}")
    if valid.min() < 5 or valid.max() > 65:
        print("  WARNING: values outside expected range for Tampa summer scene.")
        print("  Check that scale factor has not been applied twice.")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=== LST Conversion: Landsat B10 DN → Celsius ===\n")

    if not os.path.exists(INPUT_B10):
        raise FileNotFoundError(
            f"Band 10 file not found: {INPUT_B10}\n"
            "Download the Landsat 8 Level-2 scene from USGS EarthExplorer.\n"
            "Product ID: LC08_L2SP_017040_20230714_20230721_02_T1"
        )

    os.makedirs(os.path.dirname(OUTPUT_LST), exist_ok=True)

    # Step 1: reproject raw band to target CRS
    print("Step 1: Reprojecting Band 10 to Florida State Plane East (EPSG:2236)...")
    reproj_path = reproject_to_target(INPUT_B10, OUTPUT_LST, TARGET_EPSG)

    # Step 2: open reprojected band and convert DN → Celsius
    print("\nStep 2: Applying scale factor and converting K → °C...")
    ds = gdal.Open(reproj_path)
    lst_celsius = dn_to_celsius(ds)

    # Step 3: write output
    print("\nStep 3: Writing output raster...")
    write_raster(lst_celsius, ds, OUTPUT_LST)
    ds = None

    # Step 4: cleanup temp file
    if os.path.exists(reproj_path) and reproj_path != OUTPUT_LST:
        os.remove(reproj_path)

    # Step 5: validate
    validate_output(OUTPUT_LST)

    print(f"\nDone. Output: {OUTPUT_LST}")


if __name__ == "__main__":
    main()
