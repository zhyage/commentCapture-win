# -*- coding: utf-8 -*-
"""诊断3: 直开标准搜索页 /search/<did>?type=user — 能否直接出用户结果(免点tab)"""
import io
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect

DID = "55008743593"


def main():
    ctx, page = connect()
    for url, label in [
        (f"https://www.douyin.com/search/{DID}?type=user", "标准搜索页 type=user"),
        (f"https://www.douyin.com/search/{DID}?type=general", "标准搜索页 type=general"),
    ]:
        print(f"\n===== {label} =====")
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(7)
        print("  URL:", page.url)
        print("  title:", page.title())
        login = page.evaluate("() => (document.body.textContent||'').includes('扫码登录')")
        print("  登录墙:", login)
        # 用户卡片
        cards = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('a[href*="/user/"]')) {
                const t = (el.textContent || '').trim();
                const m = t.match(/抖音号[:：]\\s*([0-9A-Za-z_]+)/);
                if (!m) continue;
                const r = el.getBoundingClientRect();
                out.push({digits: m[1], nick: t.slice(0, 20), visible: r.width > 0 && r.height > 0});
            }
            return out.slice(0, 6);
        }""")
        print("  用户卡片:", cards)


if __name__ == "__main__":
    main()
