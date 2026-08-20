"""实验运行目录辅助函数。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def prepare_run_directory(base_dir: str | Path, run_id: str | None = None) -> Path:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    identifier = run_id or os.environ.get("QUANT_RUN_ID") or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in identifier):
        raise ValueError("run_id may contain only letters, numbers, underscores and hyphens")
    output = base / identifier
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"run directory already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (base / "latest.txt").write_text(identifier, encoding="ascii")
    return output
