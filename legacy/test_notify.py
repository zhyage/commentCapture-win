# -*- coding: utf-8 -*-
"""发送一条微信测试消息, 验证 Server酱 通道"""
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from notifier import get_notifier  # noqa: E402


def main():
    n = get_notifier()
    title = "✅ 抖音采集工具 - 微信提醒通道测试"
    body = f"""
**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**用途**: 验证无人值守模式下, 工具卡住时能否通知到你。

如果你在微信上看到了这条消息, 说明通道已打通 ✅
后续将用于: 滑块验证码 / 登录过期 / 抓取受阻 等事件的提醒。
"""
    ok = n.send(title, body)
    print("发送结果:", "成功" if ok else "失败")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
