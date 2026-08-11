"""Fetch-once helpers.

You will rerun this pipeline forty times while debugging flood detection. Every
one of those runs must hit disk, not the network. Nothing here is clever — it is
just the discipline of never downloading the same bytes twice, made easy enough
that you actually do it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import settings


def cache_key(**parts: Any) -> str:
    """Stable short hash of the arguments that identify a download.

    Use every parameter that changes the bytes you get back — bbox, dates,
    collection, orbit. Leave out anything cosmetic.
    """
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def cached_frame(path: Path, build: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """Return the parquet at `path`, building and writing it if absent.

        df = cached_frame(
            S1_DIR / f"backscatter_{cache_key(bbox=bbox, start=start)}.parquet",
            lambda: _download_backscatter(bbox, start),
        )
    """
    if settings.use_cache and path.exists():
        return pd.read_parquet(path)

    frame = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return frame


def cached_json(path: Path, build: Callable[[], dict]) -> dict:
    """Same contract as `cached_frame`, for API responses."""
    if settings.use_cache and path.exists():
        return json.loads(path.read_text())

    payload = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return payload
