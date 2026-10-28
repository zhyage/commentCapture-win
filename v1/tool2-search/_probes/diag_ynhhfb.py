# -*- coding: utf-8 -*-
"""诊断: YNHHFB 搜索定位失败原因 — 打印所有候选卡片的抖音号提取结果"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect

DID = "YNHHFB"


def main():
    ctx, page = connect()
    page.goto("https://www.douyin.com/", timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)
    box = page.locator("input").first
    box.fill(DID)
    time.sleep(1)
    box.press("Enter")
    time.sleep(8)
    print(">> URL:", page.url)

    # 打印所有含"抖音号"的卡片原始文本 (前15个)
    raw = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a[href*="/user/"]')) {
            const t = (el.textContent || '').trim();
            if (t.includes('抖音号') || t.includes('获赞')) {
                out.push(t.slice(0, 120));
            }
        }
        return out.slice(0, 15);
    }""")
    print("\n== 含'抖音号'的卡片文本 ==")
    for t in raw:
        print("  |", repr(t[:90]))

    # 有没有名字含 YNHHFB 的?
    named = page.evaluate("""(d) => {
        const out = [];
        for (const el of document.querySelectorAll('a[href*="/user/"]')) {
            const t = (el.textContent || '').trim();
            if (t.toUpperCase().includes(d)) out.push(t.slice(0, 90));
        }
        return out;
    }""", DID)
    print("\n== 文本含 YNHHFB 的卡片 ==")
    for t in named:
        print("  |", repr(t[:90]))
    if not named:
        print("  (无) — 搜索结果里没有该抖音号?")


if __name__ == "__main__":
    main()
