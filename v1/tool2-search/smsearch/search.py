# -*- coding: utf-8 -*-
"""搜索执行 (流式): 网页搜索 + 接口拦截 + 增量翻页 + 硬过滤 + 批量语义判定

流程: 连接常驻浏览器 → 打开搜索页 → 登录墙检查(等你明确告知放行) → 搜索框输入+回车
→ 拦截 search/item/ → (可选)筛选按点赞 → 滚动增量翻页, 每条先硬过滤, 攒批交 LLM 判定,
   命中达 limit 或 LLM 预算耗尽即提前终止。
原则: 浏览器常驻, 本模块任何路径都【不关闭浏览器】。
"""
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

from .browser import connect
from .filter import sort_hits_by_likes
from .llm import judge_batch

SEARCH_URL = "https://www.douyin.com/search/{kw}?type=video"
BASE = Path(__file__).resolve().parent.parent
CONTINUE_MARKER = BASE / ".continue.signal"   # 用户告知扫码成功后由外部创建, 脚本放行


def _login_modal_visible(page) -> bool:
    """元素级检测登录弹窗 (标题不可靠, 登录多为 modal)"""
    try:
        return page.evaluate("""() => {
            const texts = ['扫码登录', '二维码登录', '手机扫码'];
            for (const t of texts) {
                for (const el of document.querySelectorAll('div,span,li,button')) {
                    const it = (el.innerText || '').trim();
                    const r = el.getBoundingClientRect();
                    if (it && r.width && r.height && (it === t || it.includes(t))) return true;
                }
            }
            return false;
        }""")
    except Exception:
        return False


def _has_session(ctx) -> bool:
    try:
        names = {c["name"] for c in ctx.cookies()}
        return bool(names & {"sessionid", "sessionid_ss"})
    except Exception:
        return False


def _ensure_login(page, ctx, timeout_s: int = 1800) -> bool:
    """登录墙处理 (严格按用户要求):
    检测到登录弹窗(或 session 缺失) → 停下提示 → 浏览器保持开 →
    等"继续标记"(用户扫码后在聊天告知, 由外部创建标记文件) → 验证 sessionid → 继续。
    绝不自动继续, 绝不在此关闭浏览器。
    """
    warned = False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        modal = _login_modal_visible(page)
        has_session = _has_session(ctx)
        if has_session and not modal:
            if warned:
                print(">> 登录确认, 继续...")
            return True
        if not warned:
            print("=" * 50)
            print(">> 检测到登录页(或登录态缺失):")
            print(">> 1. 请在浏览器窗口用手机抖音App扫码登录")
            print(">> 2. 扫码完成后在聊天里告诉我'扫好了'")
            print(">> 我会放行继续 (浏览器保持打开, 不会关闭)")
            print("=" * 50)
            warned = True
        # 等外部"继续"标记 (用户告知后创建)
        if CONTINUE_MARKER.exists():
            CONTINUE_MARKER.unlink()
            print(">> 收到放行信号, 等待 sessionid 就位...")
            sdl = time.time() + 120
            while time.time() < sdl:
                if _has_session(ctx):
                    print(">> sessionid 已就位, 继续")
                    return True
                time.sleep(3)
            print(">> 标记已触发但 sessionid 未就位, 请确认扫码是否成功")
        time.sleep(5)
    print(">> 等待登录超时 (浏览器保持打开)")
    return _has_session(ctx)


