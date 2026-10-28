# -*- coding: utf-8 -*-
"""视觉特征模块纯逻辑测试 (不依赖视频文件)"""
from smfetch.visual import classify_motion


def test_classify_static():
    assert classify_motion(0.05, 0.1) == "static"
    assert classify_motion(0.19, 3.0) == "static"     # 幅度小即静止, 抖动高不改变


def test_classify_pan():
    assert classify_motion(0.8, 0.2) == "pan_tilt"    # 幅度大 + 方向一致
    assert classify_motion(0.5, 0.5) == "pan_tilt"


def test_classify_handheld():
    assert classify_motion(0.8, 1.2) == "handheld"    # 幅度大 + 抖动高
    assert classify_motion(0.3, 0.9) == "handheld"    # 幅度中 + 抖动高
