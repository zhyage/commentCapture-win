# -*- coding: utf-8 -*-
"""过滤层 (流式): 硬过滤(逐条) + 语义判定(批量, 由 llm 提供)

两段式: 搜索流中每条先过硬过滤, 攒批后交 LLM 语义判定。
语义判定三态: 符合(计入命中) / 不符合(丢弃) / 不确定(单独留存, 不占名额)

【决策】keywords 只作为搜索词使用, 不做主题硬过滤 —— 内容相关性全部交给
DeepSeek 语义判定(describe 意图)。硬过滤只负责客观字段: 作者/时间/互动数。
"""
from datetime import date, datetime


def _match_authors(aw, authors):
    if not authors:
        return True
    nick = (aw.get("author") or {}).get("nickname") or ""
    return any(a in nick for a in authors)


def _match_time(aw, after, before):
    ct = aw.get("create_time")
    if not ct or (not after and not before):
        return True
    d = datetime.fromtimestamp(int(ct)).date()
    if after and d < date.fromisoformat(str(after)):
        return False
    if before and d > date.fromisoformat(str(before)):
        return False
    return True


def hard_filter(aw, filters):
    """硬过滤单条: 返回 (通过?, matched_conditions)。只把实际设置的过滤计入 matched
    (keywords 不再参与硬过滤)"""
    matched = []
    if filters.get("authors"):
        if not _match_authors(aw, filters["authors"]):
            return False, []
        matched.append("authors")

    likes = (aw.get("statistics") or {}).get("digg_count") or 0
    if filters.get("min_likes"):
        if likes < filters["min_likes"]:
            return False, []
        matched.append("min_likes")

    comments = (aw.get("statistics") or {}).get("comment_count") or 0
    if filters.get("min_comments"):
        if comments < filters["min_comments"]:
            return False, []
        matched.append("min_comments")

    if filters.get("after") or filters.get("before"):
        if not _match_time(aw, filters["after"], filters["before"]):
            return False, []
        matched.append("time")

    return True, matched


def sort_hits_by_likes(hits: list) -> list:
    """命中列表按点赞数降序 (抖音号模式主页无排序, 输出截断前先按赞排序)"""
    return sorted(hits, key=lambda r: (r["aweme"].get("statistics") or {}).get("digg_count") or 0,
                  reverse=True)


def build_honesty_notes(request, sort_applied: bool) -> list:
    is_did = bool(request.get("douyin_ids"))
    notes = [
        "内容相关性(景点介绍/推荐/民俗等)由 DeepSeek 语义判定, 仅'符合'计入命中; '不确定'单独留存待人工复核",
        "min_likes/min_comments/时间/作者 基于搜索结果字段, 精确判定",
        "total_favorited 等字段搜索响应不可信, 以工具1采集为准",
    ]
    if is_did:
        notes += [
            "抖音号模式: 按抖音号精确匹配定位用户主页, 全量翻页(无排序, 一条不落)",
            "抖音号模式: 主页作品接口无排序参数, 默认按发布时间倒序",
            "抖音号模式: limit 为每个抖音号各自的截断 — 每号内部按点赞数降序取前 limit 条, 合并去重输出",
            "抖音号模式: 多个抖音号串行处理, 跨号按 aweme_id 去重; 全部符合条数见 hits_count",
        ]
    else:
        notes += [
            "keywords 仅作为搜索词使用, 不做主题硬过滤",
            "搜索只翻了有限页, 未翻尽全部结果; 命中达到 limit 即提前终止",
        ]
    if sort_applied:
        notes.append("排序为按点赞(筛选已切换成功)")
    elif not is_did:
        notes.append("排序控件未成功切换, 实际为平台默认排序")
    return notes