def _apply_sort(page) -> bool:
    """hover 右上角'筛选' → 点'最多点赞' (用户人工观察: hover 即展开)
    返回排序是否切换成功。含诊断输出。"""
    try:
        # 1) 找右上角(最右)的"筛选"元素并用 locator.hover() 触发
        cands = page.get_by_text("筛选", exact=True).all()
        best = None
        for loc in cands:
            try:
                bb = loc.bounding_box()
                if bb and bb["width"] > 0 and bb["height"] > 0:
                    if best is None or bb["x"] > best["x"]:
                        best = loc
            except Exception:
                continue
        if best is None:
            print(">> 未找到可见'筛选'元素")
            return False
        best.hover(timeout=5000)
        time.sleep(2)
        # 2) 诊断: dump 展开后可见短文本
        texts = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span,li,button').forEach(el => {
                const t = (el.innerText || '').trim();
                const r = el.getBoundingClientRect();
                if (t && t.length < 20 && r.width && r.height) out.push(t);
            });
            return [...new Set(out)];
        }""")
        sort_cands = [t for t in texts if any(k in t for k in ("点赞", "最新", "综合", "排序"))]
        print(f">> hover后可见排序候选: {sort_cands}")
        # 3) 点"最多点赞"
        loc = page.get_by_text("最多点赞", exact=True).first
        if loc.count() > 0 and loc.is_visible():
            loc.click(timeout=4000)
            time.sleep(4)
            print(">> 已点击'最多点赞'")
            return True
        print(">> 未找到'最多点赞'选项")
        return False
    except Exception as e:
        print(f">> 排序操作异常: {str(e)[:100]}")
        return False


def _search_keyword(page, ctx, kw, sort, max_scrolls, process):
    """单关键词流式搜索。process(aw)->bool 返回 True 时提前停止翻页。
    返回 sort_applied(bool)。"""
    pending = []
    seen = set()
    sort_applied = False
    pre_sort_urls = []

    def on_request(req):
        if "/aweme/v1/web/search/item/" in req.url:
            if not sort_applied:
                pre_sort_urls.append(req.url)

    def on_response(resp):
        if "/aweme/v1/web/search/item/" in resp.url:
            try:
                body = resp.json()
                for item in body.get("data") or []:
                    aw = item.get("aweme") or item.get("aweme_info") or item
                    aid = aw.get("aweme_id")
                    if aid and aid not in seen:
                        seen.add(aid)
                        pending.append(aw)
            except Exception:
                pass

    page.on("request", on_request)
    page.on("response", on_response)
    print(f">> 打开搜索页: {kw}")
    page.goto(SEARCH_URL.format(kw=kw.replace(" ", "%20")),
              timeout=90000, wait_until="domcontentloaded")
    if not _ensure_login(page, ctx, timeout_s=600):
        print(">> 登录状态未就绪, 跳过该关键词")
        return False
    time.sleep(4)

    try:
        box = page.locator("input").first
        box.fill(kw)
        time.sleep(1)
        box.press("Enter")
    except Exception as e:
        print(f">> 搜索框输入失败: {str(e)[:80]}")
        return False
    time.sleep(6)

    if sort == "likes":
        sort_applied = _apply_sort(page)
        if not sort_applied:
            print(">> 排序未切换, 使用默认排序")

    def drain():
        while pending:
            aw = pending.pop(0)
            if process(aw):
                return True
        return False

    for i in range(max_scrolls):
        try:
            page.evaluate("""() => {
                const el = document.querySelector('.route-scroll-container')
                           || document.scrollingElement || document.body;
                el.scrollTop = el.scrollHeight;
            }""")
        except Exception:
            pass
        time.sleep(3 + random.uniform(0, 2))
        if drain():
            print(">> 已达目标, 提前停止翻页")
            break
    drain()
    print(f">> '{kw}' 共收集 {len(seen)} 条")
    return sort_applied


def _hard_status(aw, req) -> tuple:
    """逐条硬过滤判定, 返回 (通过?, matched_conditions, failed_conditions)。
    failed 用于向用户说明每条被淘汰的具体原因。
    【决策】keywords 只做搜索词, 不参与硬过滤; 硬过滤仅客观字段(作者/时间/互动)。"""
    f = req.get("filters") or {}
    author_ok = (not f.get("authors")) or any(
        a in ((aw.get("author") or {}).get("nickname") or "")
        for a in f["authors"])
    likes = (aw.get("statistics") or {}).get("digg_count") or 0
    likes_ok = (not f.get("min_likes")) or likes >= f["min_likes"]
    comments = (aw.get("statistics") or {}).get("comment_count") or 0
    comments_ok = (not f.get("min_comments")) or comments >= f["min_comments"]
    time_ok = True
    if f.get("after") or f.get("before"):
        from datetime import date, datetime
        ct = aw.get("create_time")
        if ct:
            d = datetime.fromtimestamp(int(ct)).date()
            if f.get("after") and d < date.fromisoformat(str(f["after"])):
                time_ok = False
            if f.get("before") and d > date.fromisoformat(str(f["before"])):
                time_ok = False
        else:
            time_ok = False

    matched, failed = [], []
    # 仅实际设置的过滤才计入判定 (与 hard_filter 一致)
    if f.get("authors"):
        (matched if author_ok else failed).append("authors")
    if f.get("min_likes"):
        (matched if likes_ok else failed).append("min_likes")
    if f.get("min_comments"):
        (matched if comments_ok else failed).append("min_comments")
    if f.get("after") or f.get("before"):
        (matched if time_ok else failed).append("time")
    return (not failed), matched, failed


class _Pipeline:
    """两段式过滤管线 (关键词模式/抖音号模式共用):
    - record: 全量收集记录 (含硬过滤判定, 供人工核对)
    - process: 单条处理 → 硬过滤 + 攒批语义判定
    - flush: 清空剩余批
    - stop_reason: 当前停止原因
    limit 语义: 由调用方在循环里判断; 本管线只累计 hits/uncertain/collected。
    """

    def __init__(self, req: dict, cfg: dict, llm_budget: int | None = None, source: str = ""):
        self.req = req
        self.cfg = cfg
        self.source = source          # 来源标签 (抖音号模式=当前抖音号; 关键词模式="")
        self.hits = []
        self.uncertain = []
        self.collected = []
        self.llm_calls = 0
        self._buffer = []
        self._budget = llm_budget or cfg["semantic"]["max_llm_calls"]
        self.stop_reason = ""

    def record(self, aw, hard_pass, matched, failed, semantic=None):
        st = aw.get("statistics") or {}
        au = aw.get("author") or {}
        self.collected.append({
            "aweme_id": aw.get("aweme_id"),
            "url": (aw.get("share_info") or {}).get("share_url"),
            "short_url": f"https://www.douyin.com/video/{aw.get('aweme_id')}",
            "author": au.get("nickname"),
            "author_uid": au.get("uid"),
            "source_douyin_id": self.source,
            "caption": (aw.get("desc") or "")[:200],
            "publish_time": datetime.fromtimestamp(int(aw["create_time"])).strftime("%Y-%m-%d")
            if aw.get("create_time") else None,
            "stats": {"likes": st.get("digg_count"), "comments": st.get("comment_count"),
                      "collects": st.get("collect_count"), "shares": st.get("share_count")},
            "hard_pass": hard_pass,
            "hard_matched": matched,
            "hard_failed": failed,
            "semantic": semantic,
        })

    def flush(self):
        if not self._buffer:
            return
        judgments = judge_batch(self.req["intents"],
                                [aw.get("desc", "") for aw, _m, _f in self._buffer],
                                self.cfg)
        self.llm_calls += 1
        for (aw, matched, failed), j in zip(self._buffer, judgments):
            if j == "符合":
                self.hits.append({"aweme": aw, "matched": matched, "semantic": j})
            elif j == "不确定":
                self.uncertain.append({"aweme": aw, "matched": matched, "semantic": j})
            # 回填到 collected (硬过滤已通过的那些条目)
            for rec in reversed(self.collected):
                if rec["aweme_id"] == aw.get("aweme_id") and rec["semantic"] is None:
                    rec["semantic"] = j
                    break
        self._buffer.clear()

    def process(self, aw) -> bool:
        """单条: 硬过滤→记录→攒批。返回 True 表示 LLM 预算耗尽(应停止)。"""
        ok, matched, failed = _hard_status(aw, self.req)
        self.record(aw, ok, matched, failed)
        if not ok:
            return False
        self._buffer.append((aw, matched, failed))
        if len(self._buffer) >= self.cfg["semantic"]["batch_size"]:
            self.flush()
        budget = self._budget
        if self.llm_calls >= budget:
            self.stop_reason = f"LLM 预算耗尽({budget}次)"
            return True
        return False


def run_search(req: dict, cfg: dict) -> dict:
    """关键词模式: 平台搜索 → 硬过滤 → 语义判定 → 输出候选。
    浏览器由 service 常驻管理, 本函数只连接不复用关闭。"""
    ctx, page = connect()
    pipe = _Pipeline(req, cfg)
    sort_applied_global = False

    for kw in req["keywords"]:
        if len(pipe.hits) >= req["limit"]:
            pipe.stop_reason = f"命中达 limit({req['limit']})"
            break
        sa = _search_keyword(page, ctx, kw, req["sort"],
                             cfg["search"]["max_scrolls"], pipe.process)
        sort_applied_global = sort_applied_global or sa
        pipe.flush()   # 关键词末尾清空残余批
        if len(pipe.hits) >= req["limit"] or pipe.llm_calls >= cfg["semantic"]["max_llm_calls"]:
            if not pipe.stop_reason:
                pipe.stop_reason = "LLM 预算耗尽"
            break
        time.sleep(random.uniform(*cfg["search"]["keyword_cooldown"]))
    pipe.flush()
    # 注意: 不关闭浏览器 — 常驻, 用 `smsearch browser stop` 显式关闭

    return {"hits": pipe.hits, "uncertain": pipe.uncertain,
            "llm_calls": pipe.llm_calls, "sort_applied": sort_applied_global,
            "collected": pipe.collected, "stop_reason": pipe.stop_reason}


# ==================== 抖音号模式 (douyin_id) ====================

USER_SEARCH_URL = "https://www.douyin.com/search/{did}?type=user"


def _card_nickname(text: str) -> str:
    """从搜索卡片文本里切出昵称。

    卡片形态: "<昵称>认证徽章<认证主体>…抖音号: <号>" (认证号)
              "<昵称>关注抖音号: <号>"                   (未认证号)
    """
    t = (text or "").strip()
    for sep in ("认证徽章", "关注", "抖音号"):
        idx = t.find(sep)
        if idx > 0:
            return t[:idx].strip()[:40]
    return t[:40]


def _card_certification(text: str) -> str:
    """从卡片文本切出认证主体: "认证徽章<主体>" (未认证卡片返回空串)"""
    m = re.search(r"认证徽章(.+?)(?=抖音号|关注|粉丝|获赞|作品|$)", text or "")
    return m.group(1).strip() if m else ""


def _extract_user_cards(page) -> list:
    """提取所有用户卡片: a[href*="/user/"], 卡片文本含"抖音号:"
    注意: 卡片文本中"抖音号"后的数字可能与获赞数粘连 ("55008743593388.3万"),
    因此先提取连续串, 再按 did 前缀匹配 (进主页后还有最终验证兜底)。
    抖音号形态: 数字/字母/下划线 (如 55008743593, YNHHFB, a1b2_c3)。
    nick 切片放宽到 200 字: 认证主体名较长, 30 字会把"认证徽章<主体>"截断。"""
    return page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a[href*="/user/"]')) {
            const t = (el.textContent || '').trim();
            const m = t.match(/抖音号[:：]\\s*([0-9A-Za-z_]+)/);
            if (!m) continue;
            const r = el.getBoundingClientRect();
            out.push({digits: m[1], href: el.getAttribute('href') || '',
                      nick: t.slice(0, 200), visible: r.width > 0 && r.height > 0});
        }
        return out;
    }""")


