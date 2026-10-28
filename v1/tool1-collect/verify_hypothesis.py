# -*- coding: utf-8 -*-
"""验证假设: 平台评论数1937 = 顶层 + 全部回复?"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

cs = json.load(open("data-2000/douyin/7447163286870707508/comments.json", encoding="utf-8"))
top = [c for c in cs if not c.get("parent_id")]
rep = [c for c in cs if c.get("parent_id")]

declared = sum(c.get("reply_count") or 0 for c in top)
print(f"顶层评论: {len(top)}")
print(f"顶层声明的回复总数: {declared}")
print(f"顶层 + 声明回复 = {len(top) + declared}   (平台=1937)")
print(f"实际抓到回复: {len(rep)}")
print(f"已抓总数 {len(cs)} / 1937 = {len(cs)/1937*100:.1f}%")
print(f"回复覆盖: {len(rep)}/{declared} = {len(rep)/declared*100:.1f}%")
print()
print("声明回复最多的8个线程:")
for c in sorted(top, key=lambda x: -(x.get("reply_count") or 0))[:8]:
    got = len([r for r in rep if r.get("parent_id") == c["comment_id"]])
    print(f"  声明{c.get('reply_count'):>4} | 抓到{got:>3} | {c.get('text','')[:25]}")
