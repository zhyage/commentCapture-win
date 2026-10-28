# -*- coding: utf-8 -*-
"""检查现有数据的字段结构, 为统一schema做映射"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

d = json.load(open("output/json/detail.json", encoding="utf-8"))
aw = d["aweme"]
print("=== aweme 顶层字段 ===")
print(sorted(aw.keys()))
print()
print("=== author 字段 ===")
print(json.dumps(aw.get("author", {}), ensure_ascii=False)[:300])
print()
print("=== statistics ===")
print(json.dumps(aw.get("statistics", {}), ensure_ascii=False))
print()
print("=== video 字段 ===")
print(sorted(aw.get("video", {}).keys()))
print()
c = json.load(open("output/json/comments.json", encoding="utf-8"))
first = next(iter(c.values()))
print("=== 一条评论的字段 ===")
print(sorted(first.keys()))
print()
print("=== 该评论部分内容 ===")
print(json.dumps({k: first[k] for k in ("cid", "text", "digg_count", "create_time", "reply_comment_total", "reply_id", "reply_to_reply_id") if k in first}, ensure_ascii=False, indent=1)[:600])
