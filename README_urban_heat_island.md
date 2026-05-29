# Urban Heat Island Mapping — City of Tampa, FL

**Tools:** QGIS 3.34 · GDAL/OGR · PyQGIS · Python 3.11  
**Data sources:** Landsat 8 (USGS EarthExplorer) · OpenStreetMap · US Census TIGER/Line 2022  
**CRS:** WGS84 (EPSG:4326) → Florida State Plane East (EPSG:2236)  
**Status:** Complete  

---

## Overview

This project maps land surface temperature (LST) variation across Tampa's urban core using Landsat 8 multispectral imagery and ancillary vector data. The goal was to identify which census tracts experience the most significant urban heat island (UHI) effect — where urban materials like concrete and asphalt absorb and re-emit heat far more than surrounding vegetated areas — and to correlate that effect with land cover composition.

The output is a set of cartographic products intended for a city planning audience: a tract-level choropleth of LST deviation, a paired NDVI map showing green canopy density, and a composite risk scoring table that combines both variables with impervious surface cover percentage.

This was a solo end-to-end project: raw raster acquisition, preprocessing, analysis, and final map production were all completed in QGIS, with supporting data cleaning done in Python using `geopandas` and `pandas`.

---

## Background and Motivation

Urban heat islands are well-documented in dense metros, but the intra-city distribution of heat stress is uneven and often correlates with historical disinvestment patterns. I chose Tampa partly because I'm based here and have familiarity with its neighborhood geography, and partly because the city's mix of high-density urban core, mid-century residential suburbs, and significant impervious cover (parking lots, highway corridors) makes it a textbook UHI candidate.

The Landsat 8 thermal infrared sensor (Band 10) provides LST data at 100m resolution (resampled to 30m). While this isn't fine-grained enough for block-level analysis, it works well for tract-level aggregation and trend mapping.

---

## Data Sources

| Dataset | Source | Format | Notes |
|---|---|---|---|
| Landsat 8 OLI/TIRS Collection 2 | USGS EarthExplorer | GeoTIFF | Scene LC08_L2SP_017040_20230714 (July 2023, low cloud cover) |
| Census Tract Boundaries | US Census TIGER/Line 2022 | Shapefile | Hillsborough County, FL |
| Land Cover (NLCD 2021) | USGS Multi-Resolution Land Characteristics | GeoTIFF | Used for impervious surface % |
| Road Network | OpenStreetMap via QuickOSM | GeoPackage | Tampa metro bounding box |
| Administrative Boundaries | Florida Geographic Data Library | Shapefile | City limits, county boundary |

Scene selection criteria: acquired in summer (June–August) to capture peak heat conditions; cloud cover < 5%; no atmospheric anomalies noted in metadata QA band.

---

## Methodology

### 1. Data Acquisition and CRS Setup

Downloaded the Landsat 8 Level-2 scene from EarthExplorer (Product ID: `LC08_L2SP_017040_20230714_20230721_02_T1`). Level-2 products include surface reflectance and surface temperature corrections already applied by USGS, which simplifies the LST derivation step.

All layers were reprojected to **Florida State Plane East (EPSG:2236)** — a metric projection appropriate for this region — before any spatial operations. Working in a projected CRS matters here because zonal statistics and area calculations must be done in a flat coordinate system, not geographic degrees.

```
# Reproject raster in GDAL (also done via QGIS Warp tool)
gdalwarp -s_srs EPSG:4326 -t_srs EPSG:2236 -r bilinear \
  LC08_L2SP_017040_20230714_ST_B10.TIF \
  outputs/LST_B10_FL_StatePlane.tif
```

Census tract and NLCD layers were reprojected using the QGIS "Reproject Layer" tool (Processing > Reproject Layer). Confirmed alignment by overlaying all layers and checking that tract boundaries snapped cleanly to the raster grid.

### 2. LST Derivation from Landsat Band 10

Landsat Collection 2 Level-2 ST products ship with a scale factor applied. The raw DN values must be converted to Kelvin, then to Celsius:

```
LST (Kelvin) = DN × 0.00341802 + 149.0
LST (Celsius) = LST (Kelvin) − 273.15
```

Applied using the QGIS Raster Calculator. Verified output range (should be approximately 20°C–55°C for a summer Tampa scene) before proceeding.

### 3. NDVI Calculation

NDVI (Normalized Difference Vegetation Index) uses near-infrared (Band 5) and red (Band 4) reflectance:

