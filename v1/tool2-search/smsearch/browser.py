# -*- coding: utf-8 -*-
"""浏览器连接: 一律复用常驻浏览器 (A1 方案), 不自行启动/关闭"""
from . import service


def connect():
    """连接常驻浏览器, 返回 (ctx, page)。
    注意: 调用方不要 close —— 常驻浏览器由 `smsearch browser stop` 显式关闭。"""
    _p, _b, ctx, page = service.connect()
    return ctx, page
