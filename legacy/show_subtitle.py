# -*- coding: utf-8 -*-
"""展示 medium 转写结果"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

vid = open("output/video_id.txt", encoding="utf-8").read().strip()
segs = json.load(open(f"output/subtitles/{vid}.json", encoding="utf-8"))
print("===== medium 转写 (带时间戳) =====")
for s in segs:
    print(f"[{s['start']:07.2f} -> {s['end']:07.2f}] {s['text']}")
print()
print("===== 纯文本 =====")
print(" ".join(s["text"] for s in segs))
