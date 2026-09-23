#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文字圈列表页"""
from __future__ import annotations

from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar


class ChatroomsScreen(MDScreen):
    """文字圈列表页 - 展示已采集 / 已监听的文字圈."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        self.top_bar = MDTopAppBar(
            title="文字圈列表",
            right_action_item=[["refresh", self.on_refresh]],
            left_action_item=[["menu", self.on_open_nav]],
        )
        root.add_widget(self.top_bar)

        # 模式切换: 全部 / 仅监听
        from kivymd.uix.chip import MDChip

        chip_box = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            padding=dp(8),
            spacing=dp(8),
        )
        self.chip_all = MDChip(
            text="全部",
            active=True,
            on_press=lambda *_: self._switch_mode(False),
        )
        self.chip_watched = MDChip(
            text="仅监听",
            active=False,
            on_press=lambda *_: self._switch_mode(True),
        )
        chip_box.add_widget(self.chip_all)
        chip_box.add_widget(self.chip_watched)
        root.add_widget(chip_box)

        # 列表
        self.scroll = MDScrollView()
        self.list_container = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(8),
            spacing=dp(4),
        )
        self.list_container.bind(minimum_height=self.list_container.setter("height"))
        self.scroll.add_widget(self.list_container)
        root.add_widget(self.scroll)

        # 底部统计
        self.footer = MDLabel(
            text="加载中...",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(24),
            padding=(dp(16), 0),
        )
        root.add_widget(self.footer)

        self.add_widget(root)

    # ── 事件 ──────────────────────────────────────────
    def _switch_mode(self, watched: bool):
        self.chip_all.active = not watched
        self.chip_watched.active = watched
        self._only_watched = watched
        self.reload()

    def on_refresh(self, *args):
        self.reload()

    def on_open_nav(self, *args):
        """导航菜单: 切换到其他主页面."""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        dialog = MDDialog(
            title="导航",
            text="选择页面",
            buttons=[
                MDFlatButton(
                    text="文字圈",
                    on_release=lambda *_: self._navigate_to("chatrooms", dialog),
                ),
                MDFlatButton(
                    text="直播间",
                    on_release=lambda *_: self._navigate_to("live_rooms", dialog),
                ),
                MDFlatButton(
                    text="设置",
                    on_release=lambda *_: self._navigate_to("settings", dialog),
                ),
            ],
        )
        dialog.open()

    def _navigate_to(self, screen_name, dialog):
        dialog.dismiss()
        self.app.root.current = screen_name

    def on_pre_enter(self, *args):
        self.reload()

    def reload(self):
        """重新加载文字圈列表."""
        # 清空
        self.list_container.clear_widgets()
        only_watched = getattr(self, "_only_watched", False)
        rooms = self.app.db.list_chatrooms(only_watched=only_watched)

        if not rooms:
            self.footer.text = "无数据,请先到设置页启动采集"
            return

        for room in rooms:
            item = self._build_room_item(room)
            self.list_container.add_widget(item)

        self.footer.text = (
            f"共 {len(rooms)} 个文字圈"
            + (" (仅监听)" if only_watched else "")
        )

    def _build_room_item(self, room: dict):
        rid = room["id"]
        name = room.get("name") or f"文字圈 {rid}"
        last_content = (room.get("last_msg_content") or "")[:50]
        last_time = room.get("last_msg_time") or "-"
        member = room.get("member_count") or 0

        # 使用卡片更易点击
        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            elevation=1,
            radius=[dp(8)],
            on_release=lambda *x, rid=rid: self._open_detail(rid),
        )
        card.bind(minimum_height=card.setter("height"))

        title_label = MDLabel(
            text=f"[b]{name}[/b]  (id={rid})",
            markup=True,
            theme_text_color="Primary",
            size_hint_y=None,
            font_style="Body1",
        )
        title_label.bind(
            texture_size=title_label.setter("size"),
        )
        # workaround: 让 label 高度自适应
        title_label.height = dp(24)

        msg_label = MDLabel(
            text=last_content or "(无消息)",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(20),
            font_style="Caption",
        )

        meta_label = MDLabel(
            text=f"最新: {last_time} | 成员: {member}",
            theme_text_color="Hint",
            size_hint_y=None,
            height=dp(18),
            font_style="Caption",
        )

        card.add_widget(title_label)
        card.add_widget(msg_label)
        card.add_widget(meta_label)
        return card

    def _open_detail(self, room_id: int):
        # 切换到消息详情页,并传 room_id
        screen_mgr = self.app.root
        messages_screen = screen_mgr.get_screen("messages")
        messages_screen.room_id = room_id
        screen_mgr.current = "messages"
