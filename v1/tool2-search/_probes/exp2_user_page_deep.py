# -*- coding: utf-8 -*-
"""实验2: 红河文旅主页 — 深挖隐藏排序控件
1. 检查 open shadow roots
2. hover "作品" tab → 看是否展开菜单 (像搜索页"筛选"一样 hover 触发)
3. 检查 "日期筛选" 元素结构与 hover 行为
4. 检查 "作品" tab outerHTML 是否有下拉图标
只读 hover, 不点击。
"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"


def dump_visible_short(page, label):
    texts = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('div,span,li,button,a,p').forEach(el => {
            const t = (el.innerText || el.textContent || '').trim();
            const r = el.getBoundingClientRect();
            if (t && t.length <= 20 && r.width > 0 && r.height > 0
                && el.children.length <= 2) out.push(t);
        });
        return [...new Set(out)];
    }""")
    print(f"  [{label}] 可见短文本: {texts}")


def main():
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.pages[0]
    # 确认在主页
    if "/user/" not in page.url:
        print(">> 不在用户主页, 先导航 ...")
        page.goto("https://www.douyin.com/user/MS4wLjABAAAAzV1wNMOd-askb-PxHj8I8lWfvXMgy8MFgLy3g7mLuiM?from_tab_name=main&showSubTab=video&showTab=post",
                  timeout=90000, wait_until="domcontentloaded")
        time.sleep(6)

    print("\n===== A. shadow DOM 检查 =====")
    shadows = page.evaluate("""() => {
        const out = [];
        function walk(root, path) {
            if (root.shadowRoot) {
                out.push({path, nodes: root.shadowRoot.querySelectorAll('*').length,
                          text: (root.shadowRoot.textContent||'').trim().slice(0,80)});
                walk(root.shadowRoot, path + '>shadow');
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) walk(el, path + '>' + (el.tagName||'').toLowerCase());
            }
        }
        walk(document, 'doc');
        return out;
    }""")
    if not shadows:
        print("  (无 open shadow root)")
    for s in shadows[:10]:
        print(" ", json.dumps(s, ensure_ascii=False))

    print("\n===== B. '作品' tab (semiTabvideo) outerHTML =====")
    html = page.evaluate("""() => {
        const el = document.querySelector('#semiTabvideo') || document.querySelector('#semiTabpost');
        return el ? el.outerHTML.slice(0, 1500) : 'NOT FOUND';
    }""")
    print(html)

    print("\n===== C. hover '作品' tab → 观察变化 =====")
    dump_visible_short(page, "hover前")
    tab = page.locator("#semiTabvideo").first
    try:
        tab.hover(timeout=5000)
        time.sleep(2)
        dump_visible_short(page, "hover后")
    except Exception as e:
        print("  hover 异常:", str(e)[:100])

    print("\n===== D. '日期筛选' 区域结构 =====")
    html2 = page.evaluate("""() => {
        const cands = [];
        document.querySelectorAll('div,span').forEach(el => {
            const t = (el.textContent||'').trim();
            if (t === '日期筛选' && el.children.length <= 1) cands.push(el);
        });
        return cands.slice(0, 3).map(el => {
            const r = el.getBoundingClientRect();
            return {x: Math.round(r.x), y: Math.round(r.y),
                    html: el.outerHTML.slice(0, 600)};
        });
    }""")
    for h in html2:
        print(" ", json.dumps(h, ensure_ascii=False))

    print("\n===== E. hover '日期筛选' → 观察变化 =====")
    ds = page.evaluate("""() => {
        const cands = [];
        document.querySelectorAll('div,span').forEach(el => {
            const t = (el.textContent||'').trim();
            if (t === '日期筛选' && el.children.length <= 1) cands.push(el);
        });
        return cands.length ? cands[0] : null;
    }""")
    if ds:
        try:
            page.evaluate("""(el) => {
                const ev = new MouseEvent('mouseover', {bubbles: true});
                el.dispatchEvent(ev);
            }""", ds)
            time.sleep(2)
            dump_visible_short(page, "hover日期筛选后")
        except Exception as e:
            print("  hover 异常:", str(e)[:100])

    print("\n===== F. tab 栏内所有 icon/svg 元素 =====")
    icons = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('#user-tabbar svg, #user-tabbar i, #user-tabbar-2 svg, #user-tabbar-2 i, .dlxtet7x svg').forEach(el => {
            const r = el.getBoundingClientRect();
            out.push({tag: el.tagName, cls: (el.getAttribute('class')||'').slice(0,60),
                      x: Math.round(r.x), y: Math.round(r.y),
                      w: Math.round(r.width), h: Math.round(r.height)});
        });
        return out;
    }""")
    for i in icons:
        print(" ", json.dumps(i, ensure_ascii=False))
    if not icons:
        print("  (无 svg/i 图标)")

    p.stop()


if __name__ == "__main__":
    main()
