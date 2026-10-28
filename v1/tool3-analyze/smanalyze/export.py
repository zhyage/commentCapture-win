# -*- coding: utf-8 -*-
"""变量表导出: CSV(utf-8-sig) + JSON"""
import csv
import json
from pathlib import Path


def write_csv(rows: list, path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # 并集列(不同视频可能字段略有差异)
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
