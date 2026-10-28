# -*- coding: utf-8 -*-
"""工具3 v0.2 新增能力单测: 节假日日历 / Text Liveness 词表 / ETI 派生 / 多字段输入

(纯逻辑, 无网络; 数据来源见 smanalyze/holiday.py 顶部注释)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smanalyze import holiday
from smanalyze import stats
from smanalyze.cli import _field_value
from smanalyze.registry import Registry


# ---------- 节假日日历 (国务院口径) ----------
def test_holiday_official_dates():
    assert holiday.is_holiday(date(2024, 10, 1)) is True          # 国庆
    assert holiday.holiday_name(date(2024, 10, 1)) == "国庆节"
    assert holiday.is_holiday(date(2025, 10, 8)) is True          # 2025 国庆+中秋 8 天
    assert holiday.holiday_name(date(2025, 10, 8)) == "国庆节中秋节"
    assert holiday.is_holiday(date(2026, 2, 23)) is True          # 2026 春节最后一天
    assert holiday.is_holiday(date(2026, 2, 24)) is False         # 次日已上班


def test_holiday_makeup_workdays():
    # 2025-01-26(周日)、2025-02-08(周六) 调休上班
    assert holiday.is_weekend(date(2025, 1, 26)) is True
    assert holiday.is_makeup_workday(date(2025, 1, 26)) is True
    assert holiday.is_rest_day(date(2025, 1, 26)) is False
    assert holiday.is_makeup_workday(date(2026, 2, 14)) is True


def test_holiday_rest_day():
    assert holiday.is_rest_day(date(2025, 3, 1)) is True          # 普通周六
    assert holiday.is_rest_day(date(2025, 3, 3)) is False         # 普通周一
    assert holiday.is_rest_day(date(2025, 10, 2)) is True         # 法定假日(周四)


def test_holiday_unsupported_year_returns_none():
    """未收录年份必须返回 None(不猜)"""
    assert holiday.is_holiday(date(2019, 10, 1)) is None
    assert holiday.is_rest_day(date(2030, 1, 1)) is None
    assert holiday.is_makeup_workday(date(2019, 10, 1)) is None
    assert holiday.is_weekend(date(2019, 10, 5)) is True           # 星期判断与年份无关


def test_holiday_info_shape():
    info = holiday.info(date(2025, 5, 1))
    assert set(info) == {"is_holiday", "holiday_name", "is_weekend",
                         "is_makeup_workday", "is_rest_day"}
    assert info["is_holiday"] is True and info["holiday_name"] == "劳动节"


# ---------- Text Liveness 词表命中 ----------
def test_count_hits_longest_first_no_double_count():
    """'我们' 不应被 '我' 重复计数"""
    hits, matched = stats.count_hits("我们一起去", ["我", "我们"])
    assert hits == 1 and matched == ["我们"]


def test_count_hits_multiple():
    hits, _ = stats.count_hits("我们真的真的来了", ["我们", "真的"])
    assert hits == 3                       # 我们×1 + 真的×2


def test_count_hits_empty():
    assert stats.count_hits("", ["我"]) == (0, [])
    assert stats.count_hits("无命中", []) == (0, [])


def test_text_liveness_dims_and_index():
    lex = stats.load_lexicon()
    assert set(stats.TL_DIMS).issubset(lex.keys())        # 词表齐全
    out = stats.text_liveness("咱们红河真的太绝了哈哈哈", lex)
    assert out["first_person"] >= 1
    assert out["colloquial"] >= 1
    assert out["emotion"] >= 1
    assert stats.tl_index(out) > 0


def test_text_liveness_rhetorical_regex():
    out = stats.text_liveness("难道不值得来一次吗", stats.load_lexicon())
    assert out["rhetorical"] >= 1


def test_text_liveness_emotion_counts_emoji():
    out = stats.text_liveness("红河欢迎你😍", stats.load_lexicon())
    assert out["emotion"] >= 1


def test_tl_index_bounds():
    assert stats.tl_index({}) == 0.0
    assert stats.tl_index({d: 0 for d in stats.TL_DIMS}) == 0.0
    assert stats.tl_index({d: 1 for d in stats.TL_DIMS}) == 1.0


def test_lexicon_has_six_dimensions():
    lex = stats.load_lexicon()
    for dim in stats.TL_DIMS:
        spec = lex.get(dim) or {}
        assert spec.get("words") or spec.get("patterns"), f"{dim} 词表为空"


# ---------- 因变量派生 ----------
def test_derive_eti():
    rows = [
        {"video_id": "v1", "comment_id": "c1"},
        {"video_id": "v1", "comment_id": "c2"},
        {"video_id": "v1", "comment_id": "c3"},
        {"video_id": "v1", "comment_id": "c4"},
        {"video_id": "v2", "comment_id": "c5"},
    ]
    level_map = {"c1": "0", "c2": "1", "c3": "3", "c4": "4", "c5": "0"}
    out = stats.derive_eti(rows, level_map)
    assert out["v1"]["eti_n"] == 4
    assert out["v1"]["etir"] == 0.75               # 1,3,4 → 3/4
    assert out["v1"]["strong_etir"] == 0.5         # 3,4 → 2/4
    assert out["v1"]["eti_mean"] == 2.0            # (0+1+3+4)/4
    assert out["v2"]["etir"] == 0.0


def test_derive_eti_skips_missing_and_bad_labels():
    rows = [{"video_id": "v1", "comment_id": "c1"},
            {"video_id": "v1", "comment_id": "c2"}]
    out = stats.derive_eti(rows, {"c1": "abc"})    # c2 未标注, c1 非法
    assert out == {}


# ---------- 视频层多字段输入 (Text Liveness 需要 文案+字幕) ----------
def test_field_value_single():
    assert _field_value({"caption": "你好"}, "caption") == "你好"


def test_field_value_dotted_and_multi():
    rec = {"caption": "文案", "subtitles": {"full_text": "口播"}}
    got = _field_value(rec, ["caption", "subtitles.full_text"])
    assert got == "文案\n口播"


def test_field_value_missing_field_ignored():
    rec = {"caption": "文案"}
    assert _field_value(rec, ["caption", "subtitles.full_text"]) == "文案"


def test_field_value_list_field_joined():
    rec = {"hashtags": ["红河", "旅游"]}
    assert _field_value(rec, "hashtags") == "红河 旅游"


# ---------- 字幕纯文本 (剥离 SRT 时间戳标记) ----------
def test_strip_srt_markup():
    raw = "[0000.00 -> 0001.60] 每天在公司地库\n[0001.60 -> 0003.48] 床车午睡有多爽"
    assert stats.strip_srt_markup(raw) == "每天在公司地库\n床车午睡有多爽"


def test_subtitle_text_prefers_segments(tmp_path):
    (tmp_path / "subtitles.json").write_text(
        json.dumps([{"index": 1, "start": 0.0, "end": 1.6, "text": "纯口播一"},
                    {"index": 2, "start": 1.6, "end": 3.4, "text": "纯口播二"}],
                   ensure_ascii=False), encoding="utf-8")
    rec = {"subtitles": {"full_text": "[0000.00 -> 0001.60] 带时间戳的"}}
    txt, src = stats.subtitle_text(tmp_path, rec)
    assert txt == "纯口播一 纯口播二"
    assert src == "segments_raw"


def test_subtitle_text_falls_back_and_strips(tmp_path):
    rec = {"subtitles": {"full_text": "[0000.00 -> 0001.60] 带时间戳的"}}
    txt, src = stats.subtitle_text(tmp_path, rec)       # 无 subtitles.json
    assert txt == "带时间戳的"
    assert src == "full_text_fallback"


def test_subtitle_text_none(tmp_path):
    txt, src = stats.subtitle_text(tmp_path, {})
    assert txt == "" and src == "none"


def test_field_value_clean_subtitle(tmp_path):
    (tmp_path / "subtitles.json").write_text(
        json.dumps([{"index": 1, "text": "口播"}], ensure_ascii=False), encoding="utf-8")
    rec = {"caption": "文案", "subtitles": {"full_text": "[0000.00 -> 0001.60] 脏"}}
    assert _field_value(rec, ["caption", "subtitles.text"], tmp_path) == "文案\n口播"


# ---------- 繁→简归一化 (v0.2) ----------
def test_to_simplified_basic():
    assert stats.to_simplified("這說為個們來時") == "这说为个们来时"


def test_to_simplified_keeps_simplified():
    assert stats.to_simplified("这是简体") == "这是简体"


def test_to_simplified_empty():
    assert stats.to_simplified("") == ""
    assert stats.to_simplified(None) == ""


def test_text_liveness_matches_after_simplification():
    """繁体文本先归一化再匹配, 否则漏命中"""
    lex = stats.load_lexicon()
    trad = stats.to_simplified("我們真的很開心")
    assert stats.text_liveness(trad, lex)["first_person"] >= 1
    assert stats.text_liveness(trad, lex)["emotion"] >= 1


# ---------- 字幕来源优先级: LLM 修正版 > 原始 ASR (v0.2) ----------
def test_subtitle_text_prefers_llm_corrected(tmp_path):
    (tmp_path / "subtitles.json").write_text(
        json.dumps([{"index": 1, "text": "原始错字版"}], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "subtitles.llm.json").write_text(
        json.dumps([{"index": 1, "text": "修正版"}], ensure_ascii=False), encoding="utf-8")
    txt, src = stats.subtitle_text(tmp_path, {})
    assert txt == "修正版" and src == "llm_corrected"
    txt2, src2 = stats.subtitle_text(tmp_path, {}, prefer="raw")
    assert txt2 == "原始错字版" and src2 == "segments_raw"


# ---------- 词表 v0.2 扩充 ----------
def test_lexicon_v02_additions():
    lex = stats.load_lexicon()
    for dim, words in (("first_person", ["我的"]),
                       ("colloquial", ["呀", "啦", "我跟你说"]),
                       ("emotion", ["幸福", "好看", "感谢", "热闹"]),
                       ("slang", ["打卡", "出片", "氛围感"]),
                       ("meme", ["泰裤辣", "尊嘟假嘟"])):
        have = lex[dim].get("words") or []
        for w in words:
            assert w in have, f"{dim} 缺少 {w}"


def test_lexicon_retains_v01_words():
    lex = stats.load_lexicon()
    for dim, words in (("first_person", ["我们", "咱们"]),
                       ("colloquial", ["家人们", "巴适"]),
                       ("emotion", ["太美了", "泪目"]),
                       ("slang", ["yyds", "显眼包"]),
                       ("meme", ["city不city", "科目三"])):
        have = lex[dim].get("words") or []
        for w in words:
            assert w in have, f"{dim} 丢了 v0.1 的 {w}"


def test_lexicon_version_bumped():
    import yaml
    from pathlib import Path
    raw = yaml.safe_load((Path(stats.__file__).parent / "lexicon.yaml").read_text(encoding="utf-8"))
    assert raw["version"] == "0.2"


# ---------- 指标库注册 ----------
def test_registry_v02_contains_new_metrics():
    reg = Registry()
    for mid in ("is_holiday", "holiday_name", "is_makeup_workday",
                "tl_cap_first_person", "tl_all_rhetorical", "tl_index_cap",
                "visual_present_ratio", "selfie_score", "camera_motion",
                "video_resolution", "etir", "strong_etir", "eti_mean",
                "tl_llm_meme"):
        assert reg.get(mid), f"指标库缺少 {mid}"
        assert reg.get(mid).get("v0") is True, f"{mid} 未标记为已实现"


def test_registry_holiday_no_longer_need_collect():
    reg = Registry()
    reqs = [na["requirement"] for na in reg.not_available]
    assert "是否节假日" not in reqs
    assert "视频分辨率" not in reqs


# ---------- 目标账号判定 (accounts.yaml) ----------
def test_account_status_whitelist_target():
    out = stats.account_status({"id": "405032890799566", "nickname": "红河文旅"})
    assert out["account_status"] == "target"
    assert out["is_target_account"] is True
    assert out["account_level"] == "地市" and out["account_province"] == "云南"


def test_account_status_borderline():
    """融媒体中心 ≠ 文旅局 → borderline, 需研究端决定去留"""
    out = stats.account_status({"id": "110105711688", "nickname": "云南红河发布"})
    assert out["account_status"] == "borderline"
    assert out["is_target_account"] is False


def test_account_status_manual_override_non_target():
    for uid in ("63182365037", "69373540632", "1538959322664663", "7585894849103578161"):
        out = stats.account_status({"id": uid})
        assert out["account_status"] == "non_target", uid
        assert out["is_target_account"] is False


def test_account_status_cert_keyword_rule():
    """不在白名单但认证含文旅行政关键词 → target"""
    out = stats.account_status({"id": "999", "certification": "XX省文化和旅游厅官方抖音号"})
    assert out["account_status"] == "target"
    out2 = stats.account_status({"id": "998", "certification": "XX市融媒体中心官方账号"})
    assert out2["account_status"] == "borderline"
    out3 = stats.account_status({"id": "997", "certification": "XX科技有限公司"})
    assert out3["account_status"] == "non_target"


def test_account_status_cert_keyword_covers_gd_variant():
    """回归: 浙江省文化广电和旅游厅官方 → 曾误判 non_target(关键词漏了'广电'变体)"""
    out = stats.account_status({"id": "271", "certification": "浙江省文化广电和旅游厅官方"})
    assert out["account_status"] == "target", out
    out2 = stats.account_status({"id": "272", "certification": "XX省广播电视和旅游局官方"})
    assert out2["account_status"] == "target", out2


def test_account_status_shiye_danwei_boundary():
    """事业单位口径: 文旅系统的信息中心=target; 宣传系统的融媒体中心=borderline"""
    a = stats.account_status({"id": "281", "certification": "重庆市文化和旅游信息中心（重庆市文化和旅游数据中心）"})
    assert a["account_status"] == "target"
    b = stats.account_status({"id": "282", "certification": "红河州融媒体中心官方抖音号"})
    assert b["account_status"] == "borderline"


def test_account_status_nickname_fallback():
    """uid 未知时按昵称兜底匹配白名单(预登记阶段用), 并记录 account_match"""
    cfg = {"accounts": [{"uid": "1", "nickname": "测试文旅", "status": "target",
                         "level": "省级", "province": "测试省", "region": "东部"}],
           "rule": {"target_cert_keywords": [], "borderline_cert_keywords": []}}
    out = stats.account_status({"nickname": "测试文旅", "certification": ""}, cfg)
    assert out["account_status"] == "target"
    assert out["account_match"] == "nickname"
    assert out["account_level"] == "省级" and out["account_region"] == "东部"


def test_account_match_reports_provenance():
    """account_match 说明判定依据, 便于审计"""
    assert stats.account_status({"id": "405032890799566"})["account_match"] == "uid"
    assert stats.account_status({"id": "63182365037"})["account_match"] == "manual_uid"
    assert stats.account_status({"id": "997", "certification": "XX科技有限公司"})["account_match"] == "cert_other"


def test_account_status_no_cert_is_unknown():
    """无认证且无记录 → unknown(不猜, 交人工)"""
    out = stats.account_status({"id": "996"})
    assert out["account_status"] == "unknown"
    assert out["is_target_account"] is None


def test_account_status_missing_uid():
    out = stats.account_status({})
    assert out["account_uid"] is None and out["account_status"] == "unknown"


# ---------- 样本分层口径 (sample_policy) ----------
def test_sample_role_mapping():
    """口径决定: 主样本=target, 稳健性对照=borderline, 排除=non_target"""
    assert stats.sample_role("target") == "main"
    assert stats.sample_role("borderline") == "robustness"
    assert stats.sample_role("non_target") == "excluded"
    assert stats.sample_role("unknown") == "undetermined"


def test_account_status_sets_sample_role():
    assert stats.account_status({"id": "405032890799566"})["sample_role"] == "main"
    assert stats.account_status({"id": "110105711688"})["sample_role"] == "robustness"
    assert stats.account_status({"id": "63182365037"})["sample_role"] == "excluded"
    assert stats.account_status({})["sample_role"] == "undetermined"


def test_sample_policy_recorded_in_config():
    cfg = stats.load_accounts()
    pol = cfg.get("sample_policy") or {}
    assert pol.get("main") == ["target"]
    assert pol.get("robustness") == ["borderline"]
    assert pol.get("excluded") == ["non_target"]
    assert pol.get("decided_at"), "样本口径决定需留痕(decided_at)"


def test_accounts_yaml_schema():
    cfg = stats.load_accounts()
    assert cfg.get("version")
    assert cfg.get("rule", {}).get("target_cert_keywords")
    assert cfg.get("rule", {}).get("borderline_cert_keywords")
    assert cfg.get("accounts") and cfg.get("manual_overrides")
    for a in cfg["accounts"]:
        # uid 可为 null(预登记阶段尚不知, 采集后回填) —— 但昵称/状态/证据必须有
        assert a.get("nickname"), a
        assert a.get("status") in ("target", "borderline", "non_target"), a
        assert a.get("evidence"), f"{a.get('nickname')} 缺少 evidence"
        if a.get("status") == "target" and a.get("level") in ("省级",):
            assert a.get("province") and a.get("region"), f"{a.get('nickname')} 缺少省份/大区"
