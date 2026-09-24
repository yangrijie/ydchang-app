#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页 - Token / 监听 房间 IDs / 采集间隔 / 启停前台服务"""
from __future__ import annotations

from kivy.core.window import Window
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar


class SettingsScreen(MDScreen):
    """设置页: Token / watch_ids / 采集间隔 / 启停前台服务."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.dialog = None
        self._build_ui()

    # ── UI 构建 ────────────────────────────────────────
    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        # 顶栏
        top_bar = MDTopAppBar(
            title="设置",
            left_action_items=[["menu", self.on_open_nav]],
            right_action_items=[["refresh", self.on_refresh]],
        )
        root.add_widget(top_bar)

        # 滚动内容
        from kivymd.uix.scrollview import MDScrollView

        scroll = MDScrollView()
        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=dp(16),
            spacing=dp(12),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        root.add_widget(scroll)

        # Token 输入
        token = self.app.db.get_setting("ydchang.token") or ""
        self.token_field = MDTextField(
            text=token,
            hint_text="Bearer Token (UUID 格式)",
            helper_text="登录源达文字圈 API 用,需定期更新",
            helper_text_mode="on_focus",
            multiline=False,
            size_hint_x=1,
        )
        content.add_widget(self._wrap_in_card(self.token_field))

        # 监听 房间 IDs
        watch_ids = self.app.db.get_setting("ydchang.chatroom.watch_ids") or "74"
        self.ids_field = MDTextField(
            text=watch_ids,
            hint_text="监听房间 IDs (逗号分隔)",
            helper_text="例如: 74,75,76",
            helper_text_mode="on_focus",
            multiline=False,
            size_hint_x=1,
        )
        content.add_widget(self._wrap_in_card(self.ids_field))

        # 采集间隔
        interval = self.app.db.get_setting("ydchang.interval_sec") or "60"
        self.interval_field = MDTextField(
            text=interval,
            hint_text="采集间隔 (秒)",
            helper_text="默认 60 秒,前台服务循环间隔",
            helper_text_mode="on_focus",
            multiline=False,
            size_hint_x=1,
            input_filter="int",
        )
        content.add_widget(self._wrap_in_card(self.interval_field))

        # 启停按钮 + 状态
        self.status_label = MDLabel(
            text=self._status_text(),
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(28),
        )
        content.add_widget(self._wrap_in_card(self.status_label))

        # Token 状态检测
        self.token_status_label = MDLabel(
            text="Token 状态: 未检测",
            theme_text_color="Secondary",
            size_hint_y=None,
            height=dp(28),
        )
        content.add_widget(self._wrap_in_card(self.token_status_label))

        token_check_row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
        )
        self.check_token_btn = MDRaisedButton(
            text="检测 Token 有效性",
            on_release=self.on_check_token,
            size_hint_x=0.6,
        )
        token_check_row.add_widget(self.check_token_btn)

        # 增量采集直播间按钮
        self.sync_live_btn = MDRaisedButton(
            text="采集直播间",
            on_release=self.on_sync_live,
            size_hint_x=0.4,
        )
        token_check_row.add_widget(self.sync_live_btn)
        content.add_widget(token_check_row)

        self.start_btn = MDRaisedButton(
            text="启动前台采集" if not self.app.fg.is_running() else "停止前台采集",
            on_release=self.on_toggle_service,
        )
        content.add_widget(self.start_btn)

        # 手动采集一次按钮
        self.collect_btn = MDRaisedButton(
            text="立即采集一次",
            on_release=self.on_collect_once,
        )
        content.add_widget(self.collect_btn)

        # 保存按钮
        save_btn = MDRaisedButton(
            text="保存设置",
            on_release=self.on_save,
        )
        content.add_widget(save_btn)

        self.add_widget(root)

    def _wrap_in_card(self, widget):
        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            elevation=1,
            radius=[dp(8)],
        )
        card.bind(minimum_height=card.setter("height"))
        card.add_widget(widget)
        return card

    def _status_text(self) -> str:
        fg = self.app.fg
        st = fg.status()
        if not st["running"]:
            return "前台服务: 已停止"
        last = st.get("last_run_time") or "(尚未运行)"
        stats = st.get("last_run_stats")
        stats_str = (
            f"新增 {stats['new']} 条 / 跳过 {stats['skipped']} 条"
            if stats
            else "无"
        )
        return (
            f"前台服务: 运行中 | 间隔 {st['interval']}s\n"
            f"上次采集: {last}\n"
            f"{stats_str}"
        )

    # ── 事件 ──────────────────────────────────────────
    def on_open_nav(self, *args):
        """导航菜单: 切换到其它主页面."""
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
                    text="视频",
                    on_release=lambda *_: self._navigate_to("videos", dialog),
                ),
            ],
        )
        dialog.open()

    def _navigate_to(self, screen_name, dialog):
        dialog.dismiss()
        self.app.root.current = screen_name

    def on_refresh(self, *args):
        self.token_field.text = (
            self.app.db.get_setting("ydchang.token") or ""
        )
        self.ids_field.text = (
            self.app.db.get_setting("ydchang.chatroom.watch_ids") or "74"
        )
        self.interval_field.text = (
            self.app.db.get_setting("ydchang.interval_sec") or "60"
        )
        self._refresh_status()

    def on_save(self, *args):
        token = self.token_field.text.strip()
        ids = self.ids_field.text.strip() or "74"
        interval = int(self.interval_field.text.strip() or "60")

        self.app.db.set_setting("ydchang.token", token)
        self.app.db.set_setting("ydchang.chatroom.watch_ids", ids)
        self.app.db.set_setting("ydchang.interval_sec", str(interval))

        # 通知采集器更新 token,并更新间隔
        self.app.collector.reload_token(token)
        self.app.fg.interval = interval

        self._show_dialog("已保存", f"Token: {token[:8]}****\n监听: {ids}\n间隔: {interval}s")

    def on_toggle_service(self, *args):
        if self.app.fg.is_running():
            self.app.fg.stop()
        else:
            # 先读取 interval 再启动
            try:
                interval = int(self.interval_field.text.strip() or "60")
            except ValueError:
                interval = 60
            self.app.fg.interval = interval
            self.app.fg.start()
        self._refresh_status()

    def on_collect_once(self, *args):
        """手动触发一次采集."""
        # 异步: 启动临时线程
        import threading

        def _run():
            stats = self.app.collector.run_once()
            msg = (
                f"新增 {stats['new']} 条 / 跳过 {stats['skipped']} 条"
                f" / 错误 {stats['errors']} 条"
            )
            # 通过 Clock 回到主线程
            from kivy.clock import Clock

            Clock.schedule_once(lambda dt: self._show_dialog("采集完成", msg), 0)

        threading.Thread(target=_run, daemon=True).start()
        self._show_dialog("采集中", "请稍候...")

    def on_check_token(self, *args):
        """检测 Token 是否过期."""
        import threading

        def _run():
            status = self.app.collector.check_token_status()
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self._update_token_status(status), 0)

        threading.Thread(target=_run, daemon=True).start()
        self.token_status_label.text = "Token 状态: 检测中..."

    def _update_token_status(self, status):
        valid = status.get("valid")
        detail = status.get("detail", "")
        if valid is True:
            self.token_status_label.text = f"Token 状态: [color=00C853]有效[/color]\n{detail}"
            self.token_status_label.markup = True
        elif valid is False:
            self.token_status_label.text = (
                f"Token 状态: [color=FF1744]已过期[/color]\n{detail}\n"
                "请更新 Token 后保存!"
            )
            self.token_status_label.markup = True
            self._show_dialog("Token 已过期", f"{detail}\n\n请在上方输入新 Token 并点击保存。")
        else:
            self.token_status_label.text = f"Token 状态: [color=FF9100]检测失败[/color]\n{detail}"
            self.token_status_label.markup = True

    def on_sync_live(self, *args):
        """增量采集直播间 + 视频."""
        import threading

        def _run():
            stats = self.app.live_collector.run_increment(scan_range=20)
            msg = (
                f"新增直播间: {stats['new_rooms']}\n"
                f"新增视频: {stats['new_videos']}\n"
                f"刷新视频: {stats['refreshed_videos']}"
            )
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self._show_dialog("直播间采集完成", msg), 0)

        threading.Thread(target=_run, daemon=True).start()
        self._show_dialog("采集中", "正在增量采集直播间...")

    # ── 工具 ──────────────────────────────────────────
    def _refresh_status(self):
        self.status_label.text = self._status_text()
        running = self.app.fg.is_running()
        self.start_btn.text = "停止前台采集" if running else "启动前台采集"

    def _show_dialog(self, title: str, body: str):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None
        self.dialog = MDDialog(
            title=title,
            text=body,
            buttons=[
                MDFlatButton(
                    text="好的",
                    on_release=lambda *_: self.dialog.dismiss(),
                ),
            ],
        )
        self.dialog.open()

    def on_pre_enter(self, *args):
        # 切换到本页时刷新设置回显
        self.on_refresh()
