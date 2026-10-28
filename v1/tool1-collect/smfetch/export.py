# -*- coding: utf-8 -*-
"""导出: schema 数据 → CSV / JSON"""
import csv
import json
from pathlib import Path

COMMENT_CSV_COLUMNS = [
    "comment_id", "parent_id", "user_id", "user_nickname", "is_author",
    "text", "likes", "reply_count", "created_at", "ip_label", "is_hot",
    "author_replied", "author_reply_count",
]


def comments_to_csv(records: list[dict], path: str | Path) -> None:
    """评论(含回复) → CSV, 顶层在前回复随后"""
    from smfetch.schema import sort_comments
    rows = sort_comments(records)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: Excel友好
        w = csv.DictWriter(f, fieldnames=COMMENT_CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = dict(r)
            row["is_author"] = "1" if r.get("is_author") else "0"
            row["author_replied"] = "1" if r.get("author_replied") else "0"
            w.writerow(row)


def video_summary_csv(records: list[dict], path: str | Path) -> None:
    """多条视频主记录 → CSV"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    columns = ["platform", "platform_item_id", "url", "collected_at",
               "author_nickname", "author_follower_count", "author_total_favorited",
               "caption", "publish_time", "stats_likes", "stats_comments",
               "stats_shares", "stats_collects", "comments_collected_count"]
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for r in records:
            w.writerow([
                r.get("platform", ""), r.get("platform_item_id", ""), r.get("url", ""),
                r.get("collected_at", ""),
                (r.get("author") or {}).get("nickname", ""),
                (r.get("author") or {}).get("follower_count", ""),
                (r.get("author") or {}).get("total_favorited", ""),
                (r.get("caption") or "").replace("\n", " "),
                r.get("publish_time", ""),
                (r.get("stats") or {}).get("likes", ""),
                (r.get("stats") or {}).get("comments", ""),
                (r.get("stats") or {}).get("shares", ""),
                (r.get("stats") or {}).get("collects", ""),
                (r.get("comments") or {}).get("collected_count", ""),
            ])


def write_json(obj, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
