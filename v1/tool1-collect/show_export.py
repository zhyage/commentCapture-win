# -*- coding: utf-8 -*-
"""展示导出 CSV 的样本内容"""
import csv
import sys

sys.stdout.reconfigure(encoding="utf-8")


def show_csv(path, n=8):
    print(f"===== {path} =====")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("(空)")
        return
    print(f"列: {list(rows[0].keys())}")
    print(f"共 {len(rows)} 行")
    for r in rows[:n]:
        print("-", {k: r[k] for k in r if k in
                    ("comment_id", "parent_id", "user_nickname", "is_author",
                     "likes", "author_replied", "text")})


show_csv("data-2000/export_videos.csv")
print()
show_csv("data-2000/export_comments.csv", 10)
print()
# 作者回复样本
with open("data-2000/export_comments.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
auth = [r for r in rows if r["is_author"] == "1"]
print(f"===== 作者回复样本 ({len(auth)} 条) =====")
for r in auth[:8]:
    print(f"  作者: {r['text'][:50]}")
