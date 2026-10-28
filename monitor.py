# -*- coding: utf-8 -*-
"""MONITOR.md 生成器 — 每 5 分钟由后台任务重写

设计原则: **动态部分从真实状态采集**(不靠人记), 静态部分读 monitor_state.json。
可观测信号:
  1. CDP 9222 页面 URL  → 实时看到浏览器正在访问哪个账号(预检/采集进度)
  2. 相关 python 进程   → 判断任务是否在跑
  3. precheck_result.json / data 目录 / output 产物 → 产出进度
用法: python monitor.py            (单次生成)
      python monitor.py --loop 300 (每 300 秒生成一次)
"""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "monitor_state.json"
OUT = ROOT / "MONITOR.md"
CDP = "http://127.0.0.1:9222"
TOOL1 = ROOT / "v1" / "tool1-collect"
TOOL2 = ROOT / "v1" / "tool2-search"
TOOL3 = ROOT / "v1" / "tool3-analyze"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------- 动态采集 ----------
def cdp_pages() -> dict:
    """常驻浏览器状态 + 当前打开的抖音页面(实时进度信号)"""
    try:
        with urllib.request.urlopen(CDP + "/json/version", timeout=3) as r:
            ver = json.loads(r.read().decode("utf-8", "replace"))
        with urllib.request.urlopen(CDP + "/json", timeout=3) as r:
            pages = json.loads(r.read().decode("utf-8", "replace"))
        durls = [p.get("url", "") for p in pages
                 if "douyin.com" in p.get("url", "")
                 and "blob:" not in p.get("url", "")
                 and not p.get("url", "").endswith("sw.js")
                 and any(k in p.get("url", "") for k in ("/user/", "/search/", "/video/"))]
        return {"running": True, "browser": ver.get("Browser", "?"),
                "pages": len(pages), "douyin_urls": durls[:8]}
    except Exception as e:
        return {"running": False, "error": str(e)[:80]}


def procs() -> list:
    """与本工程相关的 python 进程, 按脚本归组(父子进程合并, 避免看板重复)"""
    keys = ("run_stage1", "precheck_accounts", "smfetch", "smsearch", "run_visual",
            "smanalyze", "monitor.py")
    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
              "Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | "
              "ConvertTo-Json -Compress")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=25)
        data = json.loads(out.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        pids = {d.get("ProcessId") for d in data}
        groups = {}
        for d in data:
            cmd = d.get("CommandLine") or ""
            hit = [k for k in keys if k in cmd]
            if not hit:
                continue
            key = hit[0]
            short = cmd
            for marker in ("-c ", "-m "):
                if marker in short:
                    short = marker + short.split(marker, 1)[1]
                    break
            g = groups.setdefault(key, {"key": key, "pids": [], "roots": [],
                                        "started": None, "cmd": short[:110].replace("\n", " ")})
            g["pids"].append(d.get("ProcessId"))
            if d.get("ParentProcessId") not in pids:      # 父进程不是 python → 主进程
                g["roots"].append(d.get("ProcessId"))
                g["started"] = d.get("CreationDate")
        return list(groups.values())
    except Exception as e:
        return [{"error": str(e)[:80], "key": "?", "pids": []}]


def video_stats() -> dict:
    d = TOOL1 / "data" / "douyin"
    if not d.exists():
        return {"dirs": 0}
    dirs = [p for p in d.iterdir() if p.is_dir() and (p / "video.json").exists()]
    four = sum(1 for p in dirs if (p / "comments.json").exists() and (p / "video.mp4").exists())
    vis = sum(1 for p in dirs if (p / "visual.json").exists())
    return {"dirs": len(dirs), "four_piece": four, "visual": vis}


def precheck() -> dict:
    f = TOOL2 / "precheck_result.json"
    if not f.exists():
        return {"exists": False}
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        return {"exists": True, "error": str(e)[:60]}
    loc = [r for r in rows if r.get("located")]
    return {"exists": True, "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M"),
            "total": len(rows), "located": len(loc), "rows": rows}


def output_artifacts() -> list:
    d = TOOL3 / "output"
    if not d.exists():
        return []
    files = sorted(d.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]
    return [f"{p.name} ({datetime.fromtimestamp(p.stat().st_mtime):%m-%d %H:%M})" for p in files]


