from __future__ import annotations

import json
from pathlib import Path


def load_recent_fingerprints(cache_dir: Path) -> set[str]:
    path = cache_dir / "recent_fingerprints.json"
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return set(data.get("fingerprints", []))


def save_recent_fingerprints(cache_dir: Path, fingerprints: set[str], limit: int = 200) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "recent_fingerprints.json"
    trimmed = sorted(fingerprints)[-limit:]
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"fingerprints": trimmed}, handle, indent=2)
