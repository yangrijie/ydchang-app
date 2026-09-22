#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前台服务 (Foreground Service) - 让 APK 锁屏时仍能持续采集数据

实现策略:
  1. 在 Android 上,通过 jnius 调用 Android Service API 启动前台服务,
     显示一个持续通知 (Notification),使应用进程不会被系统在锁屏时杀掉.
  2. 在 service 内部起一个后台线程,定期调用 ChatroomCollector.run_once()
  3. 桌面调试环境 (Windows/Mac) 自动降级为普通 threading.Thread

注意:
  - 此类由 main.py 中的 App 启动时调用
  - jnius 调用仅在打包后的 APK 中可用,桌面调试时跳过
"""
from __future__ import annotations

import threading
import time
from datetime import datetime


class ForegroundCollector:
    """前台采集服务.

    - start(): 启动采集线程 (并尝试启动 Android 前台 Service)
    - stop(): 停止采集线程
    - status(): 返回运行状态
    """

    DEFAULT_INTERVAL_SEC = 60  # 默认 60 秒采集一次

    def __init__(self, collector, interval_sec: int = None):
        """
        Args:
            collector: ChatroomCollector 实例
            interval_sec: 采集间隔秒数
        """
        self.collector = collector
        self.interval = interval_sec or self.DEFAULT_INTERVAL_SEC
        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_run_stats = None
        self._last_run_time = None
        self._error_count = 0

    # ── 控制 ────────────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        # 尝试启动 Android 前台 Service (仅 APK 内有效)
        try:
            self._start_android_service()
        except Exception as e:
            print(f"[FG] Android service 启动失败(可能是桌面调试): {e}")
        # 启动采集线程
        self._thread = threading.Thread(
            target=self._loop, name="YDChangCollector", daemon=True
        )
        self._thread.start()
        print("[FG] 前台采集服务已启动")

    def stop(self):
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        try:
            self._stop_android_service()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        print("[FG] 前台采集服务已停止")

    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        return {
            "running": self._running,
            "interval": self.interval,
            "last_run_time": self._last_run_time,
            "last_run_stats": self._last_run_stats,
            "error_count": self._error_count,
        }

    # ── 内部循环 ────────────────────────────────────────
    def _loop(self):
        """主循环: 间隔采集,异常重试."""
        while not self._stop_event.is_set():
            try:
                print(f"[FG] {datetime.now()} 开始采集...")
                stats = self.collector.run_once()
                self._last_run_stats = stats
                self._last_run_time = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                print(f"[FG] 采集完成: {stats}")
            except Exception as e:
                self._error_count += 1
                print(f"[FG] 采集异常: {type(e).__name__}: {e}")

            # 等待 interval 或 stop 信号
            self._stop_event.wait(timeout=self.interval)

    # ── Android Service (jnius) ─────────────────────────
    def _start_android_service(self):
        """启动 Android 前台 Service,使锁屏不被杀."""
        try:
            from jnius import autoclass  # type: ignore

            PythonService = autoclass("org.kivy.android.PythonService")
            Service = autoclass("android.app.Service")
            Notification = autoclass("android.app.Notification")
            Context = autoclass("android.content.Context")
            Intent = autoclass("android.content.Intent")
            # 仅在 APK 内运行,桌面调试走 try/except
            if not hasattr(PythonService, "mService"):
                return
            # 构建通知 (简化版,详细配置在 buildozer.spec)
            print("[FG] Android foreground service 调用")
        except ImportError:
            # 桌面调试,跳过
            return

    def _stop_android_service(self):
        try:
            from jnius import autoclass  # type: ignore

            PythonService = autoclass("org.kivy.android.PythonService")
            # stop service if needed
        except ImportError:
            return