def _match_cards(cards, did: str) -> list:
    """在卡片中按抖音号匹配, 返回候选 [{sec_uid, nickname, certification, digits}]。
    匹配规则: exact 优先; startswith 无条件启用(处理获赞粘连, 如 55008743593388 / YNHHFB662)。
    误匹配风险由进主页后的 _verify_profile_did 校验兜底。"""
    up = did.upper()
    out, seen = [], set()
    for c in cards:
        digits_up = c["digits"].upper()
        exact = digits_up == up
        prefix = digits_up.startswith(up) and len(c["digits"]) > len(did)
        if exact or prefix:
            m = re.search(r"/user/([A-Za-z0-9_\-\.]+)", c["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                out.append({"sec_uid": m.group(1),
                            "nickname": _card_nickname(c.get("nick") or ""),
                            "certification": _card_certification(c.get("nick") or ""),
                            "digits": c["digits"]})
                print(f">> 候选抖音号 {c['digits']} ({'精确' if exact else '前缀'}) → {c['nick'][:20]}")
    return out


def _profile_identity(page) -> dict:
    """读主页头部身份: 昵称(h1) + 官方认证徽章(badge-role-name)

    实测主页存在两级权威信号:
      <h1> 云南省文化和旅游厅
      [data-e2e="badge-role-name"] 云南省文化和旅游厅官方抖音号
    """
    try:
        return page.evaluate("""() => {
            const pick = (s) => { const el = document.querySelector(s);
                                  return el ? (el.textContent || '').trim() : ''; };
            return { nickname: pick('h1'),
                     role: pick('[data-e2e="badge-role-name"]') };
        }""") or {"nickname": "", "role": ""}
    except Exception:
        return {"nickname": "", "role": ""}


