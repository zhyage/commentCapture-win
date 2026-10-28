# -*- coding: utf-8 -*-
"""中国法定节假日日历 (国务院办公厅口径, 含调休)

来源(官方通知, 逐条核对):
  2024 — 国办发明电〔2023〕7号
    https://www.gov.cn/zhengce/content/202310/content_6911527.htm
  2025 — 国办发明电〔2024〕12号
    https://www.gov.cn/zhengce/zhengceku/202411/content_6986383.htm
  2026 — 国办发明电〔2025〕7号
    https://www.gov.cn/zhengce/content/202511/content_7047090.htm

口径(对应 idea.md 控制变量"是否节假日"):
  is_holiday         官方放假调休的放假日(不含普通周末)
  holiday_name       节日名
  is_weekend         周六/周日
  is_makeup_workday  调休上班日(周末需上班)
  is_rest_day        放假日 或 (周末 且 非调休上班)

设计原则: 未收录年份返回 None(不猜), 由调用方显式处理并计入报告缺口。
"""
from datetime import date, timedelta

# (节日名, 起始日, 结束日) — 含调休放假的所有日期
_SPANS = [
    # ---------- 2024 ----------
    ("元旦", "2024-01-01", "2024-01-01"),
    ("春节", "2024-02-10", "2024-02-17"),
    ("清明节", "2024-04-04", "2024-04-06"),
    ("劳动节", "2024-05-01", "2024-05-05"),
    ("端午节", "2024-06-10", "2024-06-10"),
    ("中秋节", "2024-09-15", "2024-09-17"),
    ("国庆节", "2024-10-01", "2024-10-07"),
    # ---------- 2025 ----------
    ("元旦", "2025-01-01", "2025-01-01"),
    ("春节", "2025-01-28", "2025-02-04"),
    ("清明节", "2025-04-04", "2025-04-06"),
    ("劳动节", "2025-05-01", "2025-05-05"),
    ("端午节", "2025-05-31", "2025-06-02"),
    ("国庆节中秋节", "2025-10-01", "2025-10-08"),
    # ---------- 2026 ----------
    ("元旦", "2026-01-01", "2026-01-03"),
    ("春节", "2026-02-15", "2026-02-23"),
    ("清明节", "2026-04-04", "2026-04-06"),
    ("劳动节", "2026-05-01", "2026-05-05"),
    ("端午节", "2026-06-19", "2026-06-21"),
    ("中秋节", "2026-09-25", "2026-09-27"),
    ("国庆节", "2026-10-01", "2026-10-07"),
]

# 调休上班日(周末需上班)
_MAKEUP = [
    # 2024
    "2024-02-04", "2024-02-18", "2024-04-07", "2024-04-28", "2024-05-11",
    "2024-09-14", "2024-09-29", "2024-10-12",
    # 2025
    "2025-01-26", "2025-02-08", "2025-04-27", "2025-09-28", "2025-10-11",
    # 2026
    "2026-01-04", "2026-02-14", "2026-02-28", "2026-05-09", "2026-09-20",
    "2026-10-10",
]


def _d(s: str) -> date:
    return date.fromisoformat(s)


# {日期: 节日名}
HOLIDAYS: dict = {}
for _name, _start, _end in _SPANS:
    _cur, _stop = _d(_start), _d(_end)
    while _cur <= _stop:
        HOLIDAYS[_cur] = _name
        _cur += timedelta(days=1)

MAKEUP_WORKDAYS = {_d(s) for s in _MAKEUP}

SUPPORTED_YEARS = tuple(sorted({d.year for d in HOLIDAYS} | {d.year for d in MAKEUP_WORKDAYS}))


def is_supported(d: date) -> bool:
    """该年份是否已收录(未收录 → 相关字段返回 None, 不猜)"""
    return d.year in SUPPORTED_YEARS


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def holiday_name(d: date):
    return HOLIDAYS.get(d)


def is_holiday(d: date):
    """是否处于官方放假调休安排内(不含普通周末); 年份未收录 → None"""
    if not is_supported(d):
        return None
    return d in HOLIDAYS


def is_makeup_workday(d: date):
    """是否调休上班日(周末但需上班)"""
    if not is_supported(d):
        return None
    return d in MAKEUP_WORKDAYS


def is_rest_day(d: date):
    """是否休息日 = 放假日 或 (周末 且 非调休上班)"""
    if not is_supported(d):
        return None
    if d in HOLIDAYS:
        return True
    return is_weekend(d) and d not in MAKEUP_WORKDAYS


def info(d: date) -> dict:
    """一次性取全部节假日字段(供统计引擎直接展开)"""
    return {
        "is_holiday": is_holiday(d),
        "holiday_name": holiday_name(d),
        "is_weekend": is_weekend(d),
        "is_makeup_workday": is_makeup_workday(d),
        "is_rest_day": is_rest_day(d),
    }
