# -*- coding: utf-8 -*-
"""批量采集持续监控: 定期输出进度摘要 (队列状态 + 已采目录 + 最近活动)

用法: python tools/monitor_batch.py [--interval 60] [--max-runs 0(不限)]
输出每行一个时间点摘要; 队列全部 done/blocked 或达到 max-runs 后退出。
"""
import argparse
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smfetch.queue import TaskQueue


def data_dirs() -> list[Path]:
    d = BASE / "data" / "douyin"
    return sorted(d.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) if d.exists() else []


def dir_state(p: Path) -> str:
    tags = []
    if (p / "video.json").exists():
        tags.append("详情")
    if (p / "comments.json").exists():
        tags.append("评论")
    if (p / "video.mp4").exists() and (p / "video.mp4").stat().st_size > 1_000_000:
        tags.append("视频")
    if (p / "subtitles.srt").exists():
        tags.append("字幕")
    return "|".join(tags) if tags else "空"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--max-runs", type=int, default=0, help="0=不限")
    args = ap.parse_args()

    q = TaskQueue(BASE / "data" / ".queue.jsonl")
    runs = 0
    print(f"[monitor] 开始监控 (间隔{args.interval}s) @ {datetime.now():%H:%M:%S}", flush=True)
    while True:
        runs += 1
        if args.max_runs and runs > args.max_runs:
            print("[monitor] 达到 max-runs, 退出", flush=True)
            return
        s = q.summary()
        dirs = data_dirs()
        complete = [d for d in dirs if (d / "comments.json").exists()
                    and (d / "video.mp4").exists()
                    and (d / "video.mp4").stat().st_size > 1_000_000]
        now = datetime.now().strftime("%H:%M:%S")
        # 最近活动的 3 个目录
        recent = ""
        if dirs:
            recent = ", ".join(f"{d.name}[{dir_state(d)}]" for d in dirs[:3])
        line = (f"[{now}] 队列 P{s['pending']}/D{s['done']}/B{s['blocked']} "
                f"| 已采 {len(complete)}/{len(dirs)} 完整 | 最新: {recent}")
        print(line, flush=True)
        if s["pending"] == 0 and s["done"] > 0:
            print("[monitor] 队列无待办, 采集结束", flush=True)
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
