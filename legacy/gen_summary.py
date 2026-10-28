# -*- coding: utf-8 -*-
"""生成交付汇总: output/交付汇总.md"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path("output")
vid = (OUT / "video_id.txt").read_text(encoding="utf-8").strip()
detail = json.loads((OUT / "json" / "detail.json").read_text(encoding="utf-8"))
comments = json.loads((OUT / "json" / "comments.json").read_text(encoding="utf-8"))
aw = detail.get("aweme") or {}

lines = []
lines.append("# 抖音单视频数据交付汇总\n")
lines.append(f"- 视频 ID: `{vid}`")
lines.append(f"- 短链: `https://v.douyin.com/c2lpyv0fzpk/`")
lines.append(f"- 作者: {aw.get('author', {}).get('nickname', '?')}")
st = aw.get("statistics") or {}
lines.append(f"- 数据: 点赞 {st.get('digg_count')} / 评论 {st.get('comment_count')} / 分享 {st.get('share_count')}")
import datetime
ct = aw.get("create_time")
if ct:
    lines.append(f"- 发布时间: {datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M:%S')}")
lines.append("")

lines.append("## 1. 文案\n")
lines.append(aw.get("desc", "") + "\n")

lines.append("## 2. 口播字幕 (Whisper 转写)\n")
sub = OUT / "subtitles" / f"{vid}.txt"
if sub.exists():
    lines.append("```")
    lines.append(sub.read_text(encoding="utf-8"))
    lines.append("```\n")
else:
    lines.append("(转写进行中)\n")

lines.append("## 3. 评论 (含回复)\n")
lines.append(f"- 共抓取 {len(comments)} 条 (评论总数 {st.get('comment_count')}, 本轮为安全采样)\n")
top = sorted(comments.values(), key=lambda c: -(c.get("digg_count") or 0))[:10]
lines.append("### 点赞最高的10条\n")
for c in top:
    rep = (c.get("reply_comment") or {}).get("total") or c.get("reply_comment_total") or 0
    lines.append(f"- 👍{c.get('digg_count')} 💬{rep} | {c.get('text', '')[:100]}")
lines.append("")

lines.append("## 4. 数据文件\n")
lines.append("```")
for p in sorted(OUT.rglob("*")):
    if p.is_file() and ".cache" not in str(p):
        lines.append(f"{p}  ({p.stat().st_size/1024:.0f} KB)")
lines.append("```\n")

(OUT / "交付汇总.md").write_text("\n".join(lines), encoding="utf-8")
print("已生成: output/交付汇总.md")
