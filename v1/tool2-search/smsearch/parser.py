# -*- coding: utf-8 -*-
"""请求解析: request.yaml → 搜索计划 (纯逻辑, 可单测)

两种输入模式(互斥):
- keywords 模式: 平台搜索关键词(不做主题硬过滤)
- douyin_id 模式: 抖音号列表 → 进主页全量翻页后过滤 (无排序, 需全量)
describe 不参与搜索(不拆词进 keywords), 作为语义后过滤的意图列表。
"""
import re
from datetime import date, datetime
from pathlib import Path


def _iso_date(v):
    """归一化日期过滤值 → ISO 字符串。

    YAML 会把 `after: 2024-01-01` 解析成 datetime.date 对象; 该对象
    **不可 JSON 序列化**, 会在 cli 写 results.json 时抛 TypeError
    (2026-09-13 实测: 爬完 3.5 小时后崩在最后一步, 全部结果丢失)。
    过滤层用 date.fromisoformat(str(...)) 比较, 字符串形式完全兼容。
    """
    if v is None or v == "":
        return None
    if isinstance(v, datetime):          # datetime 是 date 子类, 必须先判
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v).strip() or None


def load_request(path: str | Path) -> dict:
    import yaml
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw_keywords = [k.strip() for k in (cfg.get("keywords") or []) if k and k.strip()]

    # douyin_id → 抖音号列表 (字符串/数字/列表均可; YAML 纯数字会被解析为 int)
    dids = cfg.get("douyin_id") or []
    if isinstance(dids, (str, int)):
        dids = [dids]
    douyin_ids = [str(d).strip() for d in dids if str(d).strip()]

    if raw_keywords and douyin_ids:
        raise ValueError("keywords 与 douyin_id 不能同时填写 (二选一)")
    if not raw_keywords and not douyin_ids:
        raise ValueError("keywords 或 douyin_id 至少填写一个")

    # describe → 意图列表 (逗号/标点/空白拆分)
    intents = []
    desc = cfg.get("describe")
    if desc:
        intents = [p.strip() for p in re.split(r"[,，、;\s]+", str(desc)) if p.strip()]

    authors = cfg.get("authors")
    if isinstance(authors, str):
        authors = [authors] if authors.strip() else None
    elif authors:
        authors = [a.strip() for a in authors if a and a.strip()] or None

    filters = {
        "after": _iso_date(cfg.get("after")),
        "before": _iso_date(cfg.get("before")),
        "min_likes": cfg.get("min_likes"),
        "min_comments": cfg.get("min_comments"),
        "authors": authors,
    }
    return {
        "keywords": raw_keywords,               # 仅用户给的关键词, 作为搜索词 (不做主题硬过滤)
        "douyin_ids": douyin_ids,               # 抖音号列表 (与 keywords 互斥)
        "intents": intents,                     # 语义后过滤的意图 (任意符合即保留)
        "filters": filters,
        "sort": cfg.get("sort", "likes"),
        "limit": int(cfg.get("limit", 50)),
    }
