from __future__ import annotations

import os
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

import yaml


class YamlStorage:
    def __init__(self) -> None:
        self._locks: dict[str, RLock] = defaultdict(RLock)

    def read_yaml(self, path: Path, default: Any | None = None) -> Any:
        lock = self._locks[str(path.resolve())]
        with lock:
            if not path.exists():
                return deepcopy(default)
            with path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
            if data is None:
                return deepcopy(default)
            return data

    def write_yaml_atomic(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._locks[str(path.resolve())]
        temp_path = path.with_name(f"{path.name}.tmp")
        with lock:
            with temp_path.open("w", encoding="utf-8", newline="\n") as file:
                yaml.safe_dump(
                    data,
                    file,
                    allow_unicode=False,
                    sort_keys=False,
                    default_flow_style=False,
                )
            os.replace(temp_path, path)

    def ensure_yaml_file(self, path: Path, default: Any) -> None:
        if path.exists():
            return
        self.write_yaml_atomic(path, default)
