# -*- coding: utf-8 -*-
"""展示评论样本"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

comments = json.load(open("output/json/comments.json", encoding="utf-8"))
print("总条数:", len(comments))
top = sorted(comments.values(), key=lambda c: -(c.get("digg_count") or 0))[:5]
for c in top:
    rep = (c.get("reply_comment") or {}).get("total") or c.get("reply_comment_total") or 0
    user = ((c.get("user") or {}).get("nickname") or "?")
    text = (c.get("text") or "")[:80]
    print(f"[{user}] 赞{c.get('digg_count')} 回复{rep}: {text}")

replies = [c for c in comments.values() if c.get("reply_id") or c.get("parent_id")]
print()
print("含父评论字段(楼中楼回复)的条数:", len(replies))
