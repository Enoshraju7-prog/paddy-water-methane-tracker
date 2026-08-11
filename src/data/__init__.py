"""Data acquisition. One module per source, each cached to `data/raw/`.

    fields.py      load + validate field boundaries, area in EPSG:32644
    cache.py       fetch-once helpers — the pipeline reruns constantly
    sentinel1.py   SAR backscatter (the core signal)
    sentinel2.py   NDVI on clear days → crop stage
    weather.py     NASA POWER rainfall + temperature
    soil.py        SoilGrids SOC / clay / pH

Contract for every fetcher: takes a bounding box and a date range, returns a
DataFrame or path, writes nothing outside `data/raw/`, and never re-downloads
something already on disk.
"""
