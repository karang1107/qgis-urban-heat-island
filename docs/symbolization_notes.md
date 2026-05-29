# Symbolization Notes — Urban Heat Island Mapping

Decisions made during cartographic design, including color ramp selection, classification method, and print layout choices.

---

## Classification Method: Jenks Natural Breaks

Four classification methods were tested on the `lst_deviation` field before settling on Jenks.

**Equal Interval** — rejected. The data range spans roughly −5°C to +9°C. Equal interval with 5 classes produces 2.8°C-wide bins. The vast majority of tracts clustered in the 0–3°C range, leaving the upper classes nearly empty and making the map look like nothing was happening in most of the county.

**Quantile** — rejected. Forces equal counts per class regardless of the data distribution. This produced misleading results: tracts at +1°C and +5°C ended up in the same class simply because there weren't enough tracts in the upper range to form their own class. For a heat risk map, that kind of flattening is actively harmful to interpretation.

**Standard Deviation** — considered but not used. Produces class breaks at multiples of the standard deviation from the mean, which is statistically meaningful and good for communicating relative deviation. However, it generates break values like −3.12, −1.44, +0.24, +1.92, +3.60 — numbers that are hard to explain to a planning audience. Kept this in mind as a possible alternative for a more technical audience.

**Jenks Natural Breaks (selected)** — best visual separation; class boundaries fell at natural gaps in the data distribution. The 5-class Jenks breaks for this dataset were approximately:
- Class 1: −5.0 to −2.1 (well below average)
- Class 2: −2.1 to −0.4 (below average)
- Class 3: −0.4 to +1.5 (near average)
- Class 4: +1.5 to +4.2 (above average)
- Class 5: +4.2 to +9.1 (well above average)

These broke well at the data's natural clusters and aligned reasonably with the physical geography (parks and campus areas in the lower classes; downtown and industrial areas in the upper classes).

**Number of classes:** 5. Tested 3, 5, and 7.
- 3 classes: too coarse. Merged genuinely different patterns (e.g., Ybor City and residential South Tampa in the same "medium" class).
- 7 classes: too many for a legend at A3 size. Each swatch in the legend became very small.
- 5 classes: right balance. Legend readable, patterns spatially coherent.

---

## Color Ramp Selection

**Goal:** diverging ramp centered at 0°C deviation (county mean), with cool colors for below-average tracts and warm colors for above-average tracts.

**ColorBrewer RdYlBu (reversed) — rejected.** The yellow midpoint class was difficult to read against the white basemap and also looked washed out on screen. Yellow-to-white transitions are challenging in print contexts.

**ColorBrewer RdBu (reversed, selected).** Blue end represents below-average LST (cooler tracts); red end represents above-average LST (hotter tracts). Strong contrast between classes; reads clearly in both color and grayscale.

**Important implementation note:** QGIS's auto-classification "Classify" button places the diverging ramp midpoint at the middle of the data range, not at zero. Since the data range is asymmetric (more values above 0 than below, because some tracts are very hot and no tracts are extremely cool), the auto midpoint was around +2°C rather than 0°C. This was corrected by manually specifying the 5 class breaks after applying the ramp, centering the boundary between class 2 and class 3 at 0°C deviation.

**Colorblind accessibility:** RdBu is not ideal for deuteranopia/protanopia (red-green colorblindness), but the red-to-blue diverging axis is less problematic than a red-green ramp. For a public-facing version, the ColorBrewer "PRGn" (purple-green) ramp would be more accessible and was considered as an alternative.

---

## Map Layout (A3 Landscape)

**Page size:** A3 (420 × 297mm) landscape. Chose A3 over US Letter because:
- More room for the main map without shrinking the legend or inset.
- The county's aspect ratio (roughly 1.4:1 wide) fits A3 landscape much better than letter.
- This format works for both PDF delivery and large-format print.

**Layout panels:**
- Main map frame: ~70% of page width, full height minus margins
- Right panel (~30% width): legend, scale bar, north arrow, inset overview, data sources
- Below legend: bar chart of top 10 / bottom 10 tracts by LST deviation

**Scale bar:** 0–5–10 km, placed in lower-right of main map frame. Confirmed against known distances (see workflow_notes.md). Used "Line Ticks Middle" style — cleaner than the default filled bar.

**North arrow:** Simple single-line arrow (QGIS "Arrow 1" preset). Compass rose was considered and rejected — too decorative for an analytical map, takes up too much space.

**Inset overview map:** Hillsborough County boundary highlighted within a Florida state outline. Shows location context for readers unfamiliar with Tampa. Kept very simple — grey fill, dark outline, no labels.

**Fonts:** Myriad Pro throughout (installed as part of Adobe Creative Suite on my machine). If Myriad Pro isn't available, the QGIS project falls back to Arial. Heading size: 14pt. Body/legend labels: 9pt. Data source footnote: 7pt.

**Grid/graticule:** No grid lines on the main map. The county is small enough that a full graticule would clutter the map. If a grid is needed (e.g., for a military or field use context), UTM grid tick marks at 10km intervals would be appropriate.

**DPI:** 300 DPI for final export. 96 DPI used during layout design (faster preview rendering). Confirmed that the 300 DPI export matched the on-screen layout before finalizing.

---

## Basemap

No raster basemap was used in the final layout. Reasons:
1. The choropleth already shows meaningful spatial information — adding a basemap risks visual clutter.
2. Copyright and attribution requirements for web basemaps (OSM, Stadia, etc.) add complexity for a standalone deliverable.
3. The road network layer (OSM via QuickOSM) was added as a vector layer (thin grey, 0.2pt) to provide spatial reference without competing with the choropleth symbolization.

Considered adding building footprints for the downtown area (available from OSM) but decided against it — too much detail at county scale, and the census tract boundaries already provide sufficient spatial reference.
