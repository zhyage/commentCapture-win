# -*- coding: utf-8 -*-
"""请求解析: request.yaml → 分析计划 (纯逻辑, 可单测)"""
from pathlib import Path


def load_request(path: str | Path) -> dict:
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    metrics = cfg.get("metrics") or []
    if isinstance(metrics, str):
        metrics = [metrics]
    metrics = [str(m).strip() for m in metrics if str(m).strip()]

    tasks = cfg.get("tasks") or []
    if isinstance(tasks, str):
        tasks = [tasks]

    return {
        "data_dir": cfg.get("data_dir") or "../tool1-collect/data/douyin",
        "metrics": metrics,
        "tasks": [str(t).strip() for t in tasks if str(t).strip()],
        "sample": cfg.get("sample", "all"),          # all | random_n | top_likes_n
        "sample_n": int(cfg.get("sample_n", 0) or 0),
        "output_dir": cfg.get("output_dir") or "./output",
        "comment_level": bool(cfg.get("comment_level", False)),
        "include_comments": bool(cfg.get("include_comments", True)),
    }


def request_from_text(text: str) -> dict:
    """占位: 自由文本需求解析(v0.3 用 LLM 实现)。v0.1 仅做简单逗号/顿号切分。"""
    import re
    parts = [p.strip() for p in re.split(r"[,，、;\s]+", text or "") if p.strip()]
    return {"metrics": parts}
