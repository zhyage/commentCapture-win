# -*- coding: utf-8 -*-
"""
阶段1: 登录 (只需要你做一次)
用法: python step1_login.py
操作: 会弹出一个浏览器窗口 -> 请用【小号】的抖音App扫码登录 -> 成功后自动保存登录态并退出
"""
import time

from dy_browser import launch


def main():
    p, ctx, page = launch(headless=False)
    page.goto("https://www.douyin.com/", timeout=90000, wait_until="domcontentloaded")
    print("=" * 60)
    print(">> 请在弹出的浏览器窗口中, 用【小号】抖音App扫码登录")
    print(">> (重要: 不要用你日常使用的主号)")
    print(">> 检测到登录成功后, 本脚本会自动关闭窗口")
    print("=" * 60)

    deadline = time.time() + 300   # 5 分钟超时
    logged_in = False
    while time.time() < deadline:
        cookies = ctx.cookies()
        if any(c["name"] in ("sessionid", "sessionid_ss") for c in cookies):
            logged_in = True
            break
        time.sleep(3)

    if logged_in:
        print(">> 登录成功! 登录态已保存到 .profile 目录")
    else:
        print(">> 5分钟内未检测到登录, 已退出。可重新运行本脚本再试。")

    ctx.close()
    p.stop()


if __name__ == "__main__":
    main()
