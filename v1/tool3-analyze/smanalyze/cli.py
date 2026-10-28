# -*- coding: utf-8 -*-
"""CLI 入口: smanalyze metrics | plan | run

  smanalyze metrics [--json]          列出指标库(能力边界)
  smanalyze plan <request.yaml>       四态判定预览(不计算)
  smanalyze run <request.yaml>        执行统计引擎, 输出变量表 + 诚实报告
"""
import argparse
import sys
from pathlib import Path

from .export import write_csv, write_json
from .label import run_labeling, write_labels, write_sample_md
from .parser import load_request
from .registry import Registry
from .report import build_report
from .stats import (comment_metrics, derive_eti, list_video_ids,
                    subtitle_text, to_simplified, video_metrics)
from .tasks import list_tasks, load_task
from .verdict import judge_all, summarize

BASE = Path(__file__).resolve().parent.parent      # tool3-analyze/
CONFIG_FILE = BASE / "config.yaml"


def _load_config(path=None) -> dict:
    import yaml
    p = Path(path) if path else CONFIG_FILE
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _load_registry(args) -> Registry:
    return Registry(getattr(args, "metrics_file", None) or (BASE / "metrics.yaml"))


def _cmd_metrics(args) -> int:
    reg = _load_registry(args)
    import json
    if args.json:
        print(json.dumps({"summary": reg.summary(),
                          "metrics": list(reg.metrics.values()),
                          "not_available": reg.not_available},
                         ensure_ascii=False, indent=2))
        return 0
    s = reg.summary()
    print(f"指标库 v{s['version']}: 共 {s['total']} 个指标 (v0 已实现 {s['v0']})")
    print(f"  引擎分布: {s['by_engine']} | 层级: {s['by_level']}")
    print(f"  已知不可得/需补采: {s['not_available']} 项\n")
    print(f"{'metric_id':<28} {'层级':<8} {'引擎':<8} {'v0':<4} 名称")
    print("-" * 78)
    for m in reg.metrics.values():
        print(f"{m['metric_id']:<28} {m.get('level',''):<8} {m.get('engine',''):<8} "
              f"{'✓' if m.get('v0') else '':<4} {m.get('name','')}")
    print("\n已知不可得 / 需补采:")
    for na in reg.not_available:
        print(f"  [{na['status']}] {na['requirement']}: {na.get('reason','')}")
    return 0


def _judge_request(req: dict, reg: Registry):
    """计算覆盖率 → 判定; 返回 (verdicts, coverage_values)"""
    data_dir = (BASE / req["data_dir"]).resolve() if not Path(req["data_dir"]).is_absolute() \
        else Path(req["data_dir"])
    vids = list_video_ids(data_dir)
    coverage = []
    for v in vids:
        try:
            import json
            rec = json.loads((data_dir / v / "video.json").read_text(encoding="utf-8"))
            coverage.append((rec.get("comments") or {}).get("top_level_coverage"))
        except Exception:
            pass
    verdicts = judge_all(req["metrics"] + req.get("tasks", []), reg, coverage)
    return verdicts, coverage, data_dir


def _cmd_plan(args) -> int:
    reg = _load_registry(args)
    req = load_request(args.request)
    verdicts, coverage, data_dir = _judge_request(req, reg)
    print(f">> 分析计划判定 (数据目录: {data_dir})")
    print(f">> 需求项 {len(req['metrics'])} 个\n")
    for v in verdicts:
        print(f"{v['icon']} {v['requirement']}  →  {v['status']}")
        print(f"     {v['reason']}")
        if v.get("detail"):
            print(f"     建议/说明: {v['detail']}")
    s = summarize(verdicts)
    print("\n汇总: " + " | ".join(f"{k}:{len(v)}" for k, v in s.items()))
    return 0


def _load_label_maps(out_dir: Path) -> dict:
    """读取 output 下所有 labels_*.csv → {task_id: {id: label}} (仅 ok 行)"""
    import csv
    maps = {}
    for p in sorted(out_dir.glob("labels_*.csv")):
        task_id = p.stem.replace("labels_", "")
        m = {}
        try:
            for row in csv.DictReader(p.open(encoding="utf-8-sig")):
                if str(row.get("ok")).lower() == "true" and row.get("id"):
                    m[row["id"]] = row.get("label")
        except Exception:
            continue
        if m:
            maps[task_id] = m
    return maps