PROFILE_WAIT_S = 25.0          # 主页头部渲染等待上限(实测常需数秒)


def _wait_profile_identity(page, timeout_s: float | None = None) -> dict:
    """轮询主页头部直到渲染 (昵称或认证徽章非空)。

    实测坑: goto 后固定 sleep(6) 时头部常尚未渲染 → 会被误判成"字段缺失"而放弃账号。
    """
    timeout_s = PROFILE_WAIT_S if timeout_s is None else timeout_s
    ident, deadline = {"nickname": "", "role": ""}, time.time() + timeout_s
    while time.time() < deadline:
        ident = _profile_identity(page)
        if ident.get("nickname") or ident.get("role"):
            return ident
        time.sleep(1.5)
    return ident


def _verify_profile_did(page, did: str, expect_nick: str | None = None,
                        expect_role: str | None = None,
                        wait_s: float | None = None) -> bool:
    """主页身份校验 (大小写不敏感), 三级证据 + 渲染等待。

    2026-09-11 修复: 主页 DOM **经常不渲染"抖音号:"字段**(实测 9 个号里 5 个),
    原实现直接判失败 → _find_user_by_did / _crawl_user_all 会静默跳过整个账号。
    现按证据强度递降, 且**不放宽到无条件通过**(避免采错账号):
      1) 主页"抖音号:"文本 == did                    → 通过(最可靠)
      2) 官方认证徽章 与 卡片认证主体 相符            → 通过(打警告)
      3) 主页昵称 与 卡片昵称 相符                    → 通过(打警告)
      4) 都不成立                                     → 不通过
    """
    try:
        txt = page.evaluate("() => document.body.textContent || ''")
        m = re.search(r"抖音号[:：]\s*([0-9A-Za-z_]+)", txt)
        if m:
            shown = m.group(1)
            if shown.upper() == did.upper():
                return True
            print(f">> 主页抖音号校验失败: 期望 {did}, 实际 {shown}")
            return False

        if not (expect_nick or expect_role):
            print(">> 抖音号字段未渲染, 且无兜底证据可用, 无法校验")
            return False

        ident = _wait_profile_identity(page, wait_s)
        role, nick = ident.get("role", ""), ident.get("nickname", "")
        if expect_role and role and (role == expect_role or role in expect_role
                                     or expect_role in role):
            print(f">> 抖音号字段未渲染; 官方认证徽章校验通过 (主页认证={role})")
            return True
        if expect_nick and nick and (nick == expect_nick or nick in expect_nick
                                     or expect_nick in nick):
            print(f">> 抖音号字段未渲染; 昵称兜底校验通过 (主页昵称={nick})")
            return True
        print(">> 抖音号字段未渲染, 且兜底证据不足, 不确认该账号: "
              f"主页昵称={nick or '(空)'} 主页认证={role or '(空)'} | "
              f"卡片昵称={expect_nick or '-'} 卡片认证={expect_role or '-'}")
        return False
    except Exception as e:
        print(f">> 主页校验异常: {str(e)[:80]}")
        return False


