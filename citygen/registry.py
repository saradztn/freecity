"""Stable asset registry helpers shared by export and validation."""
from __future__ import annotations
from pathlib import Path
import json
import hashlib


class AssetRegistry:
    def __init__(self, output: Path):
        self.output = Path(output)
        self.assets: list[dict] = []
        self.texture_records: list[dict] = []
        self.stats: dict = {}

    def add_asset(self, record: dict) -> None:
        names = {x["name"] for x in self.assets}
        if record["name"] in names:
            raise ValueError(f"duplicate asset name: {record['name']}")
        self.assets.append(record)

    def add_texture(self, record: dict) -> None:
        self.texture_records.append(record)

    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def sha256(path: Path) -> str:
        h = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(part)
        return h.hexdigest()
