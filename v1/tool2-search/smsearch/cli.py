# -*- coding: utf-8 -*-
"""CLI 入口: smsearch <request.yaml> [--out urls.txt]"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .filter import build_honesty_notes, sort_hits_by_likes
from .parser import load_request
from .search import run_douyin_ids, run_search

BASE = Path(__file__).resolve().parent.parent


def _browser_cmd(argv) -> int:
    """smsearch browser start|stop|status — 常驻浏览器管理"""
    from . import service
    if not argv:
        print("用法: smsearch browser start|stop|status")
        return 2
    act = argv[0]
    if act == "start":
        service.start()
        return 0
    if act == "stop":
        service.stop()
        return 0
    if act == "status":
        st = service.status()
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    print(f"未知子命令: {act} (可用: start|stop|status)")
    return 2


def _load_config():
    import yaml
    p = BASE / "config.yaml"
    if not p.exists():
        raise SystemExit(f"缺少配置文件: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def summarize(aw, matched, semantic) -> dict:
    au = aw.get("author") or {}
    st = aw.get("statistics") or {}
    return {
        "aweme_id": aw.get("aweme_id"),
        "url": (aw.get("share_info") or {}).get("share_url"),
        "author": au.get("nickname"),
        "author_uid": au.get("uid"),
        "caption": (aw.get("desc") or "")[:150],
        "publish_time": datetime.fromtimestamp(int(aw["create_time"])).strftime("%Y-%m-%d")
        if aw.get("create_time") else None,
        "stats": {"likes": st.get("digg_count"), "comments": st.get("comment_count"),
                  "collects": st.get("collect_count"), "shares": st.get("share_count")},
        "matched_conditions": matched,
        "semantic": semantic,
    }


def _write_collected_md(collected, req, res, path: Path) -> None:
    """生成人工核对用的 Markdown 清单: 全部收集条目 + URL + 摘要 + 过滤判定"""
    def verdict(c):
        if c["semantic"] == "符合":
            return "✅ 命中"
        if c["semantic"] == "不确定":
            return "❓ 不确定"
        if c["semantic"] is not None:
            return "❌ 语义不符"
        if not c["hard_pass"]:
            return "⛔ 硬过滤淘汰(" + ",".join(c["hard_failed"]) + ")"
        return "— 未判"

    lines = ["# 搜索收集全量清单 (工具2 人工核对)", "",
             f"- 输入: {req.get('keywords') or req.get('douyin_ids')} | 意图: {req['intents']}",
             f"- 硬过滤: {req['filters']} | 排序: {req.get('sort')}",
             f"- 收集 {len(collected)} 条 | 硬过滤通过并语义判定 {sum(1 for c in collected if c['semantic'])} 条",
             f"- 命中 {len(res['hits'])} 条 | 不确定 {len(res['uncertain'])} 条",
             f"- LLM 调用 {res['llm_calls']} 次 | 停止原因: {res.get('stop_reason', '')}",
             ""]
    if res.get("hits_per_account"):
        lines.append("### 按抖音号统计")
        for pa in res["hits_per_account"]:
            lines.append(f"- {pa['douyin_id']}: 收集 {pa['collected']} | 符合 {pa['hits_total']}"
                         f" | 输出 {pa['hits_output']} | {pa['seconds']}s")
        lines.append("")
    for i, c in enumerate(collected, 1):
        st = c["stats"]
        lines += [
            f"## {i}. [{c['author']}] {c['publish_time'] or '?'}",
            f"- URL: {c['short_url']}",
            f"- aweme_id: `{c['aweme_id']}`",
            f"- 赞 {st.get('likes')} / 评 {st.get('comments')} / 藏 {st.get('collects')} / 转 {st.get('shares')}",
            f"- 判定: {verdict(c)}  (硬匹配: {c['hard_matched'] or '无'})",
            f"- 文案: {c['caption']}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f">> collected_review.md / collected.json 已生成 (全量 {len(collected)} 条)")


def _safe_write(path: Path, text: str, label: str) -> bool:
    """写文件并隔离失败 —— 单个输出失败不允许拖垮其余输出。

    (2026-09-13 教训: results.json 序列化崩溃导致 urls.txt 从未写出, 数小时爬取结果全丢)
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True
    except Exception as e:
        print(f"!! 写 {label} 失败: {type(e).__name__}: {str(e)[:120]}")
        return False


