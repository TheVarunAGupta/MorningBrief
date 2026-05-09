from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config_dir(config_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_json_config(config_dir / "sources.yml"),
        load_json_config(config_dir / "source_profiles.yml"),
        load_json_config(config_dir / "ranking.yml"),
    )
