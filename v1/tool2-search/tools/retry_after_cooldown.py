# -*- coding: utf-8 -*-
"""冷却后自动重试驱动 (2026-09-13 事故后的一次性恢复脚本)

流程:
    等待 COOLDOWN_MIN 分钟
      → 探针 probe_rate_limit.py
          ├─ OK    → 跑 run_stage1.py 2024 (只跑单段, 不再三段连跑)
          └─ EMPTY → 再等 RETRY_MIN 分钟重探 (最多 MAX_ATTEMPTS 次)
    每步都把状态写进 monitor_state.json → MONITOR.md 每 5 分钟自动反映

为什么单独跑 2024: 事故教训 — 三段连跑 6 小时必被限流; 单段可控, 且能先验证
"产物真的落盘"(序列化 bug 已修, 但要用真实运行确认)。

用法:
    cd D:\\zhy\\抖音\\v1\\tool2-search
    python -u tools/retry_after_cooldown.py [初始冷却分钟] [重试间隔分钟] [最大尝试次数]
默认: 150 分钟 → 每 40 分钟重探, 最多 5 次
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # tool2-search/
ROOT = BASE.parent.parent                              # 工程根 D:\zhy\抖音
STATE = ROOT / "monitor_state.json"
LOG = BASE / "retry_cooldown.log"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def set_focus(text: str, issue: str | None = None) -> None:
    """更新监控看板的'当前聚焦'(MONITOR.md 会随之刷新)"""
    try:
        st = json.loads(STATE.read_text(encoding="utf-8"))
        st["focus"] = text
        if issue:
            st.setdefault("issues", [])
            st["issues"] = [i for i in st["issues"] if not str(i.get("text", "")).startswith("【重试驱动】")]
            st["issues"].insert(0, {"level": "进行中", "text": "【重试驱动】" + issue})
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"更新 monitor_state 失败: {str(e)[:80]}")


def probe() -> int:
    log("运行限流探针 ...")
    with LOG.open("a", encoding="utf-8") as fh:
        rc = subprocess.run([sys.executable, "-u", "tools/probe_rate_limit.py"],
                            cwd=str(BASE), stdout=fh, stderr=subprocess.DEVNULL).returncode
    log(f"探针返回 rc={rc} (0=OK 有数据 / 1=EMPTY 仍限流 / 2=定位失败)")
    return rc


def run_segment(seg: str) -> int:
    log(f"限流已解除 → 开始跑 {seg} 年段(单段) ...")
    set_focus(f"🔄 限流已解除，正在跑 {seg} 单段（每号约 10-30 分钟，9 号）",
              f"探针 OK, 已自动启动 {seg} 单段爬取")
    with LOG.open("a", encoding="utf-8") as fh:
        rc = subprocess.run([sys.executable, "-u", "tools/run_stage1.py", seg],
                            cwd=str(BASE), stdout=fh, stderr=subprocess.STDOUT).returncode
    urls = BASE / f"stage1.{seg}.urls.txt"
    n = sum(1 for ln in urls.read_text(encoding="utf-8").splitlines() if ln.strip()) \
        if urls.exists() else 0
    log(f"{seg} 段结束 rc={rc} | 产出 {n} 条 URL")
    return n


def main() -> int:
    cooldown = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    retry_min = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    max_attempts = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    log(f"=== 冷却重试驱动启动: 初始冷却 {cooldown} 分钟, 重试间隔 {retry_min} 分钟, 最多 {max_attempts} 次 ===")
    set_focus(f"⏸ 限流冷却中：{cooldown} 分钟后自动探针；OK 则自动跑 2024 单段",
              f"已启动冷却重试驱动(初始 {cooldown} 分钟)")

    log(f"等待 {cooldown} 分钟冷却 ...")
    time.sleep(cooldown * 60)

    for attempt in range(1, max_attempts + 1):
        log(f"--- 第 {attempt}/{max_attempts} 次探针 ---")
        set_focus(f"⏸ 冷却重试中：第 {attempt}/{max_attempts} 次探针",
                  f"第 {attempt} 次探针(冷却后)")
        rc = probe()
        if rc == 0:
            n = run_segment("2024")
            if n > 0:
                set_focus(f"✅ 2024 段完成，产出 {n} 条 URL；待人工核对后跑 2025/2026",
                          f"2024 单段成功: {n} 条 URL (序列化修复已用真实运行验证)")
                log("下一步(需人工/下次会话): 核对 stage1.2024.collected_review.md → 再跑 2025/2026")
            else:
                set_focus("⚠ 2024 段跑完但 0 条 URL —— 查 stage1.2024.log",
                          "2024 段产出 0 条, 需查日志")
            return 0 if n > 0 else 1
        if rc == 2:
            log("探针 rc=2(定位失败) —— 可能登录态失效, 停止自动重试, 请人工检查浏览器登录态")
            set_focus("⚠ 探针定位失败(疑似登录态失效), 已停止自动重试, 需人工检查",
                      "探针 rc=2: 定位失败, 可能需重新扫码登录")
            return 2
        if attempt < max_attempts:
            log(f"仍被限流, 再等 {retry_min} 分钟后重探 ...")
            time.sleep(retry_min * 60)

    log(f"!! {max_attempts} 次探针仍被限流, 放弃自动重试(浏览器保持打开)")
    set_focus(f"⛔ {max_attempts} 次探针仍被限流，已放弃自动重试；建议跨夜冷却后再试",
              f"{max_attempts} 次探针仍限流(累计约 {cooldown + retry_min*(max_attempts-1)} 分钟)")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
