# -*- coding: utf-8 -*-
"""实验3: 红河文旅主页 — 决定性验证
1. 点击"日期筛选" → 观察展开面板 (是日期选择器还是排序?)
2. 监听 /aweme/v1/web/aweme/post/ 请求, 滚动一次抓作品列表接口参数 (是否有 sort)
3. 读 window 全局初始数据 (RENDER_DATA 等), 查作品列表字段
"""
import io
import json
import re
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

    print("\n===== A. 点击'日期筛选' → 观察面板 =====")
    try:
        ds = page.evaluate("""() => {
            const cands = [];
            document.querySelectorAll('div,span').forEach(el => {
                const t = (el.textContent||'').trim();
                if (t === '日期筛选' && el.children.length <= 1) cands.push(el);
            });
            return cands.length ? cands[0] : null;
        }""")
        page.evaluate("""(el) => el.click()""", ds)
        time.sleep(2)
        texts = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,li,button').forEach(el => {
                const t = (el.innerText || el.textContent || '').trim();
                const r = el.getBoundingClientRect();
                if (t && t.length <= 20 && r.width > 0 && r.height > 0
                    && el.children.length <= 2) out.push(t);
            });
            return [...new Set(out)];
        }""")
        print("  展开后新增可见文本:", [t for t in texts if t not in
              ["开启读屏标签", "精选", "推荐", "关注", "我的", "直播", "搜索", "作品"]])
        # 截图
        page.screenshot(path=str(Path(__file__).resolve().parent / "exp3_datefilter.png"))
        print("  已截图 exp3_datefilter.png")
        # 关闭面板 (Esc)
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception as e:
        print("  异常:", str(e)[:200])

    print("\n===== B. 监听作品列表接口 + 滚动一次 =====")
    reqs = []

    def on_req(req):
        if "/aweme/v1/web/" in req.url or "/aweme/v1/web/aweme/post/" in req.url:
            reqs.append(req.url)

    page.on("request", on_req)
    # 滚动作品区
    for _ in range(3):
        page.evaluate("""() => {
            const el = document.querySelector('.route-scroll-container')
                       || document.querySelector('.LSOoeXZS')
                       || document.scrollingElement || document.body;
            el.scrollTop += 900;
        }""")
        time.sleep(2.5)
    page.remove_listener("request", on_req)

    seen = set()
    for u in reqs:
        if u in seen:
            continue
        seen.add(u)
        # 提取路径与关键参数
        m = re.match(r"https?://[^/]+(/[^?]*)\?(.*)", u)
        path, qs = (m.group(1), m.group(2)) if m else (u, "")
        params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
        interesting = {k: v for k, v in params.items()
                       if k in ("sort", "sort_type", "order", "tab", "aid",
                                "offset", "cursor", "max_cursor", "count",
                                "post_type", "sec_user_id") or "sort" in k}
        print(f"  {path}")
        print(f"    params: {json.dumps(interesting, ensure_ascii=False)}")

    print("\n===== C. window 全局初始数据 =====")
    globs = page.evaluate("""() => {
        const out = {};
        for (const k of Object.keys(window)) {
            if (/RENDER|INITIAL|STATE|DATA|SSR/i.test(k)) {
                let v = window[k];
                let t = typeof v;
                let s = '';
                try { s = JSON.stringify(v); } catch (e) { s = String(v); }
                out[k] = {type: t, len: s.length, head: s.slice(0, 200)};
            }
        }
        return out;
    }""")
    for k, v in globs.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")

    # 尝试 RENDER_DATA (URL 编码)
    rd = page.evaluate("() => window.RENDER_DATA || window.__INITIAL_STATE__ || ''")
    if isinstance(rd, str) and rd:
        import urllib.parse
        try:
            decoded = urllib.parse.unquote(rd)
            if "post" in decoded.lower():
                idx = decoded.lower().find("aweme/post")
                print("  RENDER_DATA 含 aweme/post 片段:", decoded[max(0, idx-100): idx+300])
        except Exception as e:
            print("  RENDER_DATA 解码异常:", str(e)[:100])

    p.stop()


if __name__ == "__main__":
    main()
