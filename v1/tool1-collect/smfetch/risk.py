# -*- coding: utf-8 -*-
"""风控层: 真人节奏 / 上限 / 卡住检测 (纯逻辑, 可注入随机源)"""
import random
from datetime import date


class RiskController:
    """节奏与熔断控制器。

    - 等待时间: 按 pacing 随机, 模拟真人
    - 阅读停顿: 每 pause_every 轮一次长停顿
    - 卡住检测: 连续 stall_limit 轮无新增 → 应停止
    - 评论上限 / 单日限额: 超出即停
    """

    def __init__(self, pacing: dict, safety: dict | None = None, rng: random.Random | None = None):
        self.p = pacing
        self.s = safety or {}
        self.rng = rng or random
        self.stalls = 0
        self._day_requests: dict[str, int] = {}

    # --- 节奏 ---
    def scroll_wait(self) -> float:
        lo, hi = self.p.get("scroll_wait", [6, 12])
        return self.rng.uniform(lo, hi)

    def pause_every(self) -> int:
        return int(self.p.get("pause_every", 5))

    def long_pause(self) -> float:
        lo, hi = self.p.get("pause_long", [15, 25])
        return self.rng.uniform(lo, hi)

    # --- 卡住检测 ---
    def on_new_data(self) -> None:
        self.stalls = 0

    def on_no_data(self) -> bool:
        """返回 True 表示应停止 (连续无新增达到阈值)"""
        self.stalls += 1
        return self.stalls >= int(self.p.get("stall_limit", 5))

    # --- 上限 ---
    def under_comment_cap(self, count: int) -> bool:
        return count < int(self.p.get("max_comments", 2000))

    def under_round_cap(self, round_no: int) -> bool:
        return round_no < int(self.p.get("max_scrolls", 25))

    # --- 单日限额 ---
    def record_request(self, day: str | None = None) -> None:
        d = day or date.today().isoformat()
        self._day_requests[d] = self._day_requests.get(d, 0) + 1

    def daily_limit_hit(self, day: str | None = None) -> bool:
        """达到/超过单日限额返回 True"""
        limit = int(self.s.get("max_per_day", 0) or 0)
        if limit <= 0:
            return False
        d = day or date.today().isoformat()
        return self._day_requests.get(d, 0) >= limit