```
NDVI = (Band5 − Band4) / (Band5 + Band4)
```

Same scale factor conversion applied to reflectance bands first. NDVI output ranges from −1 to +1; values above 0.3 generally indicate healthy vegetation cover in this climate.

### 4. Zonal Statistics — Joining Raster Values to Census Tracts

Used QGIS "Zonal Statistics" (Raster > Zonal Statistics) to aggregate mean LST and mean NDVI values for each census tract polygon. Output fields appended to the tract attribute table:

- `lst_mean` — mean LST in Celsius per tract
- `lst_stddev` — standard deviation of LST within tract
- `ndvi_mean` — mean NDVI per tract
- `imperv_pct` — impervious surface percentage from NLCD (separate zonal stats run)

### 5. LST Deviation Calculation

Rather than mapping raw LST (which varies by season and absolute temperature), I calculated each tract's **deviation from the county mean** — how much hotter or cooler a tract runs relative to the Hillsborough County baseline. This makes the map more interpretable and comparable across different acquisition dates.

```
lst_deviation = lst_mean − county_mean_lst
```

Computed in the QGIS Field Calculator. County mean LST was calculated as the mean of all tract means (not a pixel-weighted mean — a minor simplification noted in limitations).

### 6. Risk Score Composite

Combined three normalized variables into a single 0–100 composite risk score per tract:

| Variable | Weight | Rationale |
|---|---|---|
| LST deviation | 50% | Primary heat stress indicator |
| Impervious surface % | 30% | Structural driver of UHI |
| NDVI (inverted) | 20% | Low vegetation = reduced cooling |

Each variable was min-max normalized to 0–1 before weighting. Score computed in Field Calculator. Risk tiers: Low (0–25), Moderate (25–50), High (50–75), Very High (75–100).

### 7. Symbolization and Map Production

Choropleth symbolization used a 5-class Jenks Natural Breaks classification on `lst_deviation`. Color ramp: diverging blue-to-red (ColorBrewer RdBu reversed), centered at 0°C deviation. Tracts with negative deviation (cooler than average) trend toward blue; positive deviation (hotter) toward red.

The print layout was built in QGIS Layout Manager at A3 (420×297mm) landscape orientation, 300 DPI export. Layout elements: main map frame, inset overview map, legend, scale bar, north arrow, data source block, and a small bar chart (created in Layout > Add Item > Add Plot) showing the top 10 and bottom 10 tracts by LST deviation.

---

## Key Findings

- The highest LST deviations (+6°C to +9°C above county mean) clustered around the downtown/Channelside corridor, the area north of I-4 near Ybor City, and large commercial/industrial zones along US-301.
- Lowest LST deviations (−3°C to −5°C) corresponded with census tracts containing Hillsborough River State Park, parts of USF campus, and larger residential parcels with mature tree canopy.
- NDVI and LST showed a moderately strong negative correlation (r = −0.61 across tracts), consistent with literature.
- Impervious surface % was the strongest individual predictor of elevated LST in this dataset.

---

## Limitations and Notes

- July 2023 scene captures a single point in time. Multi-date compositing would produce more stable LST estimates but was out of scope.
- Zonal statistics use unweighted mean per tract; tracts with large non-residential land (e.g., parks, industrial zones) may have skewed means.
- Landsat 8 Band 10 at 100m/30m resolution cannot resolve fine-scale heat patterns (e.g., individual parking lots vs. adjacent green spaces within a single tract).
- NLCD 2021 impervious layer is two years older than the imagery; recent development not reflected.

---

## Troubleshooting Log

**Issue:** After reprojecting the NLCD impervious raster from Albers Equal Area (EPSG:5070) to Florida State Plane (EPSG:2236), zonal statistics returned NULL for ~12% of tracts.  
**Cause:** Reprojection introduced NoData edge artifacts where the raster extent didn't fully cover coastal tract polygons.  
**Fix:** Buffered the NLCD raster extent by 500m before reprojecting, then clipped to county boundary after. NULLs resolved.

**Issue:** Raster Calculator expression for LST conversion returned values in the range 2000–5000 (clearly wrong).  
**Cause:** Scale factor had already been applied in the Level-2 product; I was applying it a second time.  
**Fix:** Reviewed Landsat Collection 2 product guide — Level-2 ST_B10 delivers scaled integers; scale factor (0.00341802) and additive offset (149.0) are applied once to get Kelvin. Corrected expression.

