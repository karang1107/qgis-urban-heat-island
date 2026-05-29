# Workflow Notes — Urban Heat Island Mapping

Real-time notes taken during the analysis. Not a polished document — just what I actually wrote as I worked through this.

---

## 2023-10-04 — Data acquisition

Downloaded the Landsat 8 scene from EarthExplorer. Took longer than expected to find a suitable scene — the July 14 one (LC08_L2SP_017040_20230714) had 2% cloud cover according to the metadata, which looked fine, but when I opened it in QGIS there was a band of thin cloud across the northern part of the scene, mostly over Pasco County. Since the analysis is focused on Hillsborough County proper, this doesn't affect the output, but I noted it anyway.

Also downloaded the wrong product initially — grabbed Level-1 instead of Level-2. The difference matters: Level-2 has the atmospheric correction and surface temperature correction already applied, which is what you want for LST work. Level-1 would require running the full atmospheric correction yourself (FLAASH or similar), which is well beyond the scope of this project. Deleted the Level-1 files, re-downloaded Level-2.

File sizes: B4 and B5 are ~60MB each, B10 is ~120MB (100m native res upsampled to 30m). QA band is small (~30MB). Total download ~270MB.

NLCD impervious layer: the national file is huge (~4GB). Clipped to the Southeast extent first using GDAL before downloading the full tile. That brought it down to a manageable ~180MB for the Florida region.

---

## 2023-10-05 — CRS decisions

Decided to work in **Florida State Plane East (EPSG:2236)** throughout. Notes on why:

- The analysis area (Hillsborough County) falls squarely within the Florida East zone.
- Units are in US Survey Feet, which is standard for Florida government data. Slightly annoying for metric calculations but manageable.
- Alternative considered: UTM Zone 17N (EPSG:32617). Would also work fine and gives metric units. Chose State Plane because most of the Florida-specific reference data (parcel data, FDEP layers, FGDL layers) is distributed in this CRS, so if this project expands to include additional data layers, the CRS is already right.
- Did NOT use WGS84 (EPSG:4326) for any analysis steps — geographic coordinate systems are inappropriate for area-based calculations like zonal statistics because the degree-based units distort areas near the poles (less of an issue at 28°N, but still bad practice).

All input layers reprojected before any analysis begins. Confirmed alignment visually in QGIS by toggling layers on/off and checking that boundaries lined up.

---

## 2023-10-05 — LST conversion issue

Ran the Raster Calculator to convert Band 10 DN → Celsius and got values between 2,000 and 5,000. That's obviously wrong (Tampa in July should be roughly 25–50°C).

After about 30 minutes of debugging, realized the issue: I was applying the scale factor twice. The Landsat Collection 2 Level-2 product guide says the ST_B10 band is delivered as scaled integers with the scale factor (0.00341802) and offset (149.0) documented in the MTL metadata file. I had already applied those in a pre-processing step (thought I hadn't), and then applied them again in the Raster Calculator expression.

Fix: removed the redundant step. After the single correct application:

```
LST_K = DN * 0.00341802 + 149.0
LST_C = LST_K - 273.15
```

Output range was 26.3°C – 49.1°C, which is reasonable for a July afternoon in Tampa.

**Lesson:** always check the product guide for Level-2 products before writing the band math expression. Collection 1 and Collection 2 have different scale factors and offsets. Don't assume.

---

## 2023-10-06 — Zonal statistics: NULL issue

After the first zonal stats run for the NLCD impervious layer, about 12% of tracts had NULL values for `imperv_pct`. Spot-checked a few — they were coastal tracts, mostly on the western edge of the county along Tampa Bay and Old Tampa Bay.

Root cause: the NLCD raster (originally in Albers Equal Area, EPSG:5070) was reprojected to EPSG:2236 using gdalwarp before the zonal stats run. The reprojection didn't quite extend to the edges of the county, so coastal tracts with significant water area had polygons that extended slightly beyond the raster extent. QGIS zonal statistics returns NULL when a polygon doesn't overlap the raster at all, or when overlap is insufficient.

Two possible fixes:
1. Buffer the raster extent before reprojection, then clip to county boundary.
2. Fill NULL values with 0 (reasonable assumption — coastal water = 0% impervious).

Went with option 1 (buffer + clip) because option 2 is a data assumption, not a data fix. Used `gdalwarp` with `-te` flag set to a slightly expanded bounding box (500m buffer on all sides), then clipped with `gdalwarp -cutline` after. NULLs resolved completely.

---

## 2023-10-06 — Field naming after zonal statistics

Lost the GEOID field after a zonal statistics join. Spent 20 minutes puzzled about why the downstream demographic data join wasn't working, before realizing that the field was still there — it had just been renamed to `_GEOID` with the zonal stats prefix.

QGIS's native zonal statistics algorithm prepends the column prefix you specify to every field name in the output, including the ones that already existed on the input layer. This caught me off guard.

Going forward: rename all fields immediately after each zonal stats run, before doing any additional joins or calculations. The rename_zonal_fields() function in the script handles this.

---

## 2023-10-09 — Symbolization decisions

Tested four classification methods for the LST deviation choropleth:
- Equal Interval: didn't work well — most tracts clustered near 0, leaving the highest classes nearly empty.
- Quantile: forced equal counts per class, which obscured the concentration of high-heat tracts downtown.
- Standard Deviation: interesting but harder to explain to a non-GIS planning audience.
- **Jenks Natural Breaks (selected):** best separation between clusters; matched the visual distribution of values; widely understood in planning contexts.

5 classes was the right number. 3 classes felt too coarse (merged genuinely different patterns). 7 classes was too many for the map legend at A3 size.

Color ramp: tried ColorBrewer "RdYlBu" (reversed) initially. The yellow middle class was hard to read against both the white basemap and the colored adjacent classes. Switched to "RdBu" reversed — cleaner contrast, better for print.

Important: set the diverging ramp to center at 0°C deviation (the county mean), not at the midpoint of the data range. This required manually specifying the break points rather than using auto-classification. The QGIS "Classify" button can't do a diverging ramp centered on an arbitrary value — had to set the 5 class breaks manually after choosing the ramp.

---

## 2023-10-10 — Print layout

A3 landscape worked better than letter landscape — the map needed space for both the main choropleth and the inset overview map without feeling cramped. The bar chart showing top/bottom 10 tracts by LST deviation took a while to place cleanly; ended up putting it below the legend in the bottom-right panel.

Scale bar: used 0–5–10km. Confirmed the scale was correct by spot-checking against a known distance (I-275 from downtown to the Gandy Bridge is roughly 10km — the scale bar matched).

North arrow: went with a simple arrow rather than a decorative compass rose. Compass roses look dated and take up too much visual space.

Exported at 300 DPI to PDF and PNG. The PNG is ~18MB — reasonable for a full A3 at 300 DPI.
