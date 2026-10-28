# -*- coding: utf-8 -*-
"""阶段一扩采 · 工具2 分段运行器

按年份段依次跑 request.stage1.{2024,2025,2026}.yaml, 每段产出独立归档:
    stage1.<seg>.results.json / .uncertain.json / .collected.json
    stage1.<seg>.collected_review.md / .urls.txt / .log
最后合并三段 URL → urls.stage1.txt (按 aweme_id 去重)

为什么必须分段:
  工具2 的输出文件名是固定的(results.json / collected.json / urls.txt ...),
  直接连跑会互相覆盖, 还会覆盖 2026-08-27 的历史爬取缓存(已备份为 archive.20260827.*)。

安全(不可突破):
  - 只读: 工具2 不点赞/关注/评论
  - 节奏: 翻页间隔 2-4s 由工具2 内部控制, 本运行器不干预
  - 登录墙: 工具2 会打印提示并**阻塞等待**; 用户在浏览器扫码后, 在聊天里说"扫好了",
    由外部创建 `v1/tool2-search/.continue.signal` 标记放行; 本运行器**绝不自动跳过**
  - 浏览器: 常驻, 任务结束不关

用法:
    cd D:\\zhy\\抖音\\v1\\tool2-search
    python -u tools/run_stage1.py              # 跑全部三段
    python -u tools/run_stage1.py 2024         # 只跑指定段
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # tool2-search/
MOVES = ("results.json", "uncertain.json", "collected.json", "collected_review.md")
ALL_SEGS = ("2024", "2025", "2026")
SEG_COOLDOWN_S = 300          # 段间冷却(秒) —— 降低限流压力, skill 红线: 不连跑轰炸

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run_segment(seg: str) -> dict:
    """跑单个年份段; 返回 {'seg','rc','seconds','urls','fresh'}"""
    req = BASE / f"request.stage1.{seg}.yaml"
    if not req.exists():
        log(f"✗ 缺少配置: {req}")
        return {"seg": seg, "rc": 2, "seconds": 0, "urls": 0}
    log_path = BASE / f"stage1.{seg}.log"
    urls_path = BASE / f"stage1.{seg}.urls.txt"
    if urls_path.exists():
        urls_path.unlink()                              # 清掉上次残留, 便于判断本次是否成功
    log(f"===== 开始 {seg} 年段 → 日志 {log_path.name} =====")
    t0 = time.time()
    with log_path.open("w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.run(
            [sys.executable, "-u", "-m", "smsearch", req.name, "--out", urls_path.name],
            cwd=str(BASE), stdout=fh, stderr=subprocess.STDOUT,
        ).returncode
    secs = round(time.time() - t0, 1)

    # 只归档**本次新写**的产物 —— 否则会把上一段/历史遗留的旧文件误当本段结果
    for name in MOVES:
        src = BASE / name
        if not src.exists():
            continue
        if src.stat().st_mtime >= t0:
            src.replace(BASE / f"stage1.{seg}.{name}")
        else:
            log(f"   注意: {name} 未被本次更新(旧文件), 不归档")

    n_urls = sum(1 for ln in urls_path.read_text(encoding="utf-8").splitlines() if ln.strip()) \
        if urls_path.exists() else 0
    flag = "✓" if (rc == 0 and n_urls > 0) else "✗"
    log(f"===== {seg} 年段结束 {flag} rc={rc} 耗时 {secs}s 输出 {n_urls} 条 URL =====")
    if n_urls == 0:
        log("   未产出 URL —— 检查日志中的 '收集 0' 或异常; 疑似限流时请冷却后重跑本段")
    return {"seg": seg, "rc": rc, "seconds": secs, "urls": n_urls}


def merge_urls(segs: list) -> tuple:
    """合并各段 URL, 按 aweme_id/video id 去重; 返回 (条数, 路径)"""
    seen, lines = set(), []
    for seg in segs:
        p = BASE / f"stage1.{seg}.urls.txt"
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            key = ln.split("/video/")[1].split("/")[0].split("?")[0] if "/video/" in ln else ln
            if key in seen:
                continue
            seen.add(key)
            lines.append(ln)
    out = BASE / "urls.stage1.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return len(lines), out


def main() -> int:
    segs = [a for a in sys.argv[1:] if a in ALL_SEGS] or list(ALL_SEGS)
    log(f"阶段一扩采: 将依次跑 {segs}（段间冷却 {SEG_COOLDOWN_S}s）")
    results = []
    for i, seg in enumerate(segs):
        results.append(run_segment(seg))
        results[-1].get("urls") or None
        if i < len(segs) - 1:
            # 上一段若无产出(疑似限流) → 加长冷却, 不硬冲
            cool = SEG_COOLDOWN_S if results[-1].get("urls", 0) else SEG_COOLDOWN_S * 4
            log(f"冷却 {cool}s 后进入下一段 ...")
            time.sleep(cool)
    n, out = merge_urls(segs)
    log(f"合并完成: {n} 条去重 URL → {out}")
    log("分段汇总:")
    for r in results:
        log(f"  {r['seg']}: rc={r['rc']} | {r['seconds']}s | {r.get('urls', 0)} 条")
    if n == 0:
        log("!! 三段合计 0 条 URL —— 请检查 stage1.*.log; 疑似限流时冷却后只重跑单段")
    log("下一步: 人工核对 stage1.*.collected_review.md → 定稿 urls.stage1.txt → 工具1 采集")
    return 0 if all(r["rc"] == 0 and r.get("urls", 0) > 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