def _join_labels(rows: list, id_field: str, maps: dict) -> int:
    """把标注列 JOIN 进变量表; 返回新增的列数"""
    if not maps or not rows:
        return 0
    added = 0
    for task_id, m in maps.items():
        if any(task_id in r for r in rows):
            continue                      # 已有该列
        hit = False
        for r in rows:
            key = r.get(id_field)
            if key in m:
                r[task_id] = m[key]
                hit = True
        if hit:
            added += 1
    return added


def _cmd_run(args) -> int:
    reg = _load_registry(args)
    req = load_request(args.request)
    verdicts, coverage, data_dir = _judge_request(req, reg)

    vids = list_video_ids(data_dir)
    if not vids:
        print(f">> 数据目录无视频: {data_dir}")
        return 1
    print(f">> 计算 {len(vids)} 个视频的统计指标 ...")
    rows_video = []
    rows_comment = []
    for v in vids:
        try:
            rows_video.append(video_metrics(data_dir / v))
            if req["include_comments"]:
                rows_comment.extend(comment_metrics(data_dir / v))
        except Exception as e:
            print(f"   [跳过] {v}: {str(e)[:80]}")

    out = Path(getattr(args, "out", None) or req["output_dir"])
    if not out.is_absolute():
        out = (BASE / out).resolve()

    # JOIN 已有标注结果(统计 + 标注合并成一张研究用表)
    label_maps = _load_label_maps(out)
    n_col_v = _join_labels(rows_video, "video_id", label_maps)
    n_col_c = _join_labels(rows_comment, "comment_id", label_maps) if rows_comment else 0
    if label_maps:
        print(f">> JOIN 标注列: 视频层 +{n_col_v} 列, 评论层 +{n_col_c} 列 "
              f"({', '.join(label_maps)})")

    # 因变量派生: ETIR / Strong ETIR / 平均意愿强度 (依赖 willingness_level 标注)
    eti_map = label_maps.get("willingness_level") or {}
    if eti_map and rows_comment:
        eti = derive_eti(rows_comment, eti_map)
        blank = {"eti_n": None, "etir": None, "strong_etir": None, "eti_mean": None}
        for r in rows_video:
            r.update(eti.get(r.get("video_id"), dict(blank)))
        print(f">> 派生因变量 ETIR/StrongETIR/eti_mean "
              f"(基于 {len(eti_map)} 条意愿标注, 覆盖 {len(eti)} 个视频)")
    write_csv(rows_video, out / "variables_video.csv")
    write_json({"metrics": rows_video}, out / "variables.json")
    if rows_comment:
        write_csv(rows_comment, out / "variables_comment.csv")
    report = build_report(verdicts, reg, rows_video, rows_comment, data_dir, coverage)
    (out / "report.md").write_text(report, encoding="utf-8")

    print(f"\n>> 输出目录: {out}")
    print(f"   variables_video.csv   {len(rows_video)} 行 × {len(rows_video[0]) if rows_video else 0} 列")
    if rows_comment:
        print(f"   variables_comment.csv {len(rows_comment)} 行")
    print(f"   variables.json / report.md")
    s = summarize(verdicts)
    print("\n判定汇总: " + " | ".join(f"{k}:{len(v)}" for k, v in s.items()))
    return 0


def _field_value(rec: dict, field, video_dir: Path | None = None) -> str:
    """取字段值; field 支持 'caption' 或 ['caption','subtitles.text'](点号路径)

    Text Liveness 需要"文案+字幕"双通道 → 允许 input_field 声明多个来源。
    特殊键 `subtitles.text` = **纯口播文本**(从 segments 读取, 已剥离时间戳标记);
    `subtitles.full_text` 含 "[0000.00 -> 0001.60] " 标记, 不用于文本分析。
    """
    fields = field if isinstance(field, (list, tuple)) else [field]
    parts = []
    for f in fields:
        key = str(f)
        if key == "subtitles.text" and video_dir is not None:
            txt, _ = subtitle_text(video_dir, rec)
            if txt:
                parts.append(txt)
            continue
        cur = rec
        for seg in key.split("."):
            cur = cur.get(seg) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, list):
            cur = " ".join(str(x) for x in cur)
        if cur:
            parts.append(str(cur))
    return "\n".join(parts)


