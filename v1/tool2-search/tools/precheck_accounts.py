# -*- coding: utf-8 -*-
"""账号预检: 只定位账号 + 读认证主体, **不翻页、不采集任何视频**

v2 (2026-09-11): 改为**从搜索结果卡片读认证主体**。
  原因: 主页 DOM 经常不渲染"抖音号:"字段 → 工具2 的 _verify_profile_did 会失败并放弃整个账号;
        而搜索卡片的 `认证徽章<主体名>` 才是稳定可得的主体证据(且是平台认证, 不可伪造)。

用法:
    cd D:\\zhy\\抖音\\v1\\tool2-search
    python tools/precheck_accounts.py accounts.stage1.txt

输入: 每行 "昵称, 抖音号" (或只有抖音号), # 开头为注释
输出: precheck_result.json + 控制台判定表

安全: 复用常驻浏览器(CDP 9222); 只读; 账号间冷却 6-10s。
"""
import json
import random
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))                              # → smsearch
sys.path.insert(0, str(BASE.parent / "tool3-analyze"))     # → smanalyze

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from smsearch import service                               # noqa: E402
from smsearch.search import _ensure_login, USER_SEARCH_URL  # noqa: E402

try:
    from smanalyze.stats import account_status, load_accounts
except Exception:
    account_status = None
    load_accounts = None


def parse_list(path: Path) -> list:
    out = []
    # utf-8-sig: 兼容记事本/PowerShell 写出的带 BOM 清单(否则首个昵称会带 \ufeff)
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        out.append((parts[0], parts[1]) if len(parts) >= 2 else (parts[0], parts[0]))
    return out


def cards_with_cert(page) -> list:
    """提取用户卡片: 抖音号 / 昵称 / 认证主体 / sec_uid (卡片文本取全, 不截断)

    卡片文本形态: "<昵称>认证徽章<认证主体>...抖音号: <号码><粘连的获赞数>"
    """
    return page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a[href*="/user/"]')) {
            const t = (el.textContent || '').replace(/\\s+/g, ' ').trim();
            if (!t || t.indexOf('抖音号') < 0) continue;
            out.push({ text: t.slice(0, 300), href: el.getAttribute('href') || '' });
        }
        return out;
    }""")


def parse_card(card: dict) -> dict:
    t = card.get("text") or ""
    m = re.search(r"抖音号[:：]\s*([0-9A-Za-z_]+)", t)
    cert = ""
    cm = re.search(r"认证徽章(.+?)(?=抖音号|关注|粉丝|获赞|作品|$)", t)
    if cm:
        cert = cm.group(1).strip()
    nick = t.split("认证徽章")[0].strip()[:40]
    sec = ""
    sm = re.search(r"/user/([A-Za-z0-9_\-\.]+)", card.get("href") or "")
    if sm:
        sec = sm.group(1)
    return {"digits": m.group(1) if m else None, "nickname": nick,
            "certification": cert, "sec_uid": sec, "card_text": t}


def match_cards(cards: list, did: str) -> list:
    """按抖音号前缀匹配(处理获赞数粘连)"""
    up = did.upper()
    out, seen = [], set()
    for c in cards:
        d = (c.get("digits") or "").upper()
        if not d:
            continue
        if d == up or (d.startswith(up) and len(d) > len(did)):
            if c["sec_uid"] and c["sec_uid"] not in seen:
                seen.add(c["sec_uid"])
                out.append(c)
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools/precheck_accounts.py accounts.stage1.txt [输出json路径]")
        return 2
    targets = parse_list(Path(sys.argv[1]))
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else (BASE / "precheck_result.json")
    print(f">> 账号预检 v2 (卡片读认证): {len(targets)} 个, 只读不采集\n")

    p, b, ctx, page = service.connect()
    if not _ensure_login(page, ctx):
        print(">> 登录未就绪, 中止")
        return 3
    cfg = load_accounts() if load_accounts else {}
    results = []

    for name, did in targets:
        print(f"===== {name} ({did}) =====")
        row = {"input_name": name, "douyin_id": did, "located": False}
        try:
            page.goto(USER_SEARCH_URL.format(did=did), timeout=60000,
                      wait_until="domcontentloaded")
            time.sleep(7)
            cards = [parse_card(c) for c in cards_with_cert(page)]
        except Exception as e:
            row["error"] = f"搜索页异常: {str(e)[:80]}"
            cards = []
        cands = match_cards(cards, did)

        # 优先选卡片里带"认证徽章"的候选(主体证据最强)
        best = next((c for c in cands if c.get("certification")), None) or (cands[0] if cands else None)
        row["candidates"] = len(cands)
        if not best:
            print(f"  ✗ 未匹配到候选 (页面卡片 {len(cards)} 个)\n")
            results.append(row)
            time.sleep(random.uniform(6, 10))
            continue

        row.update({"located": bool(best.get("sec_uid")), "sec_uid": best.get("sec_uid"),
                    "nickname": best.get("nickname"), "card_digits": best.get("digits"),
                    "certification": best.get("certification"),
                    "card_matched": best.get("card_text", "")[:160]})
        au = {"id": None, "nickname": best.get("nickname"),
              "certification": best.get("certification")}
        if account_status:
            row.update(account_status(au, cfg))
        print(f"  ✓ 匹配 {row['candidates']} 个候选 | 昵称={row['nickname']}")
        print(f"    卡片抖音号: {row['card_digits']}")
        print(f"    认证主体: {row['certification'] or '(卡片未显示认证)'}")
        print(f"    判定: {row.get('account_status')} / sample_role={row.get('sample_role')}")
        print(f"    sec_uid: {row['sec_uid'][:44]}...\n")
        results.append(row)
        time.sleep(random.uniform(6, 10))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 78)
    print(f"{'输入昵称':<20}{'匹配昵称':<18}{'认证主体':<34}{'判定'}")
    print("-" * 78)
    for r in results:
        print(f"{r['input_name'][:18]:<20}"
              f"{(r.get('nickname') or '-')[:16]:<18}"
              f"{(r.get('certification') or '-')[:32]:<34}"
              f"{r.get('account_status') or '✗未定位'}")
    print("=" * 78)
    print(f">> 结果已写入 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
