# -*- coding: utf-8 -*-
"""离线重排: 从 collected.json 的命中(符合)按点赞降序取前 limit 条, 更新 urls.txt / results.json
不碰浏览器, 不重跑采集。
"""
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    collected = json.load(open(BASE / "collected.json", encoding="utf-8"))
    hits = [x for x in collected if x["semantic"] == "符合"]
    print(f"collected: {len(collected)} | 命中(符合): {len(hits)} | 取前 {limit}")

    # 按赞降序
    hits_sorted = sorted(hits, key=lambda x: (x["stats"].get("likes") or 0), reverse=True)
    top = hits_sorted[:limit]

    # 更新 urls.txt (与 cli 一致: 用 share_url, 缺则 douyin.com/video/id)
    lines = [x["url"] or f"https://www.douyin.com/video/{x['aweme_id']}" for x in top]
    (BASE / "urls.txt").write_text("\n".join(lines), encoding="utf-8")

    # 更新 results.json (保留原结构, 替换 results 并更新字段)
    if (BASE / "results.json").exists():
        result = json.load(open(BASE / "results.json", encoding="utf-8"))
    else:
        result = {"request": {}, "performed_at": None, "method": "douyin-user-page-crawl + deepseek-semantic",
                  "honesty_notes": [], "uncertain_count": 0}
    result["request"]["limit"] = limit
    result["performed_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    result["hits_count"] = len(hits)
    result["hits_output"] = len(top)
    result["truncated"] = len(hits) > limit
    result["sort_by"] = "likes_desc"
    result["results"] = []
    for x in top:
        st = x["stats"]
        result["results"].append({
            "aweme_id": x["aweme_id"],
            "url": x["url"],
            "author": x["author"],
            "author_uid": x["author_uid"],
            "caption": x["caption"][:150],
            "publish_time": x["publish_time"],
            "stats": st,
            "matched_conditions": x["hard_matched"],
            "semantic": x["semantic"],
        })
    (BASE / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 50)
    print(f"按点赞降序前 {limit} 条:")
    for i, x in enumerate(top, 1):
        st = x["stats"]
        print(f"  {i:2d}. 赞{st.get('likes'):>6} | {x['publish_time']} | {x['caption'][:32]}")
    print(f">> urls.txt / results.json 已更新 (共 {len(top)} 条)")


if __name__ == "__main__":
    main()
