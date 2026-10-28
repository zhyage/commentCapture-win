# -*- coding: utf-8 -*-
"""实验4: 点开"日期筛选"确认面板内容 + 确认作品列表默认顺序"""
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"


def main():
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP_URL)
    ctx = b.contexts[0]
    page = ctx.pages[0]

    print("\n===== A. 点击'日期筛选'(locator) =====")
    try:
        loc = page.get_by_text("日期筛选", exact=True).first
        print("  count:", loc.count(), "visible:", loc.is_visible())
        loc.click(timeout=5000)
        time.sleep(2)
        texts = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,li,button,input').forEach(el => {
                const t = (el.innerText || el.textContent || '').trim();
                const r = el.getBoundingClientRect();
                if (t && t.length <= 24 && r.width > 0 && r.height > 0
                    && el.children.length <= 2) out.push(t);
            });
            return [...new Set(out)];
        }""")
        # 只打印日期筛选附近的文本
        print("  面板相关文本:")
        for t in texts:
            if any(k in t for k in ("日期", "今天", "本周", "本月", "最近", "年", "月",
                                    "确定", "取消", "全部", "请选择", "~", "-")):
                print("   |", t)
        page.screenshot(path=str(Path(__file__).resolve().parent / "exp4_datefilter.png"))
        print("  已截图 exp4_datefilter.png")
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception as e:
        print("  异常:", str(e)[:200])

    print("\n===== B. 作品列表前几条的 create_time (验证默认顺序) =====")
    data = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[data-e2e="user-post-item"], li, div').forEach(el => {
            const t = (el.getAttribute('data-e2e')||'');
            if (t === 'user-post-item') {
                out.push({text: (el.textContent||'').trim().slice(0, 60)});
            }
        });
        return out.slice(0, 10);
    }""")
    if data:
        for d in data[:6]:
            print("  ", json.dumps(d, ensure_ascii=False))
    else:
        print("  (未找到 data-e2e=user-post-item, 尝试抓接口响应)")
        # 重新监听一次 post 接口并解析响应里的 create_time
        times = []

        def on_resp(resp):
            if "/aweme/v1/web/aweme/post/" in resp.url:
                try:
                    body = resp.json()
                    for it in (body.get("aweme_list") or []):
                        times.append((it.get("create_time"), (it.get("desc") or "")[:30]))
                except Exception:
                    pass

        page.on("response", on_resp)
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container') || document.body;
            el.scrollTop = 0;
        }""")
        time.sleep(2)
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container') || document.body;
            el.scrollTop += 800;
        }""")
        time.sleep(3)
        page.remove_listener("response", on_resp)
        times.sort(key=lambda x: -(x[0] or 0))
        for ct, d in times[:6]:
            print(f"  create_time={ct} | {d}")

    p.stop()


if __name__ == "__main__":
    main()