**Issue:** Census tract attribute table lost `GEOID` field after zonal statistics join, breaking the join to demographic data.  
**Cause:** QGIS zonal statistics creates a copy of the input layer; the field was there but had been renamed with a prefix.  
**Fix:** Renamed field back in Field Calculator using `"_lst_mean"` → `"lst_mean"` etc. For future runs: rename fields immediately after zonal stats before doing any additional joins.

---

## Repository Structure

```
qgis-urban-heat-island/
│
├── README.md
│
├── data/
│   ├── raw/
│   │   ├── landsat/
│   │   │   ├── LC08_L2SP_017040_20230714_ST_B10.TIF       # Thermal band (LST)
│   │   │   ├── LC08_L2SP_017040_20230714_SR_B4.TIF        # Red band (NDVI)
│   │   │   ├── LC08_L2SP_017040_20230714_SR_B5.TIF        # NIR band (NDVI)
│   │   │   └── LC08_L2SP_017040_20230714_QA_PIXEL.TIF     # QA/cloud mask
│   │   ├── census/
│   │   │   ├── tl_2022_12057_tract.shp                    # Hillsborough Co. tracts
│   │   │   └── tl_2022_12057_tract.*                      # (+ .dbf, .prj, .shx)
│   │   └── nlcd/
│   │       └── nlcd_2021_impervious_l48_20230630.img      # NLCD impervious surface
│   │
│   └── processed/
│       ├── LST_B10_FL_StatePlane.tif                      # Reprojected thermal raster
│       ├── LST_celsius.tif                                 # Converted to °C
│       ├── NDVI.tif                                        # Calculated NDVI raster
│       ├── tracts_zonal_stats.gpkg                        # Tracts + joined raster stats
│       └── tracts_risk_scores.gpkg                        # Final scored + symbolized layer
│
├── scripts/
│   ├── lst_conversion.py          # Band math: DN → Kelvin → Celsius
│   ├── ndvi_calculation.py        # NDVI from B4/B5
│   ├── zonal_stats_batch.py       # Batch zonal stats via PyQGIS
│   └── risk_score_normalize.py    # Min-max normalization + composite score
│
├── qgis-project/
│   └── tampa_uhi.qgz              # Main QGIS project file (all layers + symbology)
│
├── outputs/
│   ├── maps/
│   │   ├── tampa_uhi_choropleth_A3.pdf    # Final print layout (300 DPI)
│   │   ├── tampa_uhi_choropleth_A3.png    # Web-friendly export
│   │   └── tampa_ndvi_paired_map.png      # NDVI comparison map
│   └── data/
│       └── tract_risk_scores.csv          # Exported attribute table (all tracts + scores)
│
├── docs/
│   ├── workflow_notes.md          # Real-time notes taken during analysis
│   ├── crs_decisions.md           # Projection choice rationale
│   └── symbolization_notes.md     # Color ramp and classification decisions
│
└── .gitignore
```

---

## How to Reproduce

1. Clone this repository.
2. Download the Landsat 8 scene from USGS EarthExplorer (Product ID in Data Sources above). Place `.TIF` files in `data/raw/landsat/`.
3. Download Census TIGER/Line tracts and NLCD 2021 impervious layer. Place in respective `data/raw/` subfolders.
4. Open `qgis-project/tampa_uhi.qgz` in QGIS 3.34+. Remap layer sources to your local paths if prompted.
5. To re-run the analysis pipeline from scratch, execute scripts in order: `lst_conversion.py` → `ndvi_calculation.py` → `zonal_stats_batch.py` → `risk_score_normalize.py`.
6. All scripts use `PyQGIS` and assume QGIS is installed and accessible from your Python environment (see PyQGIS docs for setup on your OS).

Raw raster files are not committed to this repo due to size. Processed outputs and the QGIS project file are included.

---

## Skills Demonstrated

- Raster analysis: band math, raster calculator expressions, resampling, reprojection
- Zonal statistics: aggregating raster values to vector polygons
- CRS management: WGS84 → projected CRS, vertical datum awareness, troubleshooting reproject artifacts
- Field calculator: normalization formulas, composite scoring
- Cartographic design: diverging color ramps, Jenks classification, A3 print layout
- PyQGIS scripting: batch processing, field manipulation
- Workflow documentation: real-time notes, troubleshooting log

---

## License

Data: all source datasets are publicly available under their respective open licenses (USGS, US Census Bureau, OpenStreetMap contributors).  
Code: MIT License.  
Map outputs: CC BY 4.0 — attribution required if reused.
