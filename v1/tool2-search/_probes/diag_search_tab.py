# -*- coding: utf-8 -*-
"""诊断: 抖音号搜索定位为何 0 候选 (复现 _find_user_by_did 步骤, 逐步观察)"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from smsearch.browser import connect

DID = "55008743593"


def main():
    ctx, page = connect()
    print(">> 当前 URL:", page.url)
    print(">> goto 首页 ...")
    page.goto("https://www.douyin.com/", timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)
    print(">> 首页 title:", page.title())
    print(">> 首页 URL:", page.url)

    # 找输入框
    inputs = page.locator("input").count()
    print(">> input 数量:", inputs)
    box = page.locator("input").first
    box.fill(DID)
    time.sleep(1)
    box.press("Enter")
    time.sleep(8)
    print(">> 回车后 URL:", page.url)
    print(">> 回车后 title:", page.title())

    # 诊断可见 tab
    tabs = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[role="tab"], [data-e2e*="tab"], span, div').forEach(el => {
            const t = (el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            if (t && t.length <= 8 && r.width > 0 && r.height > 0 && t.includes('用户')) {
                out.push({tag: el.tagName, text: t,
                          cls: (el.className||'').toString().slice(0,50)});
            }
        });
        return out.slice(0, 15);
    }""")
    print(">> 含'用户'的可见元素:", tabs)

    # 是否出现登录墙/验证码?
    login = page.evaluate("""() => {
        const txt = document.body.textContent || '';
        return txt.includes('扫码登录') || txt.includes('验证') || txt.includes('安全验证');
    }""")
    print(">> 页面含登录/验证字样:", login)

    p = ctx.new_page() if False else None


if __name__ == "__main__":
    main()