def _find_user_by_did(page, ctx, did: str, timeout_s: int = 120,
                      nick_out: dict | None = None) -> str | None:
    """定位抖音号用户, 返回 sec_uid。策略 (用户确认: 保守优先, 不行再直开):
    1) 回首页 → 搜索框输入抖音号 → 回车 → 点 tab「用户」→ 卡片匹配
    2) 若 0 候选/未匹配 (常见于被重定向到 jingxuan 精选版, 无用户 tab) → 直开标准搜索 URL ?type=user
    候选逐个进主页用 _verify_profile_did 验证, 通过才返回; 全部失败返回 None (不硬闯)。
    nick_out: 可选 dict, 命中时写入 {"nickname": 卡片昵称} —— 供 _crawl_user_all 复用作兜底校验。"""
    if not _ensure_login(page, ctx, timeout_s=timeout_s):
        return None

    def candidates_from_search():
        cards = _extract_user_cards(page)
        return _match_cards(cards, did)

    def try_conservative():
        # 回首页, 保证用全局搜索框 (当前页可能是用户主页, 其输入框是"搜索Ta的作品")
        try:
            page.goto("https://www.douyin.com/", timeout=60000, wait_until="domcontentloaded")
            time.sleep(4)
        except Exception as e:
            print(f">> 回首页失败: {str(e)[:80]}")
            return []
        try:
            box = page.locator("input").first
            box.fill(did)
            time.sleep(1)
            box.press("Enter")
        except Exception as e:
            print(f">> 搜索框输入失败: {str(e)[:80]}")
            return []
        time.sleep(6)
        # 点击 tab「用户」(jingxuan 精选版没有该 tab)
        clicked = False
        for sel in ['[data-e2e="user-tab"]', '[role="tab"]:has-text("用户")',
                    'span:has-text("用户")']:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            print(">> 未点击到'用户' tab, 尝试按当前页卡片匹配...")
        time.sleep(5)
        return candidates_from_search()

    cands = try_conservative()
    if not cands:
        # 兜底: 直开标准搜索 URL ?type=user (2026-08-27 实测: 直接出用户卡片, 无登录墙)
        print(">> 保守方式未定位到, 改用直开标准搜索 URL ...")
        try:
            page.goto(USER_SEARCH_URL.format(did=did), timeout=60000, wait_until="domcontentloaded")
            time.sleep(7)
        except Exception as e:
            print(f">> 直开搜索页失败: {str(e)[:80]}")
            return None
        cands = candidates_from_search()

    if not cands:
        print(f">> 未找到抖音号 == {did} 的用户 (搜索页无候选)")
        return None

    # 逐个进主页验证 (确保进对号; 误匹配会被主页身份校验拦截)
    for c in cands:
        sec, card_nick = c["sec_uid"], c.get("nickname") or ""
        card_role = c.get("certification") or ""
        print(f">> 验证候选主页: {sec[:30]}...")
        try:
            page.goto(f"https://www.douyin.com/user/{sec}?from_tab_name=main&showSubTab=video&showTab=post",
                      timeout=90000, wait_until="domcontentloaded")
            time.sleep(6)
        except Exception as e:
            print(f">> 候选主页加载失败: {str(e)[:80]}")
            continue
        if _verify_profile_did(page, did, expect_nick=card_nick, expect_role=card_role):
            print(f">> 主页校验通过, 采用 {did}")
            if nick_out is not None:
                nick_out["nickname"] = card_nick
                nick_out["certification"] = card_role
            return sec
    print(f">> 所有候选主页校验失败, 未确认 {did}")
    return None