# ---------- 渲染 ----------
def render() -> str:
    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    now = datetime.now()
    cdp, ps, vs, pc, arts = cdp_pages(), procs(), video_stats(), precheck(), output_artifacts()

    L = []
    A = L.append
    A(f"# 监控看板 (MONITOR)")
    A("")
    A(f"> 自动生成: **{now:%Y-%m-%d %H:%M:%S}** ｜ 刷新机制: {st.get('refresh_note', '每 5 分钟')}")
    A(f"> 本文件由 `monitor.py` 重写, 请勿手工编辑; 手工维护的部分在 `monitor_state.json`")
    A("")

    # 1. 正在做什么
    A("## 1. 现在正在做什么")
    A("")
    A(f"**当前聚焦**: {st.get('focus', '(未设置)')}")
    A("")
    A("| 信号 | 观测值 |")
    A("|---|---|")
    A(f"| 常驻浏览器(CDP 9222) | {'✅ 运行中 · ' + str(cdp.get('browser')) if cdp.get('running') else '❌ 未运行'} |")
    A(f"| 打开的页面数 | {cdp.get('pages', '-')} |")
    live = [p for p in ps if "error" not in p and p.get("key") != "monitor.py"]
    if live:
        for p in live:
            since = ""
            if p.get("started"):
                try:
                    t = datetime.strptime(str(p["started"])[:14], "%Y%m%d%H%M%S")
                    mins = int((now - t).total_seconds() // 60)
                    since = f" · 已跑 {mins} 分钟"
                except Exception:
                    pass
            A(f"| 运行中: `{p.get('key')}` | PID {p.get('pids')}{since} |")
    else:
        A("| 相关后台进程 | 无（当前没有采集/加工任务在跑） |")
    A("")
    if cdp.get("douyin_urls"):
        A("**浏览器当前打开的抖音页面**（实时进度信号）:")
        A("")
        for u in cdp["douyin_urls"]:
            A(f"- `{u[:120]}`")
        A("")
    else:
        A("_浏览器当前无抖音页面（可能任务未开始或已完成）_")
        A("")

    # 2. 还需要做什么
    A("## 2. 还需要做什么")
    A("")
    todo = st.get("todo") or []
    if todo:
        A("| # | 事项 | 状态 | 阻塞点 |")
        A("|---|---|---|---|")
        for i, t in enumerate(todo, 1):
            A(f"| {i} | {t.get('item','')} | {t.get('status','')} | {t.get('block','-')} |")
    else:
        A("_(未设置)_")
    A("")

    # 3. 碰到的问题
    A("## 3. 碰到的问题 / 风险")
    A("")
    issues = st.get("issues") or []
    if issues:
        for i in issues:
            A(f"- **[{i.get('level','?')}]** {i.get('text','')}")
    else:
        A("_暂无_")
    A("")

    # 4. 产出进度
    A("## 4. 产出进度（自动采集）")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    A(f"| 已采集视频目录 | {vs.get('dirs', 0)} |")
    A(f"| 其中四件套完整 | {vs.get('four_piece', 0)} |")
    A(f"| 其中视觉派生完成 | {vs.get('visual', 0)} |")
    pcv = "未生成" if not pc.get("exists") else f"{pc.get('located','?')}/{pc.get('total','?')} 定位成功 ({pc.get('mtime','')})"
    A(f"| 账号预检结果 | {pcv} |")
    A("")
    if arts:
        A("**工具3 最近产物**:")
        A("")
        for a in arts:
            A(f"- {a}")
        A("")

    # 5. 预检明细
    if pc.get("rows"):
        A("## 5. 账号预检明细")
        A("")
        A("| 昵称 | 抖音号 | 定位 | 认证主体 | 判定 | sample_role |")
        A("|---|---|---|---|---|---|")
        for r in pc["rows"]:
            cert = (r.get("custom_verify") or r.get("enterprise_verify_reason") or r.get("dom_verify_hint") or "-")
            A(f"| {r.get('nickname') or r.get('input_name','-')} | {r.get('douyin_id','-')} | "
              f"{'✓' if r.get('located') else '✗'} | {cert[:40]} | "
              f"{r.get('account_status') or '-'} | {r.get('sample_role') or '-'} |")
        A("")

    A("---")
    A(f"_本文件仅供监控, 不替代 `PROJECT_STATUS.md`(沉淀) 与 `EXPANSION_PLAN.md`(计划) ｜ 生成器: `monitor.py`_")
    return "\n".join(L) + "\n"


def main() -> int:
    loop = "--loop" in sys.argv
    interval = 300
    if loop:
        try:
            interval = int(sys.argv[sys.argv.index("--loop") + 1])
        except Exception:
            pass
    while True:
        try:
            OUT.write_text(render(), encoding="utf-8")
            print(f"[{datetime.now():%H:%M:%S}] MONITOR.md 已更新")
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] 生成失败: {type(e).__name__}: {str(e)[:120]}")
        if not loop:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
