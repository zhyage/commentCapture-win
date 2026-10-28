# -*- coding: utf-8 -*-
"""诊断2: 搜索页 tab 栏真实结构 — 找'用户'tab 的可靠选择器"""
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
    page.goto("https://www.douyin.com/", timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)
    box = page.locator("input").first
    box.fill(DID)
    time.sleep(1)
    box.press("Enter")
    time.sleep(8)
    print(">> URL:", page.url)

    # 1) 所有 role=tab 元素
    tabs = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[role="tab"]').forEach(el => {
            const r = el.getBoundingClientRect();
            out.push({tag: el.tagName, text: (el.textContent||'').trim().slice(0,20),
                      cls: (el.className||'').toString().slice(0,60),
                      e2e: el.getAttribute('data-e2e'),
                      aria: el.getAttribute('aria-label'),
                      visible: r.width>0 && r.height>0,
                      x: Math.round(r.x), y: Math.round(r.y)});
        });
        return out;
    }""")
    print("\n== role=tab 元素 ==")
    for t in tabs:
        print("  ", t)

    # 2) 含"用户"文本的较小元素(可能是 tab 内部)
    us = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('div,span,li,a').forEach(el => {
            const t = (el.textContent||'').trim();
            const r = el.getBoundingClientRect();
            if (t === '用户' && el.children.length === 0 && r.width > 0 && r.height > 0) {
                let p = el.parentElement;
                out.push({tag: el.tagName, cls: (el.className||'').toString().slice(0,50),
                          ptag: p ? p.tagName : '', pcls: p ? (p.className||'').toString().slice(0,70) : '',
                          pe2e: p ? p.getAttribute('data-e2e') : '',
                          x: Math.round(r.x), y: Math.round(r.y)});
            }
        });
        return out;
    }""")
    print("\n== 精确文本'用户'的叶子元素及其父节点 ==")
    for u in us:
        print("  ", u)

    # 3) 点击真正的用户 tab 后 URL 变化
    print("\n== 尝试点击 '用户' tab (精确文本+最近tabbar) ==")
    clicked = page.evaluate("""() => {
        const cands = [];
        document.querySelectorAll('div,span,li,a').forEach(el => {
            const t = (el.textContent||'').trim();
            const r = el.getBoundingClientRect();
            if (t === '用户' && el.children.length === 0 && r.width > 0 && r.height > 0) {
                // 往上找 tabbar 容器
                let p = el;
                for (let i = 0; i < 5; i++) {
                    p = p.parentElement;
                    if (!p) break;
                    if (/tab/i.test(p.className||'') || p.getAttribute('role') === 'tablist') break;
                }
                cands.push({el, container: p ? (p.className||'').toString().slice(0,60) : ''});
            }
        });
        if (cands.length) {
            cands[0].el.click();
            return {ok: true, container: cands[0].container};
        }
        return {ok: false};
    }""")
    print("  点击结果:", clicked)
    time.sleep(6)
    print("  点击后 URL:", page.url)
    # 提取卡片
    cards = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a[href*="/user/"]')) {
            const t = (el.textContent || '').trim();
            const m = t.match(/抖音号[:：]\\s*([0-9A-Za-z_]+)/);
            if (!m) continue;
            const r = el.getBoundingClientRect();
            out.push({digits: m[1], nick: t.slice(0, 25), visible: r.width > 0 && r.height > 0});
        }
        return out.slice(0, 8);
    }""")
    print("  卡片:", cards)


if __name__ == "__main__":
    main()
