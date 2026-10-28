# -*- coding: utf-8 -*-
"""按统一 schema (v0.1, 平台无关) 生成这条视频的数据样例
输出: output/schema-demo/video.json, comments.json, subtitles.json
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path("output/schema-demo")
OUT.mkdir(parents=True, exist_ok=True)
SCHEMA_VERSION = "0.1"

vid = open("output/video_id.txt", encoding="utf-8").read().strip()
aw = json.load(open("output/json/detail.json", encoding="utf-8"))["aweme"]
comments_raw = json.load(open("output/json/comments.json", encoding="utf-8"))
segs = json.load(open(f"output/subtitles/{vid}.json", encoding="utf-8"))
full_text = open(f"output/subtitles/{vid}.txt", encoding="utf-8").read()
mp4 = Path(f"output/videos/{vid}.mp4")


def ts_to_iso(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S+08:00")


author = aw.get("author", {}) or {}
stats = aw.get("statistics", {}) or {}
hashtags = re.findall(r"#([^\s#]+)", aw.get("desc", ""))

# ---------- 评论记录: 从 reply_id 推导树 + 作者标记 ----------
author_id = author.get("uid")
comment_records = []
for c in comments_raw.values():
    rid = c.get("reply_id") or "0"
    rrid = c.get("reply_to_reply_id") or "0"
    if rrid != "0":
        parent = rrid
    elif rid != "0":
        parent = rid
    else:
        parent = None
    u = c.get("user") or {}
    comment_records.append({
        "comment_id": c.get("cid"),
        "parent_id": parent,
        "user": {
            "id": u.get("uid"),
            "nickname": u.get("nickname"),
            "is_author": (u.get("uid") == author_id),   # 事实字段: 是否视频作者
        },
        "text": c.get("text"),
        "likes": c.get("digg_count"),
        "reply_count": c.get("reply_comment_total"),
        "created_at": ts_to_iso(c.get("create_time")) if c.get("create_time") else None,
        "ip_label": c.get("ip_label"),
        "is_hot": bool(c.get("is_hot")),
        # 派生字段: 作者是否在这条评论下发过回复 (见下方二次遍历填充)
        "author_replied": False,
        "author_reply_ids": [],
    })

# 二次遍历: 填充作者回复的派生标记 (作者回复的父评论)
author_reply_ids_by_parent = {}
for r in comment_records:
    if r["user"]["is_author"] and r["parent_id"]:
        author_reply_ids_by_parent.setdefault(r["parent_id"], []).append(r["comment_id"])
for r in comment_records:
    aids = author_reply_ids_by_parent.get(r["comment_id"])
    if aids:
        r["author_replied"] = True
        r["author_reply_ids"] = aids
        r["author_reply_count"] = len(aids)

# 作者互动聚合
author_replies = [r for r in comment_records if r["user"]["is_author"]]
author_engagement = {
    "total_author_replies": len(author_replies),
    "replied_comment_count": len({r["parent_id"] for r in author_replies if r["parent_id"]}),
    "comments_with_author_reply": sorted({r["parent_id"] for r in author_replies if r["parent_id"]}),
}

video_record = {
    "schema_version": SCHEMA_VERSION,
    "platform": "douyin",
    "platform_item_id": vid,
    "url": f"https://www.douyin.com/video/{vid}",
    "source_short_url": "https://v.douyin.com/c2lpyv0fzpk/",
    "collected_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "author": {
        "id": author.get("uid"),
        "nickname": author.get("nickname"),
        "certification": (json.loads(author.get("account_cert_info") or "{}") or {}).get("label_text"),
        "signature": author.get("signature"),
        "follower_count": author.get("follower_count"),      # 粉丝数
        "following_count": author.get("following_count"),    # 关注数
        "favoriting_count": author.get("favoriting_count"),  # 喜欢数
        "total_favorited": author.get("total_favorited"),    # 获赞总数
        "aweme_count": author.get("aweme_count"),            # 作品数(视频详情接口无, 需抓主页)
    },
    "caption": aw.get("desc"),
    "hashtags": hashtags,
    "publish_time": ts_to_iso(aw.get("create_time")) if aw.get("create_time") else None,
    "stats": {
        "likes": stats.get("digg_count"),
        "comments": stats.get("comment_count"),
        "shares": stats.get("share_count"),
        "collects": stats.get("collect_count"),
        "recommends": stats.get("recommend_count"),
    },
    "media": {
        "type": "video",
        "duration_seconds": round((aw.get("video") or {}).get("duration", 0) / 1000, 1),
        "video_file": str(mp4),
        "size_bytes": mp4.stat().st_size if mp4.exists() else None,
    },
    "subtitles": {
        "source": "whisper",
        "engine": "faster-whisper",
        "model": "faster-whisper-medium",
        "language": "zh",
        "segments_count": len(segs),
        "full_text": full_text,
        "segments_file": "output/schema-demo/subtitles.json",
    },
    "comments": {
        "collected_count": len(comment_records),
        "platform_total": stats.get("comment_count"),
        "coverage_note": "安全模式采样(慢速+轮次上限), 未全量; 可多次运行按comment_id去重合并",
        "file": "output/schema-demo/comments.json",
    },
    "author_engagement": author_engagement,
}

subtitle_records = [
    {"index": i + 1, "start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"]}
    for i, s in enumerate(segs)
]

(video_record_path := OUT / "video.json").write_text(
    json.dumps(video_record, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "comments.json").write_text(
    json.dumps(comment_records, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "subtitles.json").write_text(
    json.dumps(subtitle_records, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 打印可读样例 ----------
print("=" * 50)
print("video.json (统一 schema v0.1)")
print("=" * 50)
print(json.dumps({k: v for k, v in video_record.items() if k not in ("subtitles",)}, ensure_ascii=False, indent=2))
print()
n_replies = sum(1 for r in comment_records if r["parent_id"])
print(f"评论: 共{len(comment_records)}条, 其中楼中楼回复 {n_replies} 条")
print()
print("评论树样例 (前2棵):")
for r in comment_records:
    if r["parent_id"] is None:
        kids = [x for x in comment_records if x["parent_id"] == r["comment_id"]][:2]
        print(f"├─ {r['text'][:30]}  (id={r['comment_id']}, 赞{r['likes']}, 回复{r['reply_count']})")
        for k in kids:
            print(f"│   └─ [回复] {k['text'][:30]}  (parent={k['parent_id']})")
        if len([x for x in comment_records if x["parent_id"] == r["comment_id"]]) > 2:
            print(f"│      ... (共{len([x for x in comment_records if x['parent_id'] == r['comment_id']])}条回复)")
print()
print("字幕前3段:")
for s in subtitle_records[:3]:
    print(f"  [{s['start']:6.2f} -> {s['end']:6.2f}] {s['text']}")
print()
print("文件已写入: output/schema-demo/")
