# -*- coding: utf-8 -*-
"""smfetch 命令行入口"""
import argparse
import sys
from pathlib import Path

from . import pipeline
from .config import load_config
from .queue import TaskQueue

BASE = Path(__file__).resolve().parent.parent      # tool1-collect/


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smfetch",
                                description="社交媒体数据采集工具 (v1: 抖音; 安全优先)")
    p.add_argument("--config", default=None, help="配置文件路径 (默认 tool1-collect/config.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="扫码登录 (保存到 profile 目录)")

    pf = sub.add_parser("fetch", help="抓单条: 文案/评论/字幕")
    pf.add_argument("target", help="短链 或 19位数字ID")
    pf.add_argument("--comments", dest="comments", action="store_true", default=True)
    pf.add_argument("--no-comments", dest="comments", action="store_false")
    pf.add_argument("--subtitle", dest="subtitle", action="store_true", default=True,
                    help="转写口播字幕(默认开启)")
    pf.add_argument("--no-subtitle", dest="subtitle", action="store_false",
                    help="不转写")
    pf.add_argument("--video", dest="video", action="store_true", default=None,
                    help="下载视频文件(默认跟随 --subtitle)")
    pf.add_argument("--no-video", dest="video", action="store_false",
                    help="不下载视频文件")
    pf.add_argument("--model", default=None, help="tiny/small/medium/large-v3")
    pf.add_argument("--device", default=None, help="cpu/cuda")
    pf.add_argument("--force", action="store_true", help="忽略已存在数据重抓")

    pb = sub.add_parser("batch", help="批量无人值守 (队列/续跑/通知)")
    pb.add_argument("urls", help="清单文件, 每行一个短链或ID")
    pb.add_argument("--per-day", type=int, default=None, help="单日限额(覆盖配置)")
    pb.add_argument("--reset", action="store_true", help="清空队列重跑")
    pb.add_argument("--no-notify", action="store_true")
    pb.add_argument("--pause", dest="pause", action="store_true", default=False,
                    help="受阻即整批暂停; 默认跳过继续")
    pb.add_argument("--skip-on-block", dest="pause", action="store_false")
    pb.add_argument("--dry-run", action="store_true", help="只解析清单打印计划")
    pb.add_argument("--subtitle", dest="subtitle", action="store_true", default=True)
    pb.add_argument("--no-subtitle", dest="subtitle", action="store_false")
    pb.add_argument("--no-comments", dest="comments", action="store_false", default=True)
    pb.add_argument("--force", action="store_true", help="忽略已存在数据重抓")
    pb.add_argument("--model", default=None)
    pb.add_argument("--device", default=None)

    sub.add_parser("status", help="队列进度与受阻清单")

    pe = sub.add_parser("export", help="导出汇总 CSV/JSON")
    pe.add_argument("--format", default="csv", choices=["csv", "json"])
    pe.add_argument("--scope", default="all", choices=["comments", "videos", "all"])

    pc = sub.add_parser("config", help="配置")
    pc.add_argument("--show", action="store_true")
    return p


def main(argv=None) -> int:
    # Windows 控制台默认 GBK, 中文/emoji 打印会崩; 强制 UTF-8 + 容错 (与工具2一致)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    cfg_path = args.config or (BASE / "config.yaml")
    cfg = load_config(cfg_path)
    if getattr(args, "per_day", None) is not None:
        cfg["safety"]["max_per_day"] = args.per_day

    try:
        if args.cmd == "login":
            from .adapters.douyin import DouyinAdapter
            from .config import resolve_path
            from .risk import RiskController
            adapter = DouyinAdapter(resolve_path(cfg, "profile_dir", BASE),
                                    RiskController(cfg["pacing"], cfg["safety"]))
            return 0 if adapter.login() else 1

        if args.cmd == "fetch":
            try:
                pipeline.fetch_one(cfg, BASE, args.target,
                                   with_comments=args.comments,
                                   with_subtitle=args.subtitle,
                                   with_video=args.video,
                                   model=args.model, device=args.device,
                                   force=args.force)
                return 0
            except Exception as e:
                print(f"[错误] {e}", file=sys.stderr)
                return 2 if "登录" in str(e) else 1

        if args.cmd == "batch":
            res = pipeline.batch_run(cfg, BASE, args.urls, args)
            blocked = res.get("summary", {}).get("blocked", 0)
            return 2 if blocked else 0

        if args.cmd == "status":
            from .config import resolve_path
            output = resolve_path(cfg, "output_dir", BASE)
            q = TaskQueue(output / ".queue.jsonl")
            print("队列:", q.summary())
            for b in q.blocked_list():
                print(f"  受阻 {b.target} | {b.error}")
            return 0

        if args.cmd == "export":
            pipeline.export_all(cfg, BASE, args.format, args.scope)
            return 0

        if args.cmd == "config":
            import yaml
            print(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
            return 0
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