def main(argv=None) -> int:
    # Windows 控制台默认 GBK, 中文/emoji 打印会崩; 强制 UTF-8 + 容错
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "browser":
        return _browser_cmd(argv[1:])

    ap = argparse.ArgumentParser(prog="smsearch", description="工具2: 抖音搜索/筛选")
    ap.add_argument("request", help="request.yaml 配置路径")
    ap.add_argument("--out", default=None, help="urls.txt 输出路径")
    args = ap.parse_args(argv)

    cfg = _load_config()
    req = load_request(args.request)
    mode = "douyin_id" if req["douyin_ids"] else "keywords"
    if mode == "douyin_id":
        print(">> 搜索计划 (抖音号模式):")
        print(f"   抖音号: {req['douyin_ids']} | 意图(describe): {req['intents']}")
        print(f"   过滤: {req['filters']} | limit: {req['limit']}")
    else:
        print(">> 搜索计划 (关键词模式):")
        print(f"   关键词: {req['keywords']} | 意图(describe): {req['intents']}")
        print(f"   过滤: {req['filters']} | 排序: {req['sort']} | 目标命中: {req['limit']}")

    res = run_douyin_ids(req, cfg, checkpoint_path=BASE / ".stage1.checkpoint.json") \
        if mode == "douyin_id" else run_search(req, cfg)
    hits, uncertain = res["hits"], res["uncertain"]
    collected = res.get("collected") or []

    # 输出截断到 limit:
    # - 抖音号模式: 已在 run_douyin_ids 内按"每号独立"截断(每号内部按赞降序取前limit, 合并去重)
    # - 关键词模式: 翻页本身按点赞排序, 命中即停无需再排
    if mode == "douyin_id":
        per_account = res.get("hits_per_account") or []
        total_hits = sum(pa["hits_total"] for pa in per_account)
        output_hits = hits
        truncated = total_hits > len(output_hits)
    else:
        per_account = []
        total_hits = len(hits)
        output_hits = hits
        truncated = False

    result = {
        "request": req,
        "performed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "method": ("douyin-user-page-crawl + deepseek-semantic" if mode == "douyin_id"
                   else "douyin-web-search + deepseek-semantic"),
        "llm_calls": res["llm_calls"],
        "hits_count": total_hits,
        "hits_output": len(output_hits),
        "truncated": truncated,
        "collected_count": len(collected),
        "stop_reason": res.get("stop_reason", ""),
        "seconds": res.get("seconds"),
        "honesty_notes": build_honesty_notes(req, res.get("sort_applied", False)),
        "results": [summarize(r["aweme"], r["matched"], r["semantic"]) for r in output_hits],
    }
    if per_account:
        result["per_account"] = per_account

    # ---- 落盘顺序: 先写最有价值的 urls.txt, 再写其余 ----
    # default=str: 兜底任何非 JSON 原生类型(如 datetime.date), 绝不因序列化丢结果
    dump = lambda o: json.dumps(o, ensure_ascii=False, indent=2, default=str)
    urls_path = Path(args.out) if args.out else (BASE / "urls.txt")
    if not urls_path.is_absolute():
        urls_path = BASE / urls_path
    lines = [r["url"] or f"https://www.douyin.com/video/{r['aweme_id']}" for r in result["results"]]
    ok_urls = _safe_write(urls_path, "\n".join(lines), "urls.txt")

    ok_res = _safe_write(BASE / "results.json", dump(result), "results.json")
    _safe_write(BASE / "uncertain.json",
                dump([summarize(r["aweme"], r["matched"], r["semantic"]) for r in uncertain]),
                "uncertain.json")
    # 全量收集清单 (不过滤) —— 供人工核对过滤是否合理
    _safe_write(BASE / "collected.json", dump(collected), "collected.json")
    try:
        _write_collected_md(collected, req, res, BASE / "collected_review.md")
    except Exception as e:
        print(f"!! 写 collected_review.md 失败: {type(e).__name__}: {str(e)[:120]}")

    print("=" * 50)
    print(f"模式: {mode} | 命中(符合) {total_hits} 条 | 输出 {len(output_hits)} 条"
          f" | 不确定 {len(uncertain)} 条 | LLM 调用 {res['llm_calls']} 次"
          + (f" | 总耗时 {res.get('seconds', '?')}s" if mode == "douyin_id" else ""))
    if mode == "douyin_id":
        print(f"全量收集: {len(collected)} 条 | 停止原因: {res.get('stop_reason', '')}")
        for pa in per_account:
            print(f"  - {pa['douyin_id']}: 收集{pa['collected']} | 符合{pa['hits_total']}"
                  f" | 输出{pa['hits_output']} | LLM {pa['llm_calls']}次 | {pa['seconds']}s")
    else:
        print(f"排序切换: {'成功' if res.get('sort_applied') else '未切换(默认排序)'}")
    for r in result["results"][:15]:
        print(f"  [{r['author']}] 赞{r['stats']['likes']} | {r['publish_time']} | "
              f"{r['caption'][:35]}")
    print(f">> results.json / urls.txt / uncertain.json 已生成于 {BASE}")
    print("诚实性说明:")
    for n in result["honesty_notes"]:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
