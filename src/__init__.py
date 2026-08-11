"""Paddy Water & Methane Tracker — batch pipeline.

    src/data/          fetch + cache one module per source
    src/features/      backscatter → flooded/dry → season metrics
    src/models/        IPCC Tier 2 methane, AWD scenario, water & cost
    src/visualization/ per-field timeline charts

Nothing in here runs inside a web request. See docs/00-project-explainer.md §4.
"""

__version__ = "0.1.0"
