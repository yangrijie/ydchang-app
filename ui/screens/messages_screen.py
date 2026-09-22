#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""消息详情页 - 指定 房间 的最新消息列表."""
from __future__ import annotations

from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.toolbar import MDTopAppBar


class MessagesScreen(MDScreen):
    """消息详情页."""

    # 默认房间 ID, 由列表页传入
    room_id = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self._build_ui()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        self.top_bar = MDTopAppBar(
            title="消息详情",
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
    def on_back(self, *args):
        self.app.root.current = "chatrooms"

    def on_refresh(self, *args):
        # 重新拉一次,先触发采集,再 reload
        if self.room_id:
            import threading

            def _run():
                self.app.collector.run_msgs(ids=[self.room_id])
                # 回主线程刷新
                from kivy.clock import Clock

                Clock.schedule_once(lambda dt: self.reload(), 0)

            threading.Thread(target=_run, daemon=True).start()
            self.footer.text = "采集中..."
        else:
            self.reload()

    def on_pre_enter(self, *args):
        # 进入前重载
        self.reload()

    def reload(self):
        self.list_container.clear_widgets()
        if not self.room_id:
            self.footer.text = "未指定 房间 ID"
            return

        msgs = self.app.db.list_msgs(self.room_id, limit=200)
        if not msgs:
            self.footer.text = (
                f"文字圈 id={self.room_id} 暂无消息,点击右上角刷新"
            )
            # 显示 房间 名称
            rooms = self.app.db.list_chatrooms(only_watched=False)
            for r in rooms:
                if r["id"] == self.room_id:
                    self.top_bar.title = r.get("name") or f"消息详情 id={self.room_id}"
                    break
            return

        # 显示 房间 名称
        rooms = self.app.db.list_chatrooms(only_watched=False)
        for r in rooms:
            if r["id"] == self.room_id:
                self.top_bar.title = r.get("name") or f"消息详情 id={self.room_id}"
                break

        for msg in msgs:
            item = self._build_msg_item(msg)
            self.list_container.add_widget(item)

        self.footer.text = f"共 {len(msgs)} 条消息 (最新 200 条)"

    def _build_msg_item(self, msg: dict):
        card = MDCard(
            orientation="vertical",
            padding=dp(10),
            size_hint_y=None,
            elevation=1,
            radius=[dp(8)],
        )
        card.bind(minimum_height=card.setter("height"))

        sender = msg.get("sender_nickname") or "(系统/未知)"
        msg_time = msg.get("msg_time") or "-"
        content = msg.get("content") or ""

        # 类型标签
        msg_type = msg.get("msg_type")
        type_label = ""
        if msg_type == 0:
            type_label = " [降级]"
        elif msg_type == 3:
            type_label = " [附件]"

        head = MDLabel(
            text=f"[b]{sender}[/b]{type_label}  {msg_time}",
            markup=True,
            theme_text_color="Primary",
            size_hint_y=None,
            font_style="Body1",
        )
        head.bind(texture_size=head.setter("size"))
        head.height = dp(24)

        body = MDLabel(
            text=content,
            theme_text_color="Secondary",
            size_hint_y=None,
            padding=(0, dp(4)),
        )
        body.bind(texture_size=body.setter("size"))
        body.height = max(dp(40), body.texture_size[1] + dp(8))

        # 附件链接
        attachment_url = msg.get("attachment_url")
        if attachment_url:
            att = MDLabel(
                text=f"[ref={attachment_url}]下载附件[/ref]",
                markup=True,
                theme_text_color="Primary",
                size_hint_y=None,
                height=dp(20),
                font_style="Caption",
            )
            att.bind(on_ref_press=self._on_ref_press)
            card.add_widget(head)
            card.add_widget(body)
            card.add_widget(att)
        else:
            card.add_widget(head)
            card.add_widget(body)
        return card

    def _on_ref_press(self, instance, ref):
        """点击附件链接 - 调用系统打开."""
        try:
            import webbrowser

            webbrowser.open(ref)
        except Exception as e:
            print(f"[MSG] 打开附件失败: {e}")
