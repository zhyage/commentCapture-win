# -*- coding: utf-8 -*-
"""展示楼中楼与作者回复的分析结果"""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

comments = json.load(open("output/schema-demo/comments.json", encoding="utf-8"))
video = json.load(open("output/schema-demo/video.json", encoding="utf-8"))

total = len(comments)
replies = [c for c in comments if c.get("parent_id")]
top = [c for c in comments if not c.get("parent_id")]
author_replies = [c for c in comments if c.get("user", {}).get("is_author")]

print(f"总记录: {total} | 顶层评论: {len(top)} | 楼中楼回复: {len(replies)}")
print(f"作者回复数: {len(author_replies)}")
print()
print("=== 作者互动聚合 (video.json) ===")
print(json.dumps(video.get("author_engagement"), ensure_ascii=False, indent=2))
print()
print("=== 作者回复样本 (最多10条) ===")
for r in author_replies[:10]:
    parent = next((c for c in comments if c["comment_id"] == r["parent_id"]), None)
    print(f"作者回复: {r['text'][:50]}")
    if parent:
        print(f"   ↳ 回复的评论: [{parent['user']['nickname']}] {parent['text'][:50]}")
    print()
print("=== 被作者回复过的评论 ===")
replied_c = [c for c in comments if c.get("author_replied")]
for c in replied_c[:5]:
    print(f"  [{c['user']['nickname']}] {c['text'][:50]}  → 作者回复{len(c['author_reply_ids'])}条")
