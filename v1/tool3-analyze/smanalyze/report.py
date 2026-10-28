# -*- coding: utf-8 -*-
"""诚实报告生成 (report.md)"""
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from .verdict import DONE, PARTIAL, NEED_COLLECT, IMPOSSIBLE

# Text Liveness 六个维度: 词典指标名 → 对应 LLM 标注列
TL_DIMS = ("first_person", "colloquial", "emotion", "slang", "meme", "rhetorical")

# 构念口径说明(随报告交付, 避免研究端误用)
CONSTRUCT_NOTES = [
    "**词典维度 ≠ LLM 维度(重要)**：`tl_*_meme` 测的是「**引用具体梗**」，"
    "`tl_llm_meme` 测的是更宽的「**幽默化**」(含自嘲/吐槽)；"
    "`tl_*_slang` 与 `tl_llm_slang` 同理。两组**不是同一构念，不可互相替代**——"
    "按 idea.md 的 HCI3「幽默化」应优先用 LLM 版，词典版仅作稳健性对照。",
    "**Text Liveness 词典口径**：纯字符串命中(长词优先、非重叠)，"
    "匹配前做繁→简归一化；词表见 `smanalyze/lexicon.yaml`(改词表需重算，零成本)。",
    "**字幕来源**：优先 LLM 修正版 `subtitles.llm.json`，缺失回退原始 ASR；"
    "ASR 仍可能残留错字(实测如「国家飞鱼」应为「国家级非遗」)，逐条来源见 `subtitle_text_source`。",
    "**ETI 分母**：`etir/strong_etir/eti_mean` 的分母只含「成功标注的评论」(`eti_n`)，"
    "不含未采到的评论；务必与 `comment_coverage` 一起解读。",
    "**样本量**：本表视频数很小，跨账号/跨地区异质性分析需先扩采。",
    "**地区口径（2026-09-11 已定）**：扩采后账号仍以西部为主（西部 7 / 中部 1 / 东部 1），"
    "**不足以做东中西部对比** → `account_region` 仅作控制变量，**不做地区异质性分析**；"
    "论文须明确写出该限制（口径见 `accounts.yaml` 的 `sample_policy.region_policy`）。",
    "**账号口径**：`account_status` ∈ target/borderline/non_target/unknown（规则见 `accounts.yaml`）；"
    "样本分层 `sample_role` ∈ main/robustness/excluded/undetermined —— **已定口径**："
    "主样本用 `main`(=target)，`robustness`(=borderline, 融媒体中心等非文旅局主体)仅作稳健性对照，"
    "`excluded` 不进样本。注意工具2 抖音号模式的主页翻页会混入他人作品(实测 4.2%)，务必用 `sample_role` 过滤。",
]


def _cov_line(coverage_values: list) -> str:
    vals = [v for v in coverage_values if v is not None]
    if not vals:
        return "无覆盖数据"
    return (f"中位 {statistics.median(vals):.1%}, 最低 {min(vals):.1%}, "
            f"最高 {max(vals):.1%}")


def _dist(rows: list, key: str) -> str:
    c = Counter(r.get(key) for r in rows if r.get(key) not in (None, ""))
    if not c:
        return "无"
    return ", ".join(f"{k}: {v}" for k, v in c.most_common())


def _tl_agreement(rows: list) -> list:
    """词典(命中>0) vs LLM(=1) 的逐维一致率; 缺列则跳过"""
    out = []
    for d in TL_DIMS:
        lex_col, llm_col = f"tl_all_{d}", f"tl_llm_{d}"
        if not rows or lex_col not in rows[0] or llm_col not in rows[0]:
            continue
        lex = [1 if (r.get(lex_col) or 0) not in ("", None) and int(r.get(lex_col) or 0) > 0 else 0
               for r in rows]
        llm = [1 if str(r.get(llm_col)) == "1" else 0 for r in rows]
        agree = sum(1 for a, b in zip(lex, llm) if a == b)
        out.append(f"| {d} | {sum(lex)}/{len(rows)} | {sum(llm)}/{len(rows)} | {agree}/{len(rows)} |")
    return out


