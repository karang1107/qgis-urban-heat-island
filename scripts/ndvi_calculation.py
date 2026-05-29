"""
ndvi_calculation.py
-------------------
Calculates NDVI (Normalized Difference Vegetation Index) from
Landsat 8 Collection 2 Level-2 surface reflectance bands:

    NDVI = (Band 5 NIR - Band 4 Red) / (Band 5 NIR + Band 4 Red)

Like the ST_B10 thermal band, the SR (surface reflectance) bands also
ship with a scale factor and offset that must be applied before the
NDVI formula:

    Reflectance = DN * 0.0000275 + (-0.2)

Values outside [0, 1] after rescaling indicate cloud/shadow/water edges
and are masked using the QA_PIXEL band before calculation.

Output is a single-band float32 GeoTIFF in EPSG:2236, co-registered
with the LST output so zonal stats can be run on both in one pass.

Usage:
    python ndvi_calculation.py

Dependencies:
    - GDAL/OGR Python bindings
    - numpy
"""

import os
import numpy as np
from osgeo import gdal

# ── CONFIG ────────────────────────────────────────────────────────────────────

INPUT_B4    = "data/raw/landsat/LC08_L2SP_017040_20230714_SR_B4.TIF"   # Red
INPUT_B5    = "data/raw/landsat/LC08_L2SP_017040_20230714_SR_B5.TIF"   # NIR
INPUT_QA    = "data/raw/landsat/LC08_L2SP_017040_20230714_QA_PIXEL.TIF"
OUTPUT_NDVI = "data/processed/NDVI.tif"
TARGET_EPSG = 2236

# Collection 2 Level-2 SR scale factors
SR_SCALE  =  0.0000275
SR_OFFSET = -0.2

NODATA_OUT = -9999.0

# QA_PIXEL bit flags to mask (cloud, cloud shadow, cirrus)
# Bit 3 = cloud, Bit 4 = cloud shadow, Bit 2 = dialated cloud
QA_CLOUD_BITS = (1 << 3) | (1 << 4) | (1 << 2)

# ── HELPERS ───────────────────────────────────────────────────────────────────

def reproject_band(src_path: str, epsg: int, reference_ds: gdal.Dataset) -> np.ndarray:
    """
    Reproject a band to match the reference dataset's grid exactly.
    Uses nearest-neighbour for QA, bilinear for SR bands.
    Returns the array aligned to reference_ds.
    """
    ref_gt  = reference_ds.GetGeoTransform()
    ref_proj = reference_ds.GetProjection()
    ref_cols = reference_ds.RasterXSize
    ref_rows = reference_ds.RasterYSize

    mem_drv = gdal.GetDriverByName("MEM")
    dst_ds  = mem_drv.Create("", ref_cols, ref_rows, 1, gdal.GDT_Float32)
    dst_ds.SetGeoTransform(ref_gt)
    dst_ds.SetProjection(ref_proj)

    alg = gdal.GRA_NearestNeighbour if "QA" in src_path else gdal.GRA_Bilinear
    gdal.ReprojectImage(gdal.Open(src_path), dst_ds, None, None, alg)

    return dst_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)


def apply_sr_scaling(dn: np.ndarray) -> np.ndarray:
    """Apply Collection 2 SR scale factor and clamp to [0, 1]."""
    reflectance = dn * SR_SCALE + SR_OFFSET
    return np.clip(reflectance, 0.0, 1.0)


def build_qa_mask(qa_array: np.ndarray) -> np.ndarray:
    """
    Return a boolean mask — True where pixels are clear (usable).
    Masks out cloud, cloud shadow, and dilated cloud bits.
    """
    cloudy = (qa_array.astype(np.uint16) & QA_CLOUD_BITS) > 0
    return ~cloudy


def calculate_ndvi(red: np.ndarray, nir: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Compute NDVI with divide-by-zero protection.
    Masked pixels (cloud/shadow) are set to NODATA_OUT.
    """
    denom = nir + red
    # avoid division by zero — set denominator zeros to NaN temporarily
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.where(denom != 0, (nir - red) / denom, np.nan)

    # apply cloud mask
    ndvi = np.where(mask, ndvi, NODATA_OUT)
    return ndvi.astype(np.float32)


def write_raster(array: np.ndarray, reference_ds: gdal.Dataset, out_path: str) -> None:
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
    ds = gdal.Open(path)
    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    valid = arr[arr != NODATA_OUT]
    pct_positive = (valid > 0.3).sum() / valid.size * 100
    print(f"\n  NDVI output stats:")
    print(f"    Min              : {valid.min():.4f}")
    print(f"    Max              : {valid.max():.4f}")
    print(f"    Mean             : {valid.mean():.4f}")
    print(f"    % pixels > 0.3   : {pct_positive:.1f}%  (vegetation threshold)")
    print(f"    Valid pixels     : {valid.size:,}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=== NDVI Calculation: Landsat B4/B5 Surface Reflectance ===\n")

    for path in [INPUT_B4, INPUT_B5, INPUT_QA]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input not found: {path}")

    os.makedirs(os.path.dirname(OUTPUT_NDVI), exist_ok=True)

    # Use the LST output as the reference grid so all layers align perfectly
    lst_path = "data/processed/LST_celsius.tif"
    if not os.path.exists(lst_path):
        raise FileNotFoundError(
            "LST_celsius.tif not found. Run lst_conversion.py first."
        )
    reference_ds = gdal.Open(lst_path)

    print("Step 1: Reprojecting and aligning B4 (Red) to reference grid...")
    b4_dn = reproject_band(INPUT_B4, TARGET_EPSG, reference_ds)

    print("Step 2: Reprojecting and aligning B5 (NIR) to reference grid...")
    b5_dn = reproject_band(INPUT_B5, TARGET_EPSG, reference_ds)

    print("Step 3: Reprojecting QA band and building cloud mask...")
    qa_arr = reproject_band(INPUT_QA, TARGET_EPSG, reference_ds)
    mask   = build_qa_mask(qa_arr)
    pct_clear = mask.sum() / mask.size * 100
    print(f"  Clear pixels: {pct_clear:.1f}%  (cloud cover for this scene)")

    print("\nStep 4: Applying SR scale factors...")
    red = apply_sr_scaling(b4_dn)
    nir = apply_sr_scaling(b5_dn)

    print("Step 5: Computing NDVI...")
    ndvi = calculate_ndvi(red, nir, mask)

    print("\nStep 6: Writing output raster...")
    write_raster(ndvi, reference_ds, OUTPUT_NDVI)

    validate_output(OUTPUT_NDVI)

    print(f"\nDone. Output: {OUTPUT_NDVI}")


if __name__ == "__main__":
    main()
