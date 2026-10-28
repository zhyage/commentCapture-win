# -*- coding: utf-8 -*-
"""检查已抓取评论的 reply_comment 字段是否内嵌回复, 以及字段结构"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

comments = json.load(open("output/json/comments.json", encoding="utf-8"))
items = list(comments.values())

print(f"共 {len(items)} 条")
# 1) reply_id 分布
rids = {}
for c in items:
    k = (c.get("reply_id") or "0", c.get("reply_to_reply_id") or "0")
    rids[k] = rids.get(k, 0) + 1
print("reply_id / reply_to_reply_id 分布:", rids)

# 2) reply_comment 字段结构
c0 = items[0]
rc = c0.get("reply_comment") or {}
print()
print("第一条评论的 reply_comment 字段 keys:", sorted(rc.keys()))
print("reply_comment.total:", rc.get("total"))
print("reply_comment.replies 条数:", len(rc.get("replies") or []))
if rc.get("replies"):
    r0 = rc["replies"][0]
    print("内嵌回复[0] 的 keys:", sorted(r0.keys()))
    print("内嵌回复[0] reply_id:", r0.get("reply_id"), "| text:", (r0.get("text") or "")[:40])
    print("内嵌回复[0] user.nickname:", ((r0.get("user") or {}).get("nickname")))
    print("内嵌回复[0] 是否作者:", r0.get("user", {}).get("uid") == "405032890799566")

# 3) 所有评论里内嵌回复的总数
total_embedded = sum(len((c.get("reply_comment") or {}).get("replies") or []) for c in items)
print()
print(f"全部评论中内嵌回复总数: {total_embedded}")