def _collect_items(req: dict, task, data_dir: Path) -> list:
    """按任务层级收集待标注条目"""
    import json
    vids = list_video_ids(data_dir)
    items = []
    for v in vids:
        rec = json.loads((data_dir / v / "video.json").read_text(encoding="utf-8"))
        if task.level == "video":
            text = to_simplified(_field_value(rec, task.input_field, data_dir / v))
            items.append({"id": v, "video_id": v, "text": text,
                          "likes": (rec.get("stats") or {}).get("likes")})
        else:
            cp = data_dir / v / "comments.json"
            if not cp.exists():
                continue
            for c in json.loads(cp.read_text(encoding="utf-8")):
                items.append({"id": c.get("comment_id"), "video_id": v,
                              "text": c.get("text") or "", "likes": c.get("likes")})
    return items


def _cmd_label(args) -> int:
    cfg = _load_config(getattr(args, "config", None))
    req = load_request(args.request)
    data_dir = Path(req["data_dir"])
    if not data_dir.is_absolute():
        data_dir = (BASE / data_dir).resolve()
    out = Path(args.out or req["output_dir"])
    if not out.is_absolute():
        out = (BASE / out).resolve()

    task_ids = args.tasks or req.get("tasks") or []
    if not task_ids:
        print(">> 未指定标注任务。可用任务: " + ", ".join(list_tasks()))
        return 2

    strategy = args.sample or req.get("sample", "all")
    sample_n = args.sample_n or req.get("sample_n", 0)

    for tid in task_ids:
        task = load_task(tid)
        items = _collect_items(req, task, data_dir)
        print(f"\n===== 任务 {task.task_id} ({task.name}) =====")
        print(f"  层级: {task.level} | 待标注 {len(items)} 条 | 抽样: {strategy} | "
              f"标签数: {len(task.labels)}")
        res = run_labeling(items, task, cfg, out, strategy=strategy,
                           sample_n=sample_n, dry_run=args.dry_run)
        s = res["stats"]
        if args.dry_run:
            print(f"  [dry-run] 预计调用 {s['est_calls']} 次 "
                  f"(batch={s['batch_size']}, 并发={s['workers']}), "
                  f"缓存命中 {s['cache_hits']}")
            print(f"            估算输入 ~{s['est_input_tokens']} tokens / "
                  f"输出 ~{s['est_output_tokens']} tokens")
            continue
        write_labels(res["rows"], out / f"labels_{task.task_id}.csv")
        write_sample_md(res["rows"], task, out / f"labels_sample_{task.task_id}.md")
        print(f"  完成 {s['done']} 条 (失败 {s['failures']}, "
              f"缓存命中 {s['cache_hits']}, 失败率 {s['fail_rate']:.1%})")
        print(f"  → {out / f'labels_{task.task_id}.csv'}")
        print(f"  → {out / f'labels_sample_{task.task_id}.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smanalyze", description="工具3: 数据分析(数据加工层)")
    p.add_argument("--metrics-file", default=None, help="指标库 yaml 路径")
    p.add_argument("--config", default=None, help="配置文件路径")
    sub = p.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("metrics", help="列出指标库(能力边界)")
    pm.add_argument("--json", action="store_true")

    pp = sub.add_parser("plan", help="四态判定预览(不计算)")
    pp.add_argument("request", help="request.yaml")

    pr = sub.add_parser("run", help="执行统计引擎")
    pr.add_argument("request", help="request.yaml")
    pr.add_argument("--out", default=None, help="输出目录(覆盖 request)")

    pl = sub.add_parser("label", help="执行 LLM 标注")
    pl.add_argument("request", help="request.yaml")
    pl.add_argument("--tasks", nargs="*", default=None, help="任务 id(覆盖 request.tasks)")
    pl.add_argument("--sample", default=None, help="抽样策略: all|random_n|top_likes_n")
    pl.add_argument("--sample-n", type=int, default=0, dest="sample_n")
    pl.add_argument("--dry-run", action="store_true", help="只估算成本/预览, 不调用")
    pl.add_argument("--out", default=None, help="输出目录")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "metrics":
            return _cmd_metrics(args)
        if args.cmd == "plan":
            return _cmd_plan(args)
        if args.cmd == "run":
            return _cmd_run(args)
        if args.cmd == "label":
            return _cmd_label(args)
    except FileNotFoundError as e:
        print(f"[错误] 文件不存在: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[错误] {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0
