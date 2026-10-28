# -*- coding: utf-8 -*-
"""四态判定: 对每条需求项给出 可做/部分可做/需补采/做不了 + 理由

判定流程 (DESIGN §2):
  查指标库 → 有: 检查依赖字段/数据完整性 → ✅可做 / ⚠️部分可做
            → 无: 检查是否已知不可得/需补采 → 🔶需补采 / ❌做不了
"""
from pathlib import Path

DONE = "可做"
PARTIAL = "部分可做"
NEED_COLLECT = "需补采"
IMPOSSIBLE = "做不了"

ICON = {DONE: "✅", PARTIAL: "⚠️", NEED_COLLECT: "🔶", IMPOSSIBLE: "❌"}

# 依赖评论采集覆盖率的指标(覆盖率不足 → 部分可做)
COVERAGE_SENSITIVE = {
    "reply_rate", "reply_speed_p25_min", "reply_speed_p50_min",
    "reply_speed_p75_min", "reply_speed_p90_min", "reply_text_len_avg",
    "reply_emoji_rate", "reply_at_rate", "author_reply_n", "author_engaged_comments",
    "comment_len_avg", "comment_len_median", "comment_emoji_rate",
    "comment_question_rate", "top_reply_ratio", "hot_comment_ratio",
    "ip_region_entropy", "ip_top_region", "comment_velocity_24h",
    # 因变量派生: 分母是"采到的评论", 覆盖率低 → ETIR 失真
    "etir", "strong_etir", "eti_mean", "eti_n",
}
# 依赖 LLM 标注的指标(有波动 → 部分可做)
LLM_SENSITIVE = {"video_category", "willingness_level", "is_authenticity", "is_social_presence",
                 "tl_llm_first_person", "tl_llm_colloquial", "tl_llm_emotion",
                 "tl_llm_slang", "tl_llm_meme", "tl_llm_rhetorical"}
# 读取工具1 派生结果的指标(不属"纯计算", 依赖上游管线质量)
DERIVED = {"visual_present_ratio", "face_count_avg", "face_count_max", "selfie_score",
           "shake_index", "camera_motion", "video_resolution", "scene_professional_score",
           "etir", "strong_etir", "eti_mean", "eti_n"}

COVERAGE_THRESHOLD = 0.5      # 覆盖率中位低于此 → 部分可做


def _coverage_stats(coverage_values: list):
    vals = [v for v in coverage_values if v is not None]
    if not vals:
        return None, None
    vals.sort()
    mid = vals[len(vals) // 2]
    return round(mid, 4), round(min(vals), 4)


def judge(requirement: str, registry, coverage_values: list | None = None) -> dict:
    """判定单个需求项。coverage_values: 各视频的评论覆盖率(用于判断数据充分性)"""
    mid_cov, min_cov = _coverage_stats(coverage_values or [])
    mid_pct = f"{mid_cov:.0%}" if mid_cov is not None else "未知"

    metric_id = registry.resolve(requirement)
    meta = registry.get(metric_id)

    if meta:
        # 指标存在
        if not meta.get("v0"):
            engine = meta.get("engine")
            if engine == "llm":
                why = "需先执行 smanalyze label 生成标注列; 标签体系可配置"
            elif engine == "derived":
                why = "需先由工具1 运行派生管线生成 visual.json / scene.json"
            else:
                why = f"指标已登记但 v0 未实现(engine={engine})"
            return {"requirement": requirement, "metric_id": metric_id,
                    "status": NEED_COLLECT, "icon": ICON[NEED_COLLECT],
                    "reason": why, "detail": meta.get("reliability", "")}

        # 覆盖率敏感指标
        if metric_id in COVERAGE_SENSITIVE:
            if mid_cov is not None and mid_cov < COVERAGE_THRESHOLD:
                return {"requirement": requirement, "metric_id": metric_id,
                        "status": PARTIAL, "icon": ICON[PARTIAL],
                        "reason": f"评论覆盖率中位仅 {mid_pct}(最低 {min_cov:.0%}), 值可能失真",
                        "detail": meta.get("reliability", "")}
            return {"requirement": requirement, "metric_id": metric_id,
                    "status": DONE, "icon": ICON[DONE],
                    "reason": f"纯统计计算; 覆盖率中位 {mid_pct}",
                    "detail": meta.get("reliability", "")}

        # LLM 标注指标
        if metric_id in LLM_SENSITIVE:
            return {"requirement": requirement, "metric_id": metric_id,
                    "status": PARTIAL, "icon": ICON[PARTIAL],
                    "reason": "LLM 标注有波动, 需抽检; 抽样策略影响结果分布",
                    "detail": meta.get("reliability", "")}

        # 读取工具1/标注产物的派生指标
        if meta.get("engine") == "derived" or metric_id in DERIVED:
            return {"requirement": requirement, "metric_id": metric_id,
                    "status": DONE, "icon": ICON[DONE],
                    "reason": "读取上游派生结果(工具1 视觉管线 / 标注结果)",
                    "detail": meta.get("reliability", "")}

        return {"requirement": requirement, "metric_id": metric_id,
                "status": DONE, "icon": ICON[DONE],
                "reason": "纯统计计算, 完全可复现",
                "detail": meta.get("reliability", "")}

    # 指标不存在 → 查不可得/需补采清单
    na = registry.find_not_available(requirement)
    if na:
        status = NEED_COLLECT if na["status"] == "need_collect" else IMPOSSIBLE
        return {"requirement": requirement, "metric_id": None,
                "status": status, "icon": ICON[status],
                "reason": na.get("reason", ""),
                "detail": na.get("alternative", "")}

    # 完全未知的需求
    return {"requirement": requirement, "metric_id": None,
            "status": IMPOSSIBLE, "icon": ICON[IMPOSSIBLE],
            "reason": "指标库无此指标, 且不在已知可得范围",
            "detail": "请确认需求, 或反馈给工具1 补采"}


def judge_all(requirements: list, registry, coverage_values: list | None = None) -> list:
    return [judge(r, registry, coverage_values) for r in requirements]


def summarize(verdicts: list) -> dict:
    out = {DONE: [], PARTIAL: [], NEED_COLLECT: [], IMPOSSIBLE: []}
    for v in verdicts:
        out[v["status"]].append(v["requirement"])
    return out