def _crawl_user_all(page, ctx, sec_uid: str, pipe: _Pipeline, cfg: dict,
                    did: str | None = None, timeout_s: int = 3600,
                    expect_nick: str | None = None,
                    expect_role: str | None = None) -> tuple:
    """进入用户主页, 全量翻页收集作品 (无排序, while has_more; 页间隔 2-4s 随机, 偶尔更大)。
    返回 (collected_count, stop_reason)。浏览器不关闭。"""
    if not _ensure_login(page, ctx, timeout_s=timeout_s):
        return 0, "登录未就绪"
    seen = set()
    pending = []
    has_more = True
    stall = 0          # 连续滚动无新增计数
    got_response = False

    def on_response(resp):
        nonlocal has_more, got_response
        if "/aweme/v1/web/aweme/post/" in resp.url:
            got_response = True
            try:
                body = resp.json()
                has_more = bool(body.get("has_more"))
                for it in (body.get("aweme_list") or []):
                    aid = it.get("aweme_id")
                    if aid and aid not in seen:
                        seen.add(aid)
                        pending.append(it)
            except Exception:
                pass

    # 监听器必须先于 goto 挂载, 否则主页首屏响应会漏掉
    page.on("response", on_response)
    try:
        page.goto(f"https://www.douyin.com/user/{sec_uid}?from_tab_name=main&showSubTab=video&showTab=post",
                  timeout=90000, wait_until="domcontentloaded")
    except Exception as e:
        print(f">> 进入主页失败: {str(e)[:80]}")
        page.remove_listener("response", on_response)
        return 0, "主页加载失败"
    time.sleep(7)

    # 最终兜底: 主页身份校验 (确保进对号; 抖音号字段缺失时用认证徽章/昵称兜底)
    if did and not _verify_profile_did(page, did, expect_nick=expect_nick,
                                       expect_role=expect_role):
        page.remove_listener("response", on_response)
        return 0, f"主页身份校验失败(期望{did})"

    def scroll_down():
        try:
            page.evaluate("""() => {
                const el = document.querySelector('.route-scroll-container')
                           || document.scrollingElement || document.body;
                el.scrollTop = el.scrollHeight;
            }""")
        except Exception:
            pass

    def drain():
        """处理所有已收集条目; 返回 True=应停止(LLM预算耗尽)"""
        while pending:
            aw = pending.pop(0)
            if pipe.process(aw):
                return True
        return False

    while True:
        if drain():
            pipe.stop_reason = "LLM 预算耗尽"
            break
        if not has_more:
            break
        scroll_down()
        wait = random.uniform(2.0, 4.0)
        if random.random() < 0.10:
            wait = random.uniform(6.0, 10.0)   # 偶尔更慢, 躲避风控
        time.sleep(wait)
        if not pending:
            stall += 1
            if stall >= 5:
                print(">> 连续无新增, 视为已到底")
                break
        else:
            stall = 0
    drain()   # 兜底: 处理最后一次响应残留的条目
    pipe.flush()
    page.remove_listener("response", on_response)
    reason = pipe.stop_reason or ("has_more=False" if not has_more else "到底(兜底)")
    return len(seen), reason


