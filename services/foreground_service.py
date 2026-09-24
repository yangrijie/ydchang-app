#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前台服务 (Foreground Service) - 让 APK 锁屏时仍能持续采集数据

分级调度(三个周期都可在"参数设置"页修改, 改完无需重启服务):
  - 重要文字圈  : 默认 30 秒一次, 只抓"重要房间 IDs"里配置的房间
  - 其他文字圈  : 默认 60 秒一次
  - 直播间+视频 : 默认 600 秒(10 分钟)增量采集一次

实现策略:
  1. 在 Android 上,通过 jnius 调用 Android Service API 启动前台服务,
     显示一个持续通知 (Notification),使应用进程不会被系统在锁屏时杀掉.
  2. 在 service 内部起一个后台线程, 每 TICK_SEC 秒检查一次, 各任务按自己的
     周期到点执行 (这样 30 秒的任务不会被 60 秒的任务拖慢).
  3. 桌面调试环境 (Windows/Mac) 自动降级为普通 threading.Thread
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

# 调度器的最小检查粒度(秒)
TICK_SEC = 5


class ForegroundCollector:
    """前台采集服务(分级调度).

    - start(): 启动采集线程 (并尝试启动 Android 前台 Service)
    - stop(): 停止采集线程
    - status(): 返回运行状态
    """

    DEFAULT_INTERVAL_SEC = 60        # 其他文字圈
    DEFAULT_VIP_INTERVAL_SEC = 30    # 重要文字圈
    DEFAULT_LIVE_INTERVAL_SEC = 600  # 直播间 + 视频

    def __init__(self, collector, live_collector=None, interval_sec=None,
                 vip_interval_sec=None, live_interval_sec=None):
        self.collector = collector
        self.live_collector = live_collector
        self.interval = interval_sec or self.DEFAULT_INTERVAL_SEC
        self.vip_interval = vip_interval_sec or self.DEFAULT_VIP_INTERVAL_SEC
        self.live_interval = live_interval_sec or self.DEFAULT_LIVE_INTERVAL_SEC

        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_run_stats = None
        self._last_run_time = None
        self._last_live_stats = None
        self._last_live_time = None
        self._error_count = 0

    # ── 配置读取(每轮重新读取, 改设置后无需重启) ─────────
    def _setting(self, key, default=None):
        try:
            db = getattr(self.collector, "db", None)
            if db is None:
                return default
            return db.get_setting(key)
        except Exception:
            return default

    def _int_setting(self, key, default):
        raw = self._setting(key)
        try:
            val = int(str(raw).strip())
            return val if val > 0 else default
        except Exception:
            return default

    def refresh_config(self):
        """从数据库重新读取三个采集间隔."""
        self.interval = self._int_setting(
            "ydchang.interval_sec", self.DEFAULT_INTERVAL_SEC)
        self.vip_interval = self._int_setting(
            "ydchang.vip_interval_sec", self.DEFAULT_VIP_INTERVAL_SEC)
        self.live_interval = self._int_setting(
            "ydchang.live_interval_sec", self.DEFAULT_LIVE_INTERVAL_SEC)

    def _parse_ids(self, key, default=""):
        raw = self._setting(key) or default
        return [int(x) for x in str(raw).split(",") if x.strip().isdigit()]

    def _watch_ids(self):
        return self._parse_ids("ydchang.chatroom.watch_ids", "74")

    def _vip_ids(self):
        return self._parse_ids("ydchang.chatroom.vip_ids", "")

    def _normal_ids(self):
        """监听房间里去掉重要房间后剩下的."""
        vip = set(self._vip_ids())
        return [rid for rid in self._watch_ids() if rid not in vip]

    # ── 控制 ────────────────────────────────────────────
    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self.refresh_config()
        try:
            self._start_android_service()
        except Exception as e:
            print(f"[FG] Android service 启动失败(可能是桌面调试): {e}")
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
            "vip_interval": self.vip_interval,
            "live_interval": self.live_interval,
            "last_run_time": self._last_run_time,
            "last_run_stats": self._last_run_stats,
            "last_live_time": self._last_live_time,
            "last_live_stats": self._last_live_stats,
            "error_count": self._error_count,
        }

    # ── 内部循环 ────────────────────────────────────────
    def _loop(self):
        """分级调度主循环: 每个任务按自己的周期到点执行."""
        next_vip = 0.0
        next_normal = 0.0
        next_live = 0.0

        while not self._stop_event.is_set():
            now = time.time()
            self.refresh_config()
            try:
                # 1) 重要文字圈
                if now >= next_vip:
                    ids = self._vip_ids()
                    if ids:
                        print(f"[FG] {datetime.now()} 采集重要文字圈 {ids} ...")
                        stats = self.collector.run_msgs(ids=ids)
                        self._last_run_stats = stats
                        self._last_run_time = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S")
                        print(f"[FG] 重要文字圈采集完成: {stats}")
                    next_vip = now + self.vip_interval

                # 2) 其他文字圈
                if now >= next_normal:
                    ids = self._normal_ids()
                    if ids:
                        print(f"[FG] {datetime.now()} 采集其他文字圈 "
                              f"{len(ids)} 个 ...")
                        stats = self.collector.run_msgs(ids=ids)
                        self._last_run_stats = stats
                        self._last_run_time = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S")
                        print(f"[FG] 其他文字圈采集完成: {stats}")
                    next_normal = now + self.interval

                # 3) 直播间 + 视频
                if self.live_collector is not None and now >= next_live:
                    print(f"[FG] {datetime.now()} 采集直播间/视频 ...")
                    stats = self.live_collector.run_increment(scan_range=20)
                    self._last_live_stats = stats
                    self._last_live_time = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S")
                    print(f"[FG] 直播间/视频采集完成: {stats}")
                    next_live = now + self.live_interval

            except Exception as e:
                self._error_count += 1
                print(f"[FG] 采集异常: {type(e).__name__}: {e}")

            self._stop_event.wait(TICK_SEC)

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
            if not hasattr(PythonService, "mService"):
                return
            print("[FG] Android foreground service 调用")
        except ImportError:
            return

    def _stop_android_service(self):
        try:
            from jnius import autoclass  # type: ignore

            PythonService = autoclass("org.kivy.android.PythonService")
        except ImportError:
            return
