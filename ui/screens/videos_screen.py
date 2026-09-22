#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频列表页 - 直播间回放视频"""
from __future__ import annotations

from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar


class VideosScreen(MDScreen):
    """视频列表页 - 展示直播间回放视频."""

    room_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        self.top_bar = MDTopAppBar(
            title="回放视频",
            left_action_item=[["arrow-left", self.on_back]],
            right_action_item=[["refresh", self.on_refresh]],
        )
        root.add_widget(self.top_bar)

        self.scroll = MDScrollView()
        self.list_container = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(8),
            spacing=dp(6),
        )
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        self.scroll.add_widget(self.list_container)
        root.add_widget(self.scroll)

        self.footer = MDLabel(
            text="加载中...",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(24),
            padding=(dp(16), 0),
        )
        root.add_widget(self.footer)

        self.add_widget(root)

    def on_back(self, *args):
        self.app.root.current = "live_rooms"

    def on_refresh(self, *args):
        if self.room_id:
            import threading

            def _run():
                self.app.live_collector.run_refresh()
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.reload(), 0)

            threading.Thread(target=_run, daemon=True).start()
            self.footer.text = "刷新中..."
        else:
            self.reload()

    def on_pre_enter(self, *args):
        self.reload()

    def reload(self):
        self.list_container.clear_widgets()
        if not self.room_id:
            # 显示全部视频
            videos = self.app.db.list_videos(limit=200)
            self.top_bar.title = "全部回放视频"
        else:
            videos = self.app.db.list_videos(self.room_id, limit=200)
            room = self.app.db.get_room_by_id(self.room_id)
            rname = room.get("room_name") if room else f"直播间 {self.room_id}"
            self.top_bar.title = f"{rname} - 回放"

        if not videos:
            self.footer.text = "无视频数据"
            return

        for v in videos:
            item = self._build_video_item(v)
            self.list_container.add_widget(item)

        self.footer.text = f"共 {len(videos)} 个视频"

    def _build_video_item(self, v: dict):
        card = MDCard(
            orientation="vertical",
            padding=dp(10),
            size_hint_y=None,
            elevation=1,
            radius=[dp(8)],
        )
        card.bind(minimum_height=card.setter("height"))

        title = v.get("title") or "(无标题)"
        dur = v.get("duration")
        dur_text = f"时长 {int(dur)}秒" if dur else ""
        start = v.get("start_time_text") or "-"

        head = MDLabel(
            text=f"[b]{title}[/b]",
            markup=True,
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(24),
            font_style="Body1",
        )

        meta = MDLabel(
            text=f"开播: {start}  {dur_text}",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(20),
            font_style="Caption",
        )

        # 视频链接
        file_url = v.get("file_url")
        if file_url:
            url_label = MDLabel(
                text=f"[ref={file_url}]点击播放视频[/ref]",
                markup=True,
                theme_text_color="Primary",
                size_hint_y=None,
                height=dp(20),
                font_style="Caption",
            )
            url_label.bind(on_ref_press=self._on_ref_press)
            card.add_widget(head)
            card.add_widget(meta)
            card.add_widget(url_label)
        else:
            card.add_widget(head)
            card.add_widget(meta)
        return card

    def _on_ref_press(self, instance, ref):
        try:
            import webbrowser
            webbrowser.open(ref)
        except Exception as e:
            print(f"[VIDEO] 打开链接失败: {e}")
