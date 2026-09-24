#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源达投顾 APK 应用入口
- 5 屏: chatrooms(文字圈) / messages(消息) / live_rooms(直播间) / videos(视频) / settings(设置)
- 启动时初始化 DB / Collector / LiveRoomCollector / ForegroundCollector
- 首次启动自动导入预装历史数据 (assets/ydchang_history.db)

崩溃诊断(临时): 启动/运行期的异常与原生崩溃都会写入
  手机 -> 内部存储/Android/data/org.ydchang.app/files/ydchang_crash.log
(USB 连接电脑后可在该路径下取到, 也可用 adb 从私有目录 logs/ 下取)
"""
from __future__ import annotations

import datetime
import faulthandler
import os
import sys
import traceback

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


# ──────────────────────────────────────────────────────────────────────
# 崩溃诊断
# ──────────────────────────────────────────────────────────────────────
def _resolve_log_path() -> str:
    """选一个手机侧可访问的日志路径."""
    candidates = []
    # 1) Android 应用外部私有目录 (USB/MTP 可见)
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        if activity is not None:
            d = activity.getExternalFilesDir(None)
            if d is not None:
                candidates.append(os.path.join(str(d.getAbsolutePath()),
                                               "ydchang_crash.log"))
    except Exception:
        pass
    # 2) 环境变量兜底
    for key in ("ANDROID_PUBLIC", "EXTERNAL_STORAGE"):
        v = os.environ.get(key)
        if v:
            candidates.append(os.path.join(
                v, "Android", "data", "org.ydchang.app", "files",
                "ydchang_crash.log"))
    # 3) 应用私有目录 (需 adb 才能取)
    candidates.append(os.path.join(SCRIPT_DIR, "ydchang_crash.log"))

    for p in candidates:
        try:
            d = os.path.dirname(p)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(p, "a", encoding="utf-8"):
                pass
            return p
        except Exception:
            continue
    return os.path.join(SCRIPT_DIR, "ydchang_crash.log")


LOG_FILE = _resolve_log_path()
_fh_bin = None


def _log(msg: str) -> None:
    line = "[%s] %s\n" % (datetime.datetime.now().isoformat(), msg)
    try:
        sys.stderr.write(line)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _disable_kivymd_elevation():
    """禁用 KivyMD 控件的阴影(elevation).

    KivyMD 1.1.1 的阴影是用自定义 RenderContext + 手写 GLSL 实现的
    (kivymd/uix/behaviors/elevation.py: context.shader.fs = ...)。
    这套 shader 与 Kivy 2.2+ 重写后的图形栈不兼容: 首次绘制时会在
    RenderContext.draw() 里触发原生段错误(SIGSEGV), 表现为 App 启动后
    立刻闪退。这里去掉阴影, 只保留控件本体。
    注: 其它方法都自带 hasattr(self, "rect") 保护, 所以不创建阴影对象是安全的。
    """
    try:
        from kivymd.uix.behaviors import elevation as _elev
    except Exception:
        _log("elevation patch: import failed\n" + traceback.format_exc())
        return

    base = getattr(_elev, "CommonElevationBehavior", None)
    if base is None:
        _log("elevation patch: CommonElevationBehavior not found")
        return

    def _patched_init(self, **kwargs):
        # 只做基类初始化, 不创建 RenderContext / 阴影矩形 / 自定义 shader,
        # 也不再 Window.bind(on_draw=...)
        super(base, self).__init__(**kwargs)

    base.__init__ = _patched_init

    for _name in ("set_shader_string", "get_shader_string", "update_resolution",
                  "on_shadow_color", "on_shadow_radius", "on_shadow_softness",
                  "on_elevation", "on_shadow_offset", "on_pos", "on_size",
                  "on_opacity", "on_radius", "on_disabled"):
        if hasattr(base, _name):
            setattr(base, _name, lambda self, *a, **k: None)

    if hasattr(base, "hide_elevation"):
        base.hide_elevation = lambda self, hide: None

    _log("kivymd elevation disabled (Kivy 2.2+ GLSL shadow incompatibility)")


# faulthandler: 段错误/原生崩溃
try:
    _fh_bin = open(LOG_FILE, "ab")
    faulthandler.enable(_fh_bin)
    _log("faulthandler enabled")
except Exception as _e:
    _log("faulthandler enable failed: %r" % (_e,))


# 未捕获异常
def _excepthook(exc_type, exc, tb):
    _log("!!! UNCAUGHT EXCEPTION !!!\n" + "".join(
        traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _excepthook

try:
    import threading

    def _thread_excepthook(args):
        _log("!!! UNCAUGHT THREAD EXCEPTION (%s) !!!\n" % (
            getattr(args.thread, "name", "?"),) + "".join(
            traceback.format_exception(args.exc_type, args.exc_value,
                                       args.exc_traceback)))

    threading.excepthook = _thread_excepthook
except Exception:
    pass


_log("=" * 60)
_log("App start: log=%s" % LOG_FILE)
_log("python=%s argv=%s" % (sys.version.split()[0], sys.argv))
_log("cwd=%s script_dir=%s" % (os.getcwd(), SCRIPT_DIR))


# ── 导入阶段单独捕获 (定位 import 期崩溃) ─────────────────────────────
try:
    from kivymd.app import MDApp
    from kivymd.uix.label import MDLabel
    from kivymd.uix.screen import MDScreen
    from kivymd.uix.screenmanager import MDScreenManager

    from services.database import AppDatabase
    from services.collector import ChatroomCollector, LiveRoomCollector
    from services.foreground_service import ForegroundCollector

    from ui.screens.chatrooms_screen import ChatroomsScreen
    from ui.screens.messages_screen import MessagesScreen
    from ui.screens.live_rooms_screen import LiveRoomsScreen
    from ui.screens.videos_screen import VideosScreen
    from ui.screens.settings_screen import SettingsScreen

    _log("all imports OK")
except BaseException:
    _log("!!! IMPORT FAILURE !!!\n" + traceback.format_exc())
    raise

# 必须在任何 KivyMD 控件实例化之前禁用阴影, 否则渲染时段错误
_disable_kivymd_elevation()


def _install_cjk_font():
    """替换默认字体, 让中文能正常显示.

    Kivy/KivyMD 默认字体 Roboto 不含中文字形, 中文会渲染成方框(tofu).
    这里优先使用打包进 APK 的 NotoSansSC 字体, 其次尝试 Android 系统自带的
    中文字体. 注册时覆盖 KivyMD 用到的所有字体名(Roboto*).
    """
    try:
        from kivy.core.text import LabelBase
    except Exception:
        _log("CJK font: LabelBase import failed\n" + traceback.format_exc())
        return

    candidates = [
        os.path.join(SCRIPT_DIR, "assets", "NotoSansSC-Regular.otf"),
        "/system/fonts/NotoSansSC-Regular.otf",
        "/system/fonts/NotoSansCJKsc-Regular.otf",
        "/system/fonts/DroidSansFallbackFull.ttf",
        "/system/fonts/DroidSansFallback.ttf",
        "/system/fonts/MiSans-Regular.ttf",
        "/system/fonts/HarmonyOS_Sans_SC_Regular.ttf",
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansCJKsc-Regular.ttc",
    ]
    chosen = None
    for path in candidates:
        if os.path.isfile(path):
            chosen = path
            break
    if not chosen:
        _log("CJK font: no candidate found -> Chinese may render as boxes")
        return

    names = ("Roboto", "RobotoBold", "RobotoLight", "RobotoMedium",
             "RobotoThin", "RobotoBlack", "RobotoItalic", "RobotoBoldItalic",
             "RobotoLightItalic", "RobotoMediumItalic", "RobotoThinItalic",
             "RobotoBlackItalic")
    ok = 0
    for name in names:
        try:
            LabelBase.register(name=name, fn_regular=chosen)
            ok += 1
        except Exception:
            pass
    _log("CJK font: %s registered for %d font names" % (chosen, ok))


_install_cjk_font()


# 尽早把 Kivy 自身日志接入同一文件 (覆盖窗口/主循环初始化阶段)
try:
    import logging
    from kivy.logger import Logger
    _kivy_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _kivy_fh.setLevel(logging.DEBUG)
    Logger.addHandler(_kivy_fh)
    _log("kivy logger attached")
except Exception as _e:
    _log("attach kivy logger failed: %r" % (_e,))


class YDChangApp(MDApp):
    """源达投顾 APK 主应用."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None
        self.collector = None
        self.live_collector = None
        self.fg = None

    def build(self):
        try:
            _log("build(): init database")
            self.db = AppDatabase()

            _log("build(): load history data")
            self._load_history_data()

            _log("build(): init collectors")
            self.collector = ChatroomCollector(self.db)
            self.live_collector = LiveRoomCollector(self.db)
            try:
                interval_str = self.db.get_setting("ydchang.interval_sec") or "60"
                interval = int(interval_str)
            except Exception:
                interval = 60
            self.fg = ForegroundCollector(self.collector, interval_sec=interval)

            _log("build(): theme")
            self.theme_cls.material_style = "M3"
            self.theme_cls.primary_palette = "Blue"
            self.theme_cls.accent_palette = "Indigo"
            self.theme_cls.theme_style = "Light"

            _log("build(): screens")
            sm = MDScreenManager()
            screen_defs = (
                ("chatrooms", ChatroomsScreen),
                ("messages", MessagesScreen),
                ("live_rooms", LiveRoomsScreen),
                ("videos", VideosScreen),
                ("settings", SettingsScreen),
            )
            for screen_name, screen_cls in screen_defs:
                try:
                    sm.add_widget(screen_cls(name=screen_name))
                except BaseException:
                    # 单个页面初始化失败时降级为占位页, 保证其余页面仍可用,
                    # 并把完整 traceback 写进日志(便于一次性定位所有问题).
                    _log("!!! screen '%s' FAILED !!!\n%s" % (
                        screen_name, traceback.format_exc()))
                    placeholder = MDScreen(name=screen_name)
                    placeholder.add_widget(MDLabel(
                        text="页面 [%s] 初始化失败" % screen_name,
                        halign="center"))
                    sm.add_widget(placeholder)
            _log("build(): done")
            return sm
        except BaseException:
            _log("!!! build() FAILURE !!!\n" + traceback.format_exc())
            raise

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
            _log("import history db: %s" % history_path)
            stats = self.db.import_history_db(history_path)
            _log("history import done: %s" % (stats,))
        else:
            _log("history db not found: %s" % history_path)

    def on_start(self):
        try:
            _log("on_start: db=%s" % self.db.db_path)
            _log("on_start: chatrooms=%d msgs=%d rooms=%d videos=%d" % (
                self.db.count_chatrooms(), self.db.count_msgs(),
                self.db.count_rooms(), self.db.count_videos()))
        except Exception:
            _log("on_start log failed:\n" + traceback.format_exc())
        return super().on_start()

    def on_stop(self):
        try:
            if self.fg and self.fg.is_running():
                self.fg.stop()
        except Exception:
            pass
        return super().on_stop()


if __name__ == "__main__":
    try:
        _log("calling YDChangApp().run()")
        YDChangApp().run()
        _log("run() returned normally")
    except BaseException:
        _log("!!! run() FAILURE !!!\n" + traceback.format_exc())
        raise
