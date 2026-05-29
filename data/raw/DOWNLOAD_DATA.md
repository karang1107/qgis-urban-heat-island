# Data Directory

Raw spatial data is not committed to this repository due to file size.

## Download Instructions

### Landsat 8 Scene
1. Go to [USGS EarthExplorer](https://earthexplorer.usgs.gov/) (free account required)
2. Search for Product ID: `LC08_L2SP_017040_20230714_20230721_02_T1`
3. Select **Landsat Collection 2 Level-2** product
4. Download the full scene bundle, or at minimum these bands:
   - `*_ST_B10.TIF` — Surface Temperature (Band 10)
   - `*_SR_B4.TIF`  — Surface Reflectance Red (Band 4)
   - `*_SR_B5.TIF`  — Surface Reflectance NIR (Band 5)
   - `*_QA_PIXEL.TIF` — Quality Assessment pixel band

Place downloaded files in `data/raw/landsat/`.

### Census Tract Boundaries
1. Go to [Census TIGER/Line Files](https://www.census.gov/cgi-bin/geo/shapefiles/index.php)
2. Year: **2022**, Layer type: **Census Tracts**
3. State: **Florida**, County: **Hillsborough County**
4. Download and extract the shapefile

Place files (`tl_2022_12057_tract.*`) in `data/raw/census/`.

### NLCD 2021 Impervious Surface
1. Go to [MRLC Viewer](https://www.mrlc.gov/viewer/)
2. Select **NLCD 2021 Impervious Surface**
3. Download tile covering Florida (or use the national file and clip)

Place the `.img` or `.tif` file in `data/raw/nlcd/`.
