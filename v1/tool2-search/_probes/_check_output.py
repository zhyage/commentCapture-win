# -*- coding: utf-8 -*-
"""检查 results.json: 输出顺序与时间/赞数关系"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
r = json.load(open("results.json", encoding="utf-8"))
print("hits_count(全部符合):", r["hits_count"])
print("hits_output(输出):", r["hits_output"])
print("truncated:", r["truncated"])
print("collected_count:", r["collected_count"])
print()
print("输出 30 条 (按 results.json 顺序):")
for i, x in enumerate(r["results"], 1):
    st = x["stats"]
    print(f"  {i:2d}. {x['publish_time']} 赞{st['likes']:>6} | {x['caption'][:30]}")
