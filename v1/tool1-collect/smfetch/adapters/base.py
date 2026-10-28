# -*- coding: utf-8 -*-
"""平台适配器抽象接口 (v1 仅实现 douyin, 接口预留多平台)"""
from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    platform: str = "base"

    @abstractmethod
    def login(self, timeout_s: int = 300) -> bool:
        """登录 (返回是否成功)"""

    @abstractmethod
    def resolve(self, target: str) -> str:
        """短链或ID → 平台 item_id"""

    @abstractmethod
    def fetch_video(self, item_id: str) -> dict:
        """抓视频主数据 (返回原始 aweme dict)"""

    @abstractmethod
    def fetch_comments(self, item_id: str) -> dict:
        """抓评论+回复, 返回 {"comments": {cid: item}, "collected": n}"""

    @abstractmethod
    def download_video(self, item_id: str, aweme: dict, dest: Path) -> bool:
        """下载无水印视频到 dest"""
