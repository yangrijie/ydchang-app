#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源达投顾 APK 应用入口
- 5 屏: chatrooms(文字圈) / messages(消息) / live_rooms(直播间) / videos(视频) / settings(设置)
- 启动时初始化 DB / Collector / LiveRoomCollector / ForegroundCollector
- 首次启动自动导入预装历史数据 (assets/ydchang_history.db)
"""
from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager

from services.database import AppDatabase
from services.collector import ChatroomCollector, LiveRoomCollector
from services.foreground_service import ForegroundCollector

from ui.screens.chatrooms_screen import ChatroomsScreen
from ui.screens.messages_screen import MessagesScreen
from ui.screens.live_rooms_screen import LiveRoomsScreen
from ui.screens.videos_screen import VideosScreen
from ui.screens.settings_screen import SettingsScreen


class YDChangApp(MDApp):
    """源达投顾 APK 主应用."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None
        self.collector = None
        self.live_collector = None
        self.fg = None

    def build(self):
        # 初始化数据库
        self.db = AppDatabase()

        # 首次启动: 导入预装历史数据
        self._load_history_data()

        # 初始化采集器
        self.collector = ChatroomCollector(self.db)
        self.live_collector = LiveRoomCollector(self.db)
        try:
            interval_str = self.db.get_setting("ydchang.interval_sec") or "60"
            interval = int(interval_str)
        except Exception:
            interval = 60
        self.fg = ForegroundCollector(self.collector, interval_sec=interval)

        # 主题
        self.theme_cls.material_style = "M3"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Indigo"
        self.theme_cls.theme_style = "Light"

        # 路由: 5 个屏幕
        sm = MDScreenManager()
        sm.add_widget(ChatroomsScreen(name="chatrooms"))
        sm.add_widget(MessagesScreen(name="messages"))
        sm.add_widget(LiveRoomsScreen(name="live_rooms"))
        sm.add_widget(VideosScreen(name="videos"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def _load_history_data(self):
        """首次启动时导入预装历史数据."""
        if self.db.is_history_loaded():
            return
        history_path = os.path.join(SCRIPT_DIR, "assets", "ydchang_history.db")
        if not os.path.exists(history_path):
            # Android 打包后, assets 在 app 目录下
            try:
                from kivy.app import App
                app = App.get_running_app()
                if app:
                    history_path = os.path.join(
                        app.directory, "assets", "ydchang_history.db"
                    )
            except Exception:
                pass
        if os.path.exists(history_path):
            print(f"[App] 导入预装历史数据: {history_path}")
            stats = self.db.import_history_db(history_path)
            print(f"[App] 导入完成: {stats}")
        else:
            print(f"[App] 未找到预装数据: {history_path}")

    def on_start(self):
        print(f"[App] 启动完成, DB: {self.db.db_path}")
        print(f"  文字圈: {self.db.count_chatrooms()} 个, 消息: {self.db.count_msgs()} 条")
        print(f"  直播间: {self.db.count_rooms()} 个, 视频: {self.db.count_videos()} 个")
        return super().on_start()

    def on_stop(self):
        if self.fg and self.fg.is_running():
            self.fg.stop()
        return super().on_stop()


if __name__ == "__main__":
    YDChangApp().run()
