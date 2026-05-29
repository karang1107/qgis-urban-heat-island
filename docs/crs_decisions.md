# CRS Decisions — Urban Heat Island Mapping

Documents the coordinate reference system choices made in this project and the reasoning behind them.

---

## Summary

| Stage | CRS | EPSG | Reason |
|---|---|---|---|
| Raw Landsat download | WGS84 Geographic | 4326 | USGS delivers in WGS84 |
| Raw Census TIGER/Line | NAD83 Geographic | 4269 | Census default |
| Raw NLCD | Albers Equal Area Conic (NAD83) | 5070 | USGS national raster CRS |
| All analysis and outputs | Florida State Plane East (NAD83) | 2236 | Appropriate for Hillsborough County |

---

## Why Florida State Plane East (EPSG:2236)?

Florida State Plane East is the standard projected CRS for work in Hillsborough, Pinellas, Pasco, and surrounding counties. Reasons for choosing it here:

**1. Appropriate for the study area.** Hillsborough County falls within the Florida East zone boundary. Using a CRS whose zone closely matches the study area minimizes distortion. UTM Zone 17N (EPSG:32617) would also have been acceptable and gives metric units, but State Plane is the standard for Florida county-level work.

**2. Consistency with Florida reference data.** Most Florida state and county datasets — parcel data, FDOT road network, FGDL administrative layers, SFWMD hydrology — are distributed in Florida State Plane East. If this project expands to incorporate any of those layers, no reprojection step is needed.

**3. Appropriate for area-based calculations.** Geographic CRS (EPSG:4326, EPSG:4269) measure in degrees. Degree-based units are not appropriate for zonal statistics, area calculations, or any distance-dependent analysis. A projected CRS is required for all spatial analysis steps.

**Units note:** Florida State Plane East uses US Survey Feet, not metres. Distance calculations in this project (e.g., buffer distances) are specified in feet. 500m buffer = approximately 1,640 ft.

---

## Reprojection Decisions

### Landsat Band 10 (LST)
- **Source CRS:** WGS84 Geographic (EPSG:4326)
- **Resampling method:** Bilinear
- **Reason:** Bilinear resampling is appropriate for continuous data (temperature values). Nearest-neighbour would introduce blocky artifacts. Cubic convolution would be slightly smoother but bilinear is standard and sufficient at this resolution.

### Landsat SR Bands (B4, B5 for NDVI)
- **Source CRS:** WGS84 Geographic (EPSG:4326)
- **Resampling method:** Bilinear
- **Note:** Both reflectance bands reprojected to match the LST raster grid exactly (same extent, same pixel size, same origin). This ensures pixel-perfect alignment before NDVI calculation.

### QA_PIXEL Band
- **Resampling method:** Nearest Neighbour
- **Reason:** QA_PIXEL is a bitmask — continuous resampling methods (bilinear, cubic) would blend bit flag values across pixels, producing meaningless intermediate values. Nearest-neighbour preserves the integer bit flags.

### NLCD Impervious Surface
- **Source CRS:** Albers Equal Area Conic (EPSG:5070)
- **Resampling method:** Bilinear
- **Known issue:** Initial reprojection introduced NoData edge artifacts on coastal tracts. Resolved by buffering the raster extent by 500ft before reprojecting and then clipping to the county boundary. See workflow_notes.md for details.

### Census Tracts (TIGER/Line)
- **Source CRS:** NAD83 Geographic (EPSG:4269)
- **Method:** QGIS "Reproject Layer" processing algorithm
- **Note:** NAD83 and WGS84 are nearly identical for the contiguous US (difference < 1 metre) but they are technically different datums. Reprojected to State Plane rather than assuming equivalence.

---

## Vertical Datum Note

This project uses only 2D horizontal analysis — no elevation-dependent calculations. Vertical datum was not a factor here.

For reference: Florida State Plane East (EPSG:2236) is a 2D projected CRS based on the NAD83 horizontal datum. If this project were extended to include LiDAR-derived elevation data (e.g., for tree canopy height analysis), the vertical datum would need to be addressed — LiDAR in Florida is typically delivered in NAVD88 (vertical), which requires a geoid model (GEOID18 or GEOID12B) to convert to ellipsoidal height if needed. That's a separate issue from horizontal CRS management.

---

## On-the-Fly Reprojection in QGIS

QGIS reprojects layers on-the-fly for display purposes when layer CRS differs from the project CRS. This is fine for visualization but is NOT a substitute for actual reprojection before analysis. Processing algorithms in QGIS operate in the layer's native CRS unless explicitly reprojected first.

All layers in this project were reprojected to EPSG:2236 before any processing steps. On-the-fly reprojection was left enabled in QGIS for display convenience but played no role in the analysis.
