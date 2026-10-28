# -*- coding: utf-8 -*-
"""统计引擎: 纯计算指标(零模型, 可复现)

指标定义见 metrics.yaml; 本模块只做计算, 不做判定/报告。
所有长尾指标(速度/时间间隔)输出分位 p25/p50/p75/p90, 不给均值(见 DESIGN §2 教训2)。
"""
import json
import math
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from .holiday import info as holiday_info

# 繁→简转换 (ASR 偶尔输出繁体字, 词表是简体) — zhconv 为纯 Python 依赖
try:
    from zhconv import convert as _zh_convert
except Exception:                                    # 未安装时降级为不转换
    _zh_convert = None

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]")
QUESTION_RE = re.compile(r"[?？]")
# SRT 时间戳标记: "[0000.00 -> 0001.60] " (video.json 的 full_text 里混有该标记)
SRT_MARK_RE = re.compile(r"\[\s*\d+(?:[:.]\d+)*\s*->\s*\d+(?:[:.]\d+)*\s*\]\s*")

# ---------- Text Liveness 词表 (口径可审, 见 lexicon.yaml) ----------
LEXICON_FILE = Path(__file__).resolve().parent / "lexicon.yaml"
# 6 个维度 → idea.md: HCI1人格化/HCI2口语化/情绪/网络语言/HCI3玩梗/反问
TL_DIMS = ("first_person", "colloquial", "emotion", "slang", "meme", "rhetorical")


def load_lexicon(path: Path | str | None = None) -> dict:
    """加载 Text Liveness 词表; 缺失/损坏时返回空 dict(指标退化为全 0, 不报错)"""
    import yaml
    p = Path(path) if path else LEXICON_FILE
    if not p.exists():
        return {}
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return raw.get("dimensions") or {}


LEXICON = load_lexicon()


def count_hits(text: str, words: list) -> tuple:
    """长词优先、非重叠计数 → (命中次数, 命中词列表)

    先匹配长词并替换为占位符, 避免"我们"被"我"重复计数。
    占位符等长(\\x00), 不影响按原始字数的归一化。
    """
    if not text or not words:
        return 0, []
    hits, matched, t = 0, [], text
    for w in sorted((str(w) for w in words if str(w)), key=len, reverse=True):
        c = t.count(w)
        if c:
            hits += c
            matched.append(w)
            t = t.replace(w, "\x00" * len(w))
    return hits, matched


def text_liveness(text: str, lexicon: dict | None = None) -> dict:
    """单段文本的 6 维活人感词命中次数(纯字符串, 零模型, 可复现)"""
    lex = lexicon if lexicon is not None else LEXICON
    out = {}
    for dim in TL_DIMS:
        spec = lex.get(dim) or {}
        hits, _ = count_hits(text or "", spec.get("words") or [])
        if spec.get("emoji"):
            hits += len(EMOJI_RE.findall(text or ""))
        for pat in (spec.get("patterns") or []):
            try:
                hits += len(re.findall(pat, text or ""))
            except re.error:
                continue
        out[dim] = hits
    return out


def tl_index(hits: dict) -> float:
    """等权活人感指数 = 6 维"是否出现"的均值 (0~1)

    稳健性检验要求"等权/PCA/因子"多种构造 → 本指标只给最朴素的等权版;
    原始 6 维命中次数已单独输出, PCA/因子由研究端自行计算。
    """
    if not hits:
        return 0.0
    return round(sum(1 for v in hits.values() if v) / len(TL_DIMS), 4)


