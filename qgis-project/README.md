# QGIS Project File

The file `tampa_uhi.qgz` is the main QGIS project file containing:
- All layer definitions and CRS settings
- Symbology and classification for the LST deviation choropleth
- Print layout (A3 landscape)
- Layer groups and naming conventions

## Opening the Project

1. Open QGIS 3.34 or later
2. File > Open Project > select `tampa_uhi.qgz`
3. If prompted about missing layers, remap each layer to its path under `data/processed/` or `data/raw/`

## Layer Order (top to bottom in Layers Panel)

```
▼ Reference
    Road network (OSM)
    County boundary
    City limits
▼ Analysis outputs
    Census tracts — Risk score (choropleth)
    Census tracts — LST deviation (choropleth)
▼ Rasters (hidden by default)
    NDVI
    LST (Celsius)
▼ Base data
    Census tracts (no symbology)
```

## Print Layout

Open via Project > Layout Manager > "Tampa UHI A3 Landscape"

Export settings:
- Format: PDF or PNG
- Resolution: 300 DPI
- Output path: `../outputs/maps/`
