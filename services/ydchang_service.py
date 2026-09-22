#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YDChangService - Android 前台 Service 入口
- 由 buildozer.spec 的 services 配置注册
- 由 Android 启动,在 main.py 中的 ForegroundCollector 也独立启动一个采集线程
- 这里作为 Android 端的 service 钩子(将来可改为真正调用 jnius 启动 notification)
"""
from __future__ import annotations

# 在 APK 内, 此 service 模块被 python-for-android 加载,
# 可以独立运行一个采集线程, 不依赖 UI
def main():
    import os
    import sys

    # 让 services / ui 在 path 中
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    # 上一级目录(包含 services/ 和 main.py)
    parent = os.path.dirname(SCRIPT_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    from services.database import AppDatabase
    from services.collector import ChatroomCollector
    from services.foreground_service import ForegroundCollector

    db = AppDatabase()
    collector = ChatroomCollector(db)
    try:
        interval_str = db.get_setting("ydchang.interval_sec") or "60"
        interval = int(interval_str)
    except Exception:
        interval = 60

    fg = ForegroundCollector(collector, interval_sec=interval)
    fg.start()
    # 进入等待循环 (service 进程保持运行)
    import time

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        fg.stop()


if __name__ == "__main__":
    main()