def _labeled_tasks(rows_video: list, rows_comment: list) -> list:
    cols = set()
    for rows in (rows_video, rows_comment):
        for r in rows[:1]:
            cols |= {k for k in r if k.startswith("tl_llm_") or k in
                     ("willingness_level", "video_category",
                      "is_authenticity", "is_social_presence")}
    return sorted(cols)


def build_report(verdicts: list, registry, rows_video: list, rows_comment: list,
                 data_dir: Path, coverage_values: list) -> str:
    s = {DONE: [], PARTIAL: [], NEED_COLLECT: [], IMPOSSIBLE: []}
    for v in verdicts:
        s[v["status"]].append(v)

    total_comments = sum((r.get("comments_collected") or 0) for r in rows_video)
    lines = [
        "# 分析报告 — 工具3 统计引擎",
        "",
        f"- 数据目录: `{data_dir}`",
        f"- 视频数: {len(rows_video)} | 评论总数: {total_comments}",
        f"- 指标库版本: {registry.version} | 执行时间: {datetime.now():%Y-%m-%d %H:%M}",
        f"- 评论层变量: {len(rows_comment)} 行",
        "",
    ]

    if s[DONE]:
        lines += ["## ✅ 可做 (统计引擎已输出)", "",
                  "| 指标 | 说明 |", "|---|---|"]
        for v in s[DONE]:
            lines.append(f"| `{v['metric_id']}` | {v['reason']} |")
        lines.append("")

    if s[PARTIAL]:
        lines += ["## ⚠️ 部分可做 (值可用, 但有前提)", "",
                  "| 指标 | 限制 |", "|---|---|"]
        for v in s[PARTIAL]:
            lines.append(f"| `{v.get('metric_id') or v['requirement']}` | {v['reason']} |")
        lines.append("")

    if s[NEED_COLLECT]:
        lines += ["## 🔶 需补采 (工具1 可补)", "",
                  "| 需求 | 缺什么 | 建议 |", "|---|---|---|"]
        for v in s[NEED_COLLECT]:
            lines.append(f"| {v['requirement']} | {v['reason']} | {v.get('detail','')} |")
        lines.append("")

    if s[IMPOSSIBLE]:
        lines += ["## ❌ 做不了 (当前数据无法支持)", "",
                  "| 需求 | 原因 | 替代路径 |", "|---|---|---|"]
        for v in s[IMPOSSIBLE]:
            lines.append(f"| {v['requirement']} | {v['reason']} | {v.get('detail','')} |")
        lines.append("")

    lines += [
        "## 数据可信度总览",
        "",
        f"- 评论覆盖率: {_cov_line(coverage_values)}",
        "- 统计指标方法: 纯计算(无模型), 完全可复现",
        "- 长尾指标(回复速度等)使用分位 p25/p50/p75/p90, 不给均值",
        f"- 已 JOIN 的标注列: {', '.join(_labeled_tasks(rows_video, rows_comment)) or '无'}",
        f"- 字幕文本来源: {_dist(rows_video, 'subtitle_text_source')}",
        f"- **账号判定分布**: {_dist(rows_video, 'account_status')}",
        f"- **样本分层**: {_dist(rows_video, 'sample_role')}"
        "（主样本用 `sample_role == 'main'`；`robustness`=稳健性对照；`excluded` 不进样本）",
    ]

    agree = _tl_agreement(rows_video)
    if agree:
        lines += ["", "### Text Liveness: 词典 vs LLM 对照", "",
                  "| 维度 | 词典命中 | LLM 命中 | 一致率 |", "|---|---|---|---|"]
        lines += agree

    lines += ["", "## 口径与已知局限", ""]
    lines += [f"- {n}" for n in CONSTRUCT_NOTES]
    return "\n".join(lines)