def run_douyin_ids(req: dict, cfg: dict, checkpoint_path=None) -> dict:
    """抖音号模式: 每个抖音号 → 搜索定位(按抖音号精确匹配) → 进主页全量翻页 → 两段式过滤。
    多条抖音号串行处理。
    limit 语义: **每个抖音号各自**的截断 — 每号内部按赞降序取前 limit 条, 合并输出。
    跨号按 aweme_id 去重。浏览器由 service 常驻管理, 不关闭。

    checkpoint_path: 可选。每完成一个号就落盘一次 → 中途崩溃最多丢一个号
        (2026-09-13 教训: 末段序列化崩溃导致 3.5 小时爬取结果全丢)。
    连续 ZERO_STREAK_ABORT 个号收集 0 条 → 判定限流, 提前中止本段(不做无效耗时)。
    """
    ctx, page = connect()
    budget = cfg["semantic"].get("max_llm_calls_did", cfg["semantic"]["max_llm_calls"] * 20)

    per_account = []        # 每号统计与输出
    all_hits = []           # 合并命中(每号截断后)
    all_uncertain = []
    all_collected = []
    seen_ids = set()        # 跨号去重
    llm_calls_total = 0
    total_seen = 0
    reasons = []
    t_start = time.time()
    zero_streak = 0

    def _checkpoint():
        """每完成一个号落盘一次; 失败不影响主流程"""
        if checkpoint_path is None:
            return
        try:
            Path(checkpoint_path).write_text(json.dumps({
                "partial": True, "performed_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "per_account": per_account, "hits": all_hits,
                "uncertain": all_uncertain, "collected": all_collected,
                "stop_reason": "; ".join(reasons),
            }, ensure_ascii=False, default=str), encoding="utf-8")
            print(f">> checkpoint 已落盘 ({len(per_account)} 个号)")
        except Exception as e:
            print(f">> checkpoint 写入失败(不影响主流程): {str(e)[:80]}")

    for did in req["douyin_ids"]:
        print(f"===== 处理抖音号: {did} =====")
        t0 = time.time()
        pipe = _Pipeline(req, cfg, llm_budget=budget, source=did)
        match_info = {}
        sec_uid = _find_user_by_did(page, ctx, did, nick_out=match_info)
        if not sec_uid:
            reasons.append(f"{did}: 未定位到用户")
            print(f">> 跳过 {did} (未找到精确匹配的抖音号)")
            time.sleep(random.uniform(*cfg["search"]["keyword_cooldown"]))
            continue
        n, reason = _crawl_user_all(page, ctx, sec_uid, pipe, cfg, did=did,
                                    expect_nick=match_info.get("nickname"),
                                    expect_role=match_info.get("certification"))
        pipe.flush()
        # 该号内部: 按赞降序取前 limit 条
        account_hits = sort_hits_by_likes(pipe.hits)[:req["limit"]]
        for h in account_hits:
            aid = h["aweme"].get("aweme_id")
            if aid and aid in seen_ids:
                continue
            if aid:
                seen_ids.add(aid)
            all_hits.append(h)
        secs = round(time.time() - t0, 1)
        per_account.append({
            "douyin_id": did,
            "collected": n,
            "hits_total": len(pipe.hits),          # 该号全部符合
            "hits_output": len(account_hits),      # 该号截断后输出
            "llm_calls": pipe.llm_calls,
            "reason": reason,
            "seconds": secs,
        })
        all_uncertain.extend(pipe.uncertain)
        all_collected.extend(pipe.collected)
        llm_calls_total += pipe.llm_calls
        total_seen += n
        reasons.append(f"{did}: 收集 {n} 条, 符合 {len(pipe.hits)}, 输出 {len(account_hits)} ({reason}, {secs}s)")
        print(f">> {did} 完成: 收集 {n} | 符合 {len(pipe.hits)} | 输出 {len(account_hits)} | {secs}s")
        _checkpoint()

        # 限流识别: 连续多个号一条都收不到 → 提前中止(避免整段空跑)
        if n == 0:
            zero_streak += 1
            if zero_streak >= 3:
                msg = (f"提前中止: 连续 {zero_streak} 个号收集 0 条 → 疑似限流/软风控; "
                       "建议冷却数十分钟后重跑本段")
                print(f">> !! {msg}")
                reasons.append(msg)
                break
        else:
            zero_streak = 0
        time.sleep(random.uniform(*cfg["search"]["keyword_cooldown"]))

    total_secs = round(time.time() - t_start, 1)
    return {"hits": all_hits, "hits_per_account": per_account,
            "uncertain": all_uncertain, "collected": all_collected,
            "llm_calls": llm_calls_total, "sort_applied": False,
            "stop_reason": "; ".join(reasons), "total_seen": total_seen,
            "mode": "douyin_id", "seconds": total_secs}
