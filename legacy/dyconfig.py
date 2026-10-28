# -*- coding: utf-8 -*-
"""集中配置: 路径与常量"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
PROFILE = ROOT / ".profile"          # 浏览器持久化登录态(请只用小号登录)
CACHE = ROOT / ".cache"
VIDEO_DIR = OUT / "videos"
JSON_DIR = OUT / "json"
SUBTITLE_DIR = OUT / "subtitles"

# 目标视频短链 (你提供的那条)
SHORT_URL = "https://v.douyin.com/c2lpyv0fzpk/"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 抓取上限与节奏 (防封参数, 安全优先, 宁可慢不可快)
MAX_SCROLLS = 25          # 单次会话滚动次数上限(安全上限, 不贪多)
MAX_COMMENTS = 2000       # 评论上限
SCROLL_WAIT = (6, 12)     # 每轮之间等待秒数(随机)
REPLY_WAIT = (3, 6)       # 点击展开回复后等待秒数(随机)
PAUSE_EVERY = 5           # 每N轮做一次"阅读停顿"
PAUSE_LONG = (15, 25)     # 阅读停顿秒数(随机)
STALL_LIMIT = 5           # 连续N轮无新增即停止
DETAIL_WAIT = 120         # 等待详情接口最长秒数(期间可处理验证码)

for d in (OUT, PROFILE, VIDEO_DIR, JSON_DIR, SUBTITLE_DIR):
    d.mkdir(parents=True, exist_ok=True)