# ---------- 工具函数 (纯逻辑, 可单测) ----------
def parse_dt(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None


def percentile(sorted_vals: list, q: float):
    """线性插值百分位; 输入须升序。空返回 None。"""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(float(sorted_vals[0]), 1)
    pos = (len(sorted_vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return round(float(sorted_vals[lo]), 1)
    frac = pos - lo
    return round(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac, 1)


def entropy(items: list):
    """香农熵 (地区多样性); 空返回 None"""
    if not items:
        return None
    c = Counter(items)
    n = len(items)
    return round(-sum((v / n) * math.log(v / n) for v in c.values()), 3)


def flatten(text: str, limit: int = 120) -> str:
    """压平空白, 便于 CSV 单行显示"""
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


def strip_srt_markup(text: str) -> str:
    """去掉 SRT 时间戳标记, 只留口播文本"""
    return SRT_MARK_RE.sub("", text or "").strip()


def to_simplified(text: str) -> str:
    """繁体 → 简体 (词表是简体; ASR 偶尔输出繁体字, 不转换会漏命中)

    zhconv 未安装时原样返回(不报错), 由 subtitle_text_source / 报告说明。
    """
    if not text or _zh_convert is None:
        return text or ""
    return _zh_convert(text, "zh-cn")


def subtitle_text(video_dir: Path, rec: dict, prefer: str = "llm") -> tuple:
    """取**纯口播文本** → (text, source)

    两个已知坑:
      1. video.json 的 subtitles.full_text 含 "[0000.00 -> 0001.60] " 时间戳标记
         → 不用于字数统计/文本分析; 优先读 segments 文件
      2. prefer="llm" 时优先 LLM 修正版 subtitles.llm.json (专名/错字修正),
         缺失则回退原始 ASR subtitles.json, 再回退 full_text(剥离标记)
    """
    sub = rec.get("subtitles") or {}
    names = [("subtitles.llm.json", "llm_corrected"),
             ("subtitles.json", "segments_raw")]
    if prefer != "llm":
        names = [n for n in names if n[1] == "segments_raw"]
    for name, source in names:
        try:
            data = json.loads((Path(video_dir) / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            txt = " ".join(str(x.get("text") or "") for x in data if isinstance(x, dict)).strip()
            if txt:
                return txt, source
    ft = sub.get("full_text") or ""
    return strip_srt_markup(ft), "full_text_fallback" if ft else "none"


# ---------- 目标账号判定 (口径见 accounts.yaml) ----------
ACCOUNTS_FILE = Path(__file__).resolve().parent.parent / "accounts.yaml"
TARGET, BORDERLINE, NON_TARGET, UNKNOWN = "target", "borderline", "non_target", "unknown"


def load_accounts(path: Path | str | None = None) -> dict:
    """加载目标账号白名单; 缺失/损坏时返回空 dict(全部判 unknown)"""
    import yaml
    p = Path(path) if path else ACCOUNTS_FILE
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


ACCOUNTS = load_accounts()


def sample_role(status: str, accounts: dict | None = None) -> str:
    """账号判定 → 样本分层 (口径见 accounts.yaml 的 sample_policy)

    main=主样本 / robustness=稳健性对照 / excluded=排除 / undetermined=待人工
    """
    cfg = accounts if accounts is not None else ACCOUNTS
    pol = cfg.get("sample_policy") or {}
    if not pol:
        pol = {"main": [TARGET], "robustness": [BORDERLINE],
               "excluded": [NON_TARGET], "undetermined": [UNKNOWN]}
    for role, statuses in (("main", pol.get("main")), ("robustness", pol.get("robustness")),
                           ("excluded", pol.get("excluded"))):
        if status in (statuses or []):
            return role
    return "undetermined"


def account_status(au: dict, accounts: dict | None = None) -> dict:
    """判定该视频作者是否属于研究总体 → 账号维度字段

    优先级: manual_overrides > 白名单 > 认证关键词规则 > unknown(不猜)
    """
    cfg = accounts if accounts is not None else ACCOUNTS
    uid = str(au.get("id") or "")
    out = {"account_uid": uid or None, "account_status": UNKNOWN,
           "is_target_account": None, "account_admin_type": None,
           "account_level": None, "account_province": None, "account_region": None,
           "sample_role": None, "account_match": None}
    if not uid and not str(au.get("nickname") or "").strip():
        out["sample_role"] = sample_role(UNKNOWN, cfg)
        return out

    def finish(match: str):
        st = out["account_status"]
        out["account_match"] = match
        # unknown 时不下"不是目标账号"的断言 → None(交人工), 但 sample_role 仍为 undetermined
        out["is_target_account"] = True if st == TARGET else (None if st == UNKNOWN else False)
        out["sample_role"] = sample_role(st, cfg)
        return out

    if uid:
        over = (cfg.get("manual_overrides") or {}).get(uid)
        if over:
            out["account_status"] = over.get("status") or NON_TARGET
            out["account_admin_type"] = over.get("admin_type")
            return finish("manual_uid")

        for a in cfg.get("accounts") or []:
            if str(a.get("uid") or "") == uid:
                out.update({
                    "account_status": a.get("status") or UNKNOWN,
                    "account_admin_type": a.get("admin_type"),
                    "account_level": a.get("level"),
                    "account_province": a.get("province"),
                    "account_region": a.get("region"),
                })
                return finish("uid")

    # 昵称兜底(预登记阶段 uid 未知时用; 弱于 uid → 仅在 uid 未命中时尝试)
    nick = str(au.get("nickname") or "").strip()
    if nick:
        for a in cfg.get("accounts") or []:
            if str(a.get("nickname") or "").strip() == nick:
                out.update({
                    "account_status": a.get("status") or UNKNOWN,
                    "account_admin_type": a.get("admin_type"),
                    "account_level": a.get("level"),
                    "account_province": a.get("province"),
                    "account_region": a.get("region"),
                })
                return finish("nickname")

    cert = str(au.get("certification") or "")
    rule = cfg.get("rule") or {}
    for kw in rule.get("target_cert_keywords") or []:
        if kw in cert:
            out.update({"account_status": TARGET, "account_admin_type": kw})
            return finish("cert_keyword")
    for kw in rule.get("borderline_cert_keywords") or []:
        if kw in cert:
            out.update({"account_status": BORDERLINE, "account_admin_type": kw})
            return finish("cert_keyword")
    # 认证为空且无记录 → unknown(不猜, 交人工)
    if not cert:
        out["account_status"] = UNKNOWN
        return finish("none")
    out.update({"account_status": NON_TARGET})
    return finish("cert_other")


# ---------- 视频层 ----------
def video_metrics(video_dir: Path) -> dict:
    """计算单视频的全部视频层统计指标"""
    rec = json.loads((video_dir / "video.json").read_text(encoding="utf-8"))
    comments = json.loads((video_dir / "comments.json").read_text(encoding="utf-8"))
    au = rec.get("author") or {}
    st = rec.get("stats") or {}
    cm = rec.get("comments") or {}
    sub = rec.get("subtitles") or {}
    pub = parse_dt(rec.get("publish_time"))

    top = [c for c in comments if not c.get("parent_id")]
    author_replies = [c for c in comments if c.get("is_author")]

    # 官方回复率
    replied_top = [c for c in top if c.get("author_replied")]
    reply_rate = round(len(replied_top) / len(top), 4) if top else None

    # 回复速度分位(分钟)
    by_id = {c["comment_id"]: c for c in comments}
    deltas = []
    for ar in author_replies:
        p = by_id.get(ar.get("parent_id"))
        if not p:
            continue
        t1, t0 = parse_dt(ar.get("created_at")), parse_dt(p.get("created_at"))
        if t1 and t0:
            sec = (t1 - t0).total_seconds()
            if 0 <= sec <= 86400 * 7:
                deltas.append(sec / 60)
    deltas.sort()

    rtexts = [c.get("text") or "" for c in author_replies]
    rlens = [len(t) for t in rtexts]
    texts = [c.get("text") or "" for c in comments]
    tlens = [len(t) for t in texts]
    top_texts = [c.get("text") or "" for c in top]

    # 24h 评论占比
    within24 = None
    if pub:
        hrs = []
        for c in comments:
            t = parse_dt(c.get("created_at"))
            if t:
                h = (t - pub).total_seconds() / 3600
                if h >= 0:
                    hrs.append(h)
        if hrs:
            within24 = round(sum(1 for h in hrs if h <= 24) / len(hrs), 4)

    caption = rec.get("caption") or ""
    ip_top = Counter(c.get("ip_label") for c in top if c.get("ip_label")).most_common(1)

    # --- 目标账号判定 (口径见 accounts.yaml) ---
    acct = account_status(au)

    # --- 节假日 (国务院口径; 未收录年份 → None) ---
    hol = holiday_info(pub.date()) if pub else {
        "is_holiday": None, "holiday_name": None, "is_weekend": None,
        "is_makeup_workday": None, "is_rest_day": None,
    }

    # --- 视觉派生 (工具1 visual.json; 缺失 → 全 None) ---
    vis = {"visual_present_ratio": None, "face_count_avg": None, "face_count_max": None,
           "selfie_score": None, "shake_index": None, "camera_motion": None,
           "video_resolution": None}
    vpath = video_dir / "visual.json"
    if vpath.exists():
        try:
            vd = json.loads(vpath.read_text(encoding="utf-8"))
            vm = vd.get("metrics") or {}
            vis.update({
                "visual_present_ratio": vm.get("person_presence_ratio"),
                "face_count_avg": vm.get("face_count_avg"),
                "face_count_max": vm.get("face_count_max"),
                "selfie_score": vm.get("selfie_score"),
                "shake_index": vm.get("shake_index"),
                "camera_motion": vm.get("dominant"),
                "video_resolution": (vd.get("video_meta") or {}).get("resolution"),
            })
        except Exception:
            pass

    # --- Text Liveness: 双通道 (仅文案 / 文案+字幕) ---
    # 字幕用 LLM 修正版纯文本(prefer="llm"), 并做繁→简归一化后再匹配词表
    sub_text, sub_text_src = subtitle_text(video_dir, rec)
    cap_norm = to_simplified(caption)
    sub_norm = to_simplified(sub_text)
    tl_cap = text_liveness(cap_norm)
    tl_all = text_liveness((cap_norm + "\n" + sub_norm).strip())

    return {
        "video_id": rec.get("platform_item_id") or video_dir.name,
        "author": au.get("nickname"),
        # 账号维度 (研究总体过滤用; 口径见 accounts.yaml)
        **acct,
        # 基础
        "duration_sec": (rec.get("media") or {}).get("duration_seconds"),
        "publish_date": pub.strftime("%Y-%m-%d") if pub else None,
        "publish_weekday": "周" + "一二三四五六日"[pub.weekday()] if pub else None,
        "publish_hour": pub.hour if pub else None,
        # 节假日 (控制变量)
        **hol,
        # 互动
        "likes": st.get("likes"), "comments_n": st.get("comments"),
        "collects": st.get("collects"), "shares": st.get("shares"),
        "recommends": st.get("recommends"),
        "engage_ratio": round((st.get("comments") or 0) / st.get("likes"), 4)
        if st.get("likes") else None,
        # 文案
        "caption_len": len(caption),
        "hashtag_count": len(rec.get("hashtags") or []),
        "mention_count": caption.count("@"),
        "caption_emoji": len(EMOJI_RE.findall(caption)),
        "caption_question": len(QUESTION_RE.findall(caption)),
        # 账号
        "followers": au.get("follower_count"),
        "total_favorited": au.get("total_favorited"),
        "is_verified": bool(au.get("certification")),
        "signature_len": len(au.get("signature") or ""),
        # 评论覆盖
        "comments_collected": cm.get("collected_count"),
        "comments_platform_total": cm.get("platform_total"),
        "comment_coverage": cm.get("top_level_coverage"),
        # 官方互动
        "author_reply_n": len(author_replies),
        "reply_rate": reply_rate,
        "reply_speed_p25_min": percentile(deltas, 0.25),
        "reply_speed_p50_min": percentile(deltas, 0.50),
        "reply_speed_p75_min": percentile(deltas, 0.75),
        "reply_speed_p90_min": percentile(deltas, 0.90),
        "reply_text_len_avg": round(statistics.mean(rlens), 1) if rlens else None,
        "reply_emoji_rate": round(sum(1 for t in rtexts if EMOJI_RE.search(t)) / len(rtexts), 4)
        if rtexts else None,
        "reply_at_rate": round(sum(1 for t in rtexts if "@" in t) / len(rtexts), 4)
        if rtexts else None,
        "author_engaged_comments": (rec.get("author_engagement") or {}).get("replied_comment_count"),
        # 评论群体
        "comment_len_avg": round(statistics.mean(tlens), 1) if tlens else None,
        "comment_len_median": round(statistics.median(tlens), 1) if tlens else None,
        "comment_emoji_rate": round(sum(1 for t in texts if EMOJI_RE.search(t)) / len(texts), 4)
        if texts else None,
        "comment_question_rate": round(sum(1 for t in top_texts if QUESTION_RE.search(t)) / len(top_texts), 4)
        if top_texts else None,
        "top_reply_ratio": round(len(top) / len(comments), 4) if comments else None,
        "hot_comment_ratio": round(sum(1 for c in comments if c.get("is_hot")) / len(comments), 4)
        if comments else None,
        "ip_region_entropy": entropy([c.get("ip_label") for c in top if c.get("ip_label")]),
        "ip_top_region": ip_top[0][0] if ip_top else None,
        "comment_velocity_24h": within24,
        # 字幕 (subtitle_len = 纯口播字数, 已剥离 SRT 时间戳标记)
        "subtitle_len": len(sub_text),
        "subtitle_segments": sub.get("segments_count"),
        "subtitle_source": sub.get("source"),
        "subtitle_text_source": sub_text_src,
        # 视觉派生 (Visual Liveness)
        **vis,
        # Text Liveness · 仅文案通道
        **{f"tl_cap_{k}": v for k, v in tl_cap.items()},
        "tl_index_cap": tl_index(tl_cap),
        # Text Liveness · 文案+字幕通道
        **{f"tl_all_{k}": v for k, v in tl_all.items()},
        "tl_index_all": tl_index(tl_all),
    }


# ---------- 评论层 ----------
def comment_metrics(video_dir: Path, text_limit: int = 120) -> list[dict]:
    """计算单视频的全部评论层指标(每评论一行)"""
    rec = json.loads((video_dir / "video.json").read_text(encoding="utf-8"))
    pub = parse_dt(rec.get("publish_time"))
    vid = rec.get("platform_item_id") or video_dir.name
    comments = json.loads((video_dir / "comments.json").read_text(encoding="utf-8"))

    rows = []
    for c in comments:
        t = parse_dt(c.get("created_at"))
        raw = c.get("text") or ""
        rows.append({
            "video_id": vid,
            "comment_id": c.get("comment_id"),
            "level": "顶层" if not c.get("parent_id") else "回复",
            "parent_id": c.get("parent_id"),
            "is_author_reply": bool(c.get("is_author")),
            "author_replied": bool(c.get("author_replied")),
            "text": flatten(raw, text_limit),
            "char_len": len(raw),
            "has_emoji": bool(EMOJI_RE.search(raw)),
            "has_at": "@" in raw,
            "is_question": bool(QUESTION_RE.search(raw)),
            "likes": c.get("likes"),
            "reply_count": c.get("reply_count"),
            "is_hot": bool(c.get("is_hot")),
            "ip_label": c.get("ip_label"),
            "hours_since_publish": round((t - pub).total_seconds() / 3600, 1) if (t and pub) else None,
        })
    return rows


def list_video_ids(data_dir: Path) -> list:
    """列出数据目录下所有视频 ID(有 video.json 的)"""
    if not data_dir.exists():
        return []
    return sorted(p.name for p in data_dir.iterdir()
                  if p.is_dir() and (p / "video.json").exists())


# ---------- 因变量派生 (ETI, 依赖 LLM 标注结果) ----------
def derive_eti(rows_comment: list, level_map: dict) -> dict:
    """按视频聚合意愿分级 → {video_id: {eti_n, etir, strong_etir, eti_mean}}

    level_map: {comment_id: "0".."4"} (来自 labels_willingness_level.csv)
    口径(与 idea.md 稳健性"替换因变量"对应):
      etir       意愿分级 ≥1 的评论占比(有表达意愿)
      strong_etir 意愿分级 ≥3 的评论占比(行动/计划性意愿)
      eti_mean   意愿分级均值(0~4)
    注意: 分母只含"成功标注"的评论; 未采到的评论不在分母内(覆盖率见 comment_coverage)。
    """
    from collections import defaultdict
    acc = defaultdict(list)
    for r in rows_comment:
        raw = level_map.get(str(r.get("comment_id")))
        if raw is None or raw == "":
            continue
        try:
            lv = int(float(raw))
        except (TypeError, ValueError):
            continue
        acc[r.get("video_id")].append(lv)
    out = {}
    for vid, lvls in acc.items():
        n = len(lvls)
        if not n:
            continue
        out[vid] = {
            "eti_n": n,
            "etir": round(sum(1 for x in lvls if x >= 1) / n, 4),
            "strong_etir": round(sum(1 for x in lvls if x >= 3) / n, 4),
            "eti_mean": round(sum(lvls) / n, 4),
        }
    return out
