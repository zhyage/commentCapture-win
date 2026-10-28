# -*- coding: utf-8 -*-
"""汇总 data/douyin 下所有视频的抓取结果"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

base = Path("data/douyin")
for d in sorted(base.iterdir()):
    if not d.is_dir():
        continue
    vp = d / "video.json"
    if not vp.exists():
        continue
    v = json.loads(vp.read_text(encoding="utf-8"))
    cp = d / "comments.json"
    n_comments = len(json.loads(cp.read_text(encoding="utf-8"))) if cp.exists() else 0
    mp4 = d / "video.mp4"
    sub = d / "subtitles.srt"
    st = v.get("stats", {})
    cm = v.get("comments", {})
    au = v.get("author", {})
    print(f"视频ID: {v.get('platform_item_id')}")
    print(f"  作者: {au.get('nickname')} | 粉丝: {au.get('follower_count')}")
    print(f"  文案: {(v.get('caption') or '')[:40]}")
    print(f"  平台统计: 点赞{st.get('likes')} 评论{st.get('comments')} 收藏{st.get('collects')} 转发{st.get('shares')}")
    print(f"  抓到评论: {n_comments} / {st.get('comments')} = {n_comments/max(st.get('comments') or 1,1)*100:.1f}%")
    eng = v.get("author_engagement", {})
    print(f"  作者互动: 回复{eng.get('total_author_replies', 0)} 条 | 翻牌评论 {eng.get('replied_comment_count', 0)} 条")
    print(f"  视频: {'✅ ' + str(round(mp4.stat().st_size/1048576,1)) + 'MB' if mp4.exists() else '❌ 无'}")
    segs = v.get("subtitles", {}).get("segments_count", 0)
    print(f"  字幕: {'✅ ' + str(segs) + ' 段' if sub.exists() else '❌ 无'}")
    print()
