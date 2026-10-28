# -*- coding: utf-8 -*-
"""工具2 定位/身份校验测试 (无网络; 用假 page 对象)

覆盖 2026-09-11 修复: 主页 DOM 经常不渲染"抖音号:"字段(实测 9 个号里 5 个),
原实现直接放弃账号 → 采集会静默跳过。
现改为"渲染等待 + 三级证据": ①抖音号文本 → ②官方认证徽章 → ③昵称,
且**不放宽到无条件通过**(避免采错账号)。
"""
import pytest

from smsearch.search import (_card_certification, _card_nickname, _match_cards,
                             _profile_identity, _verify_profile_did,
                             _wait_profile_identity)


class FakePage:
    """按 JS 内容返回不同结果:
       含 'badge-role-name' → 主页头部身份(dict); 其余 → 页面全文(str)"""

    def __init__(self, body_text="", nickname="", role=""):
        self.body_text, self.nickname, self.role = body_text, nickname, role

    def evaluate(self, js):
        if "badge-role-name" in js:
            return {"nickname": self.nickname, "role": self.role}
        return self.body_text


# ---------- 卡片解析 ----------
def test_card_nickname_verified_card():
    assert _card_nickname("贵州文旅认证徽章贵州省文化和旅游厅官方抖音号: gzslyfzwyh5864") == "贵州文旅"


def test_card_nickname_unverified_card():
    assert _card_nickname("皖美全景游关注抖音号: anhuilvyou990066378") == "皖美全景游"


def test_card_nickname_empty():
    assert _card_nickname("") == ""


def test_card_certification_verified():
    assert _card_certification("云南省文化和旅游厅认证徽章云南省文化和旅游厅官方抖音号: ynswhhlyt1630") \
        == "云南省文化和旅游厅官方"


def test_card_certification_absent():
    assert _card_certification("皖美全景游关注抖音号: anhuilvyou990066378") == ""


# ---------- 卡片匹配 ----------
def _card(digits, sec, text):
    return {"digits": digits, "href": f"/user/{sec}", "nick": text}


def test_match_cards_returns_nickname_and_certification():
    cards = [_card("gzslyfzwyh5864", "SEC_A", "贵州文旅认证徽章贵州省文化和旅游厅官方")]
    out = _match_cards(cards, "gzslyfzwyh")
    assert len(out) == 1
    assert out[0]["sec_uid"] == "SEC_A"
    assert out[0]["nickname"] == "贵州文旅"
    assert out[0]["certification"] == "贵州省文化和旅游厅官方"


def test_match_cards_exact_and_dedupe():
    cards = [_card("abc", "S1", "甲"), _card("abc", "S1", "甲"), _card("abcd", "S2", "乙")]
    assert [c["sec_uid"] for c in _match_cards(cards, "abc")] == ["S1", "S2"]


def test_match_cards_no_hit():
    assert _match_cards([_card("zzz", "S9", "别的")], "abc") == []


# ---------- 主页身份读取 ----------
def test_profile_identity_reads_nick_and_role():
    ident = _profile_identity(FakePage(nickname="云南", role="云南省文化和旅游厅官方"))
    assert ident["nickname"] == "云南" and ident["role"] == "云南省文化和旅游厅官方"


def test_wait_profile_identity_timeout_returns_empty():
    """头部始终为空 → 超时返回空(不抛异常, 不无限等)"""
    ident = _wait_profile_identity(FakePage(), timeout_s=0.2)
    assert ident == {"nickname": "", "role": ""}


def test_wait_profile_identity_success():
    assert _wait_profile_identity(FakePage(nickname="云南"), timeout_s=1)["nickname"] == "云南"


# ---------- 身份校验: 一级证据 ----------
def test_verify_by_douyin_id_text():
    assert _verify_profile_did(FakePage(body_text="抖音号: gzslyfzwyh"), "gzslyfzwyh") is True


def test_verify_douyin_id_mismatch_fails():
    assert _verify_profile_did(FakePage(body_text="别人 抖音号: SXLY66"), "sxly6") is False


def test_verify_douyin_id_case_insensitive():
    assert _verify_profile_did(FakePage(body_text="抖音号: AnHuiLvYou"), "anhuilvyou") is True


# ---------- 身份校验: 二级证据(认证徽章) ----------
def test_verify_fallback_role_badge():
    """主页不渲染抖音号时, 官方认证徽章相符 → 通过"""
    p = FakePage(body_text="云南省文化和旅游厅 关注 粉丝 获赞",
                 nickname="云南省文化和旅游厅", role="云南省文化和旅游厅官方抖音号")
    assert _verify_profile_did(p, "ynswhhlyt",
                               expect_role="云南省文化和旅游厅官方") is True


def test_verify_fallback_role_takes_priority_over_nick():
    p = FakePage(body_text="无字段", nickname="", role="贵州省文化和旅游厅官方")
    assert _verify_profile_did(p, "gzslyfzwyh", expect_nick="别的名字",
                               expect_role="贵州省文化和旅游厅官方") is True


# ---------- 身份校验: 三级证据(昵称) ----------
def test_verify_fallback_nickname_when_field_missing():
    p = FakePage(body_text="无字段", nickname="贵州文旅")
    assert _verify_profile_did(p, "gzslyfzwyh", expect_nick="贵州文旅") is True


def test_verify_fallback_nickname_partial_match():
    p = FakePage(body_text="无字段", nickname="云南红河发布")
    assert _verify_profile_did(p, "YNHHFB", expect_nick="云南红河发布官方") is True


# ---------- 不放宽: 证据不足必须失败 ----------
def test_verify_role_and_nick_mismatch_fails():
    """认证与昵称都不符 → 必须失败(避免采错账号)"""
    p = FakePage(body_text="无字段", nickname="皖美全景游", role="皖美全景游")
    assert _verify_profile_did(p, "Anhuilvyou", expect_nick="安徽文旅",
                               expect_role="安徽省文化和旅游厅官方") is False


def test_verify_no_evidence_fails():
    p = FakePage(body_text="无字段", nickname="安徽文旅")
    assert _verify_profile_did(p, "Anhuilvyou") is False


def test_verify_empty_header_fails():
    """头部始终渲染不出来 → 不确认(且 wait_s 可注入, 测试不必真等 25s)"""
    p = FakePage(body_text="无字段")
    assert _verify_profile_did(p, "Anhuilvyou", expect_nick="安徽文旅",
                               expect_role="安徽省文化和旅游厅官方", wait_s=0.2) is False
