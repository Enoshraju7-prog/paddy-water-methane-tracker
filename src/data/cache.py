"""Fetch-once caching, keyed by a hash of the request.

Built before any fetcher, deliberately. You will rerun the pipeline dozens of
times over the next two weeks while tuning the flood threshold, and every rerun
without this re-downloads gigabytes over a home connection. With it, the second
run is free.

The key idea: a cache entry is identified by *what was asked for*, not by a
filename you invent. Hash the request parameters, and identical requests hit the
same file automatically. Change the bbox or a date and you get a fresh key — no
stale-cache bugs, which are the worst kind because the numbers look plausible.

    @disk_cache("s1_series")
    def fetch(field_id: str, start: date, end: date) -> pd.DataFrame:
        ...

    fetch("F001", d1, d2)   # downloads, writes cache
    fetch("F001", d1, d2)   # reads cache, no network
"""

from __future__ import annotations

import functools
import hashlib
import json
import pickle
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any, TypeVar

from src.config import INTERIM_DIR, settings

CACHE_DIR = INTERIM_DIR / "cache"

T = TypeVar("T")


def _stringify(value: Any) -> Any:
    """Make arguments JSON-serialisable so they can be hashed.

    Dates are the reason this exists — they are all over this pipeline and are
    not JSON-serialisable by default. Anything unrecognised falls back to repr(),
    which is imperfect but stable within a run.
    """
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_stringify(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _stringify(v) for k, v in sorted(value.items())}
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return repr(value)


def cache_key(namespace: str, *args: Any, **kwargs: Any) -> str:
    """A short, stable hash of the call signature."""
    payload = json.dumps(
        {"args": _stringify(args), "kwargs": _stringify(kwargs)},
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"{namespace}_{digest}"


def disk_cache(
    namespace: str, enabled: bool | None = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Cache a function's return value on disk, keyed by its arguments.

    `namespace` groups related entries and makes the cache directory readable —
    you can delete `s1_series_*` without touching the weather cache.

    Pickle rather than parquet/JSON because the return types vary (DataFrames,
    dicts, lists of dataclasses) and this is a local, single-user cache. Do not
    point it at untrusted files.
    """
    use = settings.use_cache if enabled is None else enabled

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not use:
                return func(*args, **kwargs)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = CACHE_DIR / f"{cache_key(namespace, *args, **kwargs)}.pkl"

            if path.exists():
                try:
                    with path.open("rb") as fh:
                        return pickle.load(fh)
                except (pickle.UnpicklingError, EOFError):
                    # A run killed mid-write leaves a truncated file. Refetch
                    # rather than crash — a corrupt cache should never be fatal.
                    path.unlink(missing_ok=True)

            result = func(*args, **kwargs)

            # Write to a temp file then rename. Rename is atomic, so an
            # interrupted run can't leave a half-written entry that later reads
            # as valid.
            tmp = path.with_suffix(".tmp")
            with tmp.open("wb") as fh:
                pickle.dump(result, fh)
            tmp.replace(path)

            return result

        wrapper.cache_namespace = namespace  # type: ignore[attr-defined]
        return wrapper

    return decorator


def cache_stats() -> dict[str, tuple[int, float]]:
    """Entries and megabytes per namespace."""
    if not CACHE_DIR.exists():
        return {}
    stats: dict[str, list] = {}
    for path in CACHE_DIR.glob("*.pkl"):
        namespace = path.stem.rsplit("_", 1)[0]
        entry = stats.setdefault(namespace, [0, 0.0])
        entry[0] += 1
        entry[1] += path.stat().st_size / 1e6
    return {k: (v[0], round(v[1], 1)) for k, v in sorted(stats.items())}


def clear_cache(namespace: str | None = None) -> int:
    """Delete cached entries. Returns how many were removed."""
    if not CACHE_DIR.exists():
        return 0
    pattern = f"{namespace}_*.pkl" if namespace else "*.pkl"
    paths = list(CACHE_DIR.glob(pattern))
    for path in paths:
        path.unlink()
    return len(paths)


if __name__ == "__main__":
    from rich import print as rprint

    rprint(f"[bold]cache[/bold]  {CACHE_DIR}")
    stats = cache_stats()
    if not stats:
        rprint("[dim]empty[/dim]")
    for namespace, (count, mb) in stats.items():
        rprint(f"  {namespace:<20} {count:>4} entries  {mb:>7.1f} MB")
