#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播间列表页 - 源达投顾直播平台"""
from __future__ import annotations

from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar


class LiveRoomsScreen(MDScreen):
    """直播间列表页 - 展示已采集的直播间."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        self.top_bar = MDTopAppBar(
            title="直播间列表",
            left_action_items=[["menu", self.on_open_nav]],
            right_action_items=[["refresh", self.on_refresh]],
        )
        root.add_widget(self.top_bar)

        # 列表
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

        # 底部统计 + 操作按钮
        footer_box = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            padding=dp(8),
            spacing=dp(8),
        )
        self.footer = MDLabel(
            text="加载中...",
            theme_text_color="Hint",
            size_hint_x=0.6,
        )
        footer_box.add_widget(self.footer)

        from kivymd.uix.button import MDRaisedButton
        self.sync_btn = MDRaisedButton(
            text="增量采集",
            on_release=self.on_sync,
            size_hint_x=0.4,
        )
        footer_box.add_widget(self.sync_btn)
        root.add_widget(footer_box)

        self.add_widget(root)

    # ── 事件 ──────────────────────────────────────────
    def on_refresh(self, *args):
        self.reload()

    def on_open_nav(self, *args):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        dialog = MDDialog(
            title="导航",
            text="选择页面",
            buttons=[
                MDFlatButton(text="文字圈",
                    on_release=lambda *_: self._navigate_to("chatrooms", dialog)),
                MDFlatButton(text="直播间",
                    on_release=lambda *_: self._navigate_to("live_rooms", dialog)),
                MDFlatButton(text="视频",
                    on_release=lambda *_: self._navigate_to("videos", dialog)),
                MDFlatButton(text="设置",
                    on_release=lambda *_: self._navigate_to("settings", dialog)),
            ],
        )
        dialog.open()

    def _navigate_to(self, screen_name, dialog):
        dialog.dismiss()
        self.app.root.current = screen_name

    def on_sync(self, *args):
        """增量采集直播间 + 视频."""
        import threading

        def _run():
            stats = self.app.live_collector.run_increment(scan_range=20)
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self._after_sync(stats), 0)

        threading.Thread(target=_run, daemon=True).start()
        self.footer.text = "采集中..."

    def _after_sync(self, stats):
        msg = (
            f"新增直播间: {stats['new_rooms']}\n"
            f"新增视频: {stats['new_videos']}\n"
            f"刷新视频: {stats['refreshed_videos']}"
        )
        self.reload()
        self._show_dialog("增量采集完成", msg)

    def on_pre_enter(self, *args):
        self.reload()

    def reload(self):
        self.list_container.clear_widgets()
        rooms = self.app.db.list_rooms(limit=200)

        if not rooms:
            self.footer.text = "无数据,请在设置页启动采集"
            return

        for room in rooms:
            item = self._build_room_item(room)
            self.list_container.add_widget(item)

        self.footer.text = f"共 {len(rooms)} 个直播间"

    def _build_room_item(self, room: dict):
        rid = room["room_id"]
        name = room.get("room_name") or f"直播间 {rid}"
        anchor = room.get("anchor_nick") or "(未知主播)"
        category = room.get("room_category") or ""
        live_status = room.get("live_status")
        started = room.get("started_at") or "-"

        # 直播状态: 1=直播中, 2=已结束
        if live_status == 1:
            status_text = "[color=00C853]直播中[/color]"
        elif live_status == 2:
            status_text = "[color=9E9E9E]已结束[/color]"
        else:
            status_text = ""

        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            elevation=1,
            radius=[dp(8)],
            on_release=lambda *x, rid=rid: self._open_videos(rid),
        )
        card.bind(minimum_height=card.setter("height"))

        title = MDLabel(
            text=f"[b]{name}[/b]  (id={rid})",
            markup=True,
            theme_text_color="Primary",
            size_hint_y=None,
            height=dp(24),
            font_style="Body1",
        )

        anchor_label = MDLabel(
            text=f"主播: {anchor}" + (f" | {category}" if category else ""),
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(20),
            font_style="Caption",
        )

        meta = MDLabel(
            text=f"开播: {started}  {status_text}",
            markup=True,
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(18),
            font_style="Caption",
        )

        card.add_widget(title)
        card.add_widget(anchor_label)
        card.add_widget(meta)
        return card

    def _open_videos(self, room_id: int):
        screen_mgr = self.app.root
        videos_screen = screen_mgr.get_screen("videos")
        videos_screen.room_id = room_id
        screen_mgr.current = "videos"

    def _show_dialog(self, title, text):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[MDFlatButton(
                text="好的",
                on_release=lambda *_: dialog.dismiss(),
            )],
        )
        dialog.open()
