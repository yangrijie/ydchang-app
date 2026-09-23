#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立 SQLite 数据库管理器 (源达投顾文字圈 APK 专用)
- 仅管理 T_ydchang_chatroom / T_ydchang_chatroom_msg 两张表
- token / watch_ids 等配置使用单独的 app_settings 表
- 数据库文件位置:
  - Android: 通过 App.get_running_app().user_data_dir 获取
  - 桌面调试: 当前工作目录
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS T_ydchang_chatroom (
    id INTEGER PRIMARY KEY,
    mch_id TEXT,
    name TEXT,
    type TEXT,
    avatar_url TEXT,
    description TEXT,
    owner_id TEXT,
    last_msg_content TEXT,
    last_msg_time TEXT,
    member_count INTEGER,
    mute_all INTEGER DEFAULT 0,
    risk_warning INTEGER DEFAULT 0,
    risk_warning_text TEXT,
    history_visible_days INTEGER,
    service_end_time TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS T_ydchang_chatroom_msg (
    msg_id TEXT PRIMARY KEY,
    room_id INTEGER,
    sender_nickname TEXT,
    content TEXT,
    msg_type INTEGER,
    msg_time TEXT,
    fetched_at TEXT,
    attachment_url TEXT,
    attachment_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_msg_room_time
    ON T_ydchang_chatroom_msg(room_id, msg_time DESC);

CREATE INDEX IF NOT EXISTS idx_msg_room_id
    ON T_ydchang_chatroom_msg(room_id);

CREATE TABLE IF NOT EXISTS T_ydchang_room (
    room_id INTEGER NOT NULL PRIMARY KEY,
    room_name TEXT,
    room_code TEXT,
    anchor_id TEXT,
    anchor_nick TEXT,
    room_type TEXT,
    room_status TEXT,
    room_category TEXT,
    room_description TEXT,
    room_cover TEXT,
    is_password_protected INTEGER,
    max_viewers INTEGER,
    room_level INTEGER,
    is_recommend INTEGER,
    audit_status TEXT,
    live_time_pre TEXT,
    config TEXT,
    create_by TEXT,
    create_time TEXT,
    update_by TEXT,
    update_time TEXT,
    del_flag TEXT,
    live_id TEXT,
    live_title TEXT,
    live_status INTEGER,
    external_live_id TEXT,
    scheduled_at TEXT,
    started_at TEXT,
    stopped_at TEXT,
    cover_url TEXT,
    notice TEXT,
    pull_rtmp_url TEXT,
    pull_hls_url TEXT,
    pull_flv_url TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS T_ydchang_video (
    record_id TEXT NOT NULL PRIMARY KEY,
    room_id INTEGER NOT NULL,
    title TEXT,
    file_url TEXT,
    domain TEXT,
    stream TEXT,
    app TEXT,
    uri TEXT,
    duration REAL,
    start_time INTEGER,
    stop_time INTEGER,
    start_time_text TEXT,
    stop_time_text TEXT,
    fetched_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_video_room
    ON T_ydchang_video(room_id);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    category TEXT,
    updated_at TEXT
);
"""


class AppDatabase:
    """APK 端 SQLite 操作类,线程安全 (带 lock)."""

    _lock = threading.Lock()

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = self._default_db_path()
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    @staticmethod
    def _default_db_path() -> str:
        """默认数据库路径: 优先使用 Android user_data_dir."""
        try:
            from kivy.app import App  # type: ignore
            app = App.get_running_app()
            if app is not None:
                return os.path.join(app.user_data_dir, "ydchang.db")
        except Exception:
            pass
        return os.path.join(os.getcwd(), "ydchang.db")

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.executescript(SCHEMA_SQL)
                conn.commit()
            finally:
                conn.close()

    # ── Settings ──────────────────────────────────────────
    def get_setting(self, key: str, default: str = None) -> str:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT value FROM app_settings WHERE key=?", (key,)
                ).fetchone()
                return row[0] if row else default
            finally:
                conn.close()

    def set_setting(self, key: str, value: str, category: str = "ydchang"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO app_settings(key,value,category,updated_at) "
                    "VALUES(?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                    "updated_at=excluded.updated_at, category=excluded.category",
                    (key, value, category, ts),
                )
                conn.commit()
            finally:
                conn.close()

    # ── 文字圈列表 ────────────────────────────────────────
    def upsert_chatroom(self, rec: dict) -> bool:
        sql = """
        INSERT INTO T_ydchang_chatroom
            (id, mch_id, name, type, avatar_url, description, owner_id,
             last_msg_content, last_msg_time, member_count, mute_all,
             risk_warning, risk_warning_text, history_visible_days,
             service_end_time, fetched_at)
        VALUES
            (:id, :mch_id, :name, :type, :avatar_url, :description, :owner_id,
             :last_msg_content, :last_msg_time, :member_count, :mute_all,
             :risk_warning, :risk_warning_text, :history_visible_days,
             :service_end_time, :fetched_at)
        ON CONFLICT(id) DO UPDATE SET
            mch_id=excluded.mch_id, name=excluded.name, type=excluded.type,
            avatar_url=excluded.avatar_url, description=excluded.description,
            owner_id=excluded.owner_id,
            last_msg_content=excluded.last_msg_content,
            last_msg_time=excluded.last_msg_time,
            member_count=excluded.member_count, mute_all=excluded.mute_all,
            risk_warning=excluded.risk_warning,
            risk_warning_text=excluded.risk_warning_text,
            history_visible_days=excluded.history_visible_days,
            service_end_time=excluded.service_end_time,
            fetched_at=excluded.fetched_at
        """
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(sql, rec)
                conn.commit()
            finally:
                conn.close()
        return True

    def list_chatrooms(self, only_watched: bool = False) -> list:
        """返回文字圈列表,如果 only_watched=True 只返回 watch_ids 列表中的."""
        if only_watched:
            ids_str = self.get_setting("ydchang.chatroom.watch_ids") or ""
            ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
            if not ids:
                return []
            placeholders = ",".join("?" * len(ids))
            sql = (
                f"SELECT * FROM T_ydchang_chatroom WHERE id IN ({placeholders}) "
                "ORDER BY last_msg_time DESC"
            )
            with self._lock:
                conn = self._conn()
                try:
                    rows = conn.execute(sql, ids).fetchall()
                finally:
                    conn.close()
        else:
            sql = (
                "SELECT * FROM T_ydchang_chatroom ORDER BY last_msg_time DESC"
            )
            with self._lock:
                conn = self._conn()
                try:
                    rows = conn.execute(sql).fetchall()
                finally:
                    conn.close()
        return [dict(r) for r in rows]

    def count_chatrooms(self) -> int:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM T_ydchang_chatroom"
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    # ── 消息 ─────────────────────────────────────────────
    def insert_msg(self, msg: dict) -> bool:
        """按 msg_id 去重,只插入新消息. 返回 True=新增, False=已存在."""
        sql = """
        INSERT OR IGNORE INTO T_ydchang_chatroom_msg
            (msg_id, room_id, sender_nickname, content, msg_type,
             msg_time, fetched_at, attachment_url, attachment_name)
        VALUES
            (:msg_id, :room_id, :sender_nickname, :content, :msg_type,
             :msg_time, :fetched_at, :attachment_url, :attachment_name)
        """
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(sql, msg)
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def list_msgs(self, room_id: int, limit: int = 200) -> list:
        sql = (
            "SELECT * FROM T_ydchang_chatroom_msg "
            "WHERE room_id=? ORDER BY msg_time DESC LIMIT ?"
        )
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(sql, (room_id, limit)).fetchall()
            finally:
                conn.close()
        return [dict(r) for r in rows]

    def count_msgs(self, room_id: int = None) -> int:
        if room_id is None:
            sql = "SELECT COUNT(*) FROM T_ydchang_chatroom_msg"
            params = ()
        else:
            sql = "SELECT COUNT(*) FROM T_ydchang_chatroom_msg WHERE room_id=?"
            params = (room_id,)
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(sql, params).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    def latest_msg_time(self, room_id: int) -> str:
        sql = (
            "SELECT msg_time FROM T_ydchang_chatroom_msg "
            "WHERE room_id=? ORDER BY msg_time DESC LIMIT 1"
        )
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(sql, (room_id,)).fetchone()
                return row[0] if row else None
            finally:
                conn.close()

    # ── 预装历史数据导入 ──────────────────────────────────
    def import_history_db(self, history_db_path: str) -> dict:
        """从预装的 ydchang_history.db 导入数据 (首次启动时调用).

        Returns: {"chatroom": n, "msg": n, "room": n, "video": n, "settings": n}
        """
        if not os.path.exists(history_db_path):
            return {"chatroom": 0, "msg": 0, "room": 0, "video": 0, "settings": 0}

        src = sqlite3.connect(history_db_path, timeout=10)
        src.row_factory = sqlite3.Row
        stats = {"chatroom": 0, "msg": 0, "room": 0, "video": 0, "settings": 0}

        with self._lock:
            conn = self._conn()
            try:
                # 逐表导入: INSERT OR IGNORE 避免覆盖已有数据
                for tbl, stat_key in [
                    ("T_ydchang_chatroom", "chatroom"),
                    ("T_ydchang_chatroom_msg", "msg"),
                    ("T_ydchang_room", "room"),
                    ("T_ydchang_video", "video"),
                ]:
                    try:
                        cols = [r[1] for r in src.execute(
                            f"PRAGMA table_info('{tbl}')"
                        ).fetchall()]
                        rows = src.execute(f"SELECT * FROM {tbl}").fetchall()
                        if rows:
                            placeholders = ",".join("?" * len(cols))
                            col_names = ",".join(cols)
                            cur = conn.executemany(
                                f"INSERT OR IGNORE INTO {tbl} ({col_names}) "
                                f"VALUES ({placeholders})",
                                [tuple(r[c] for c in cols) for r in rows],
                            )
                            stats[stat_key] = cur.rowcount
                    except Exception:
                        pass
                # 导入 settings (仅 ydchang 相关)
                try:
                    rows = src.execute(
                        "SELECT key,value,category,updated_at FROM app_settings "
                        "WHERE key LIKE 'ydchang%'"
                    ).fetchall()
                    for r in rows:
                        conn.execute(
                            "INSERT OR IGNORE INTO app_settings"
                            "(key,value,category,updated_at) VALUES(?,?,?,?)",
                            (r["key"], r["value"], r["category"], r["updated_at"]),
                        )
                    stats["settings"] = len(rows)
                except Exception:
                    pass
                conn.commit()
            finally:
                conn.close()
                src.close()
        return stats

    def is_history_loaded(self) -> bool:
        """检查是否已导入预装数据."""
        return self.count_chatrooms() > 0 or self.count_rooms() > 0

    # ── 直播间 (T_ydchang_room) ───────────────────────────
    def upsert_room(self, rec: dict) -> bool:
        sql = """
        INSERT INTO T_ydchang_room
            (room_id, room_name, room_code, anchor_id, anchor_nick,
             room_type, room_status, room_category, room_description,
             room_cover, is_password_protected, max_viewers, room_level,
             is_recommend, audit_status, live_time_pre, config,
             create_by, create_time, update_by, update_time, del_flag,
             live_id, live_title, live_status, external_live_id,
             scheduled_at, started_at, stopped_at, cover_url, notice,
             pull_rtmp_url, pull_hls_url, pull_flv_url, fetched_at)
        VALUES
            (:room_id, :room_name, :room_code, :anchor_id, :anchor_nick,
             :room_type, :room_status, :room_category, :room_description,
             :room_cover, :is_password_protected, :max_viewers, :room_level,
             :is_recommend, :audit_status, :live_time_pre, :config,
             :create_by, :create_time, :update_by, :update_time, :del_flag,
             :live_id, :live_title, :live_status, :external_live_id,
             :scheduled_at, :started_at, :stopped_at, :cover_url, :notice,
             :pull_rtmp_url, :pull_hls_url, :pull_flv_url, :fetched_at)
        ON CONFLICT(room_id) DO UPDATE SET
            room_name=excluded.room_name, anchor_nick=excluded.anchor_nick,
            room_status=excluded.room_status, room_category=excluded.room_category,
            room_description=excluded.room_description, room_cover=excluded.room_cover,
            live_status=excluded.live_status, live_title=excluded.live_title,
            cover_url=excluded.cover_url, notice=excluded.notice,
            started_at=excluded.started_at, stopped_at=excluded.stopped_at,
            scheduled_at=excluded.scheduled_at,
            pull_rtmp_url=excluded.pull_rtmp_url,
            pull_hls_url=excluded.pull_hls_url,
            pull_flv_url=excluded.pull_flv_url,
            update_time=excluded.update_time,
            fetched_at=excluded.fetched_at
        """
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(sql, rec)
                conn.commit()
            finally:
                conn.close()
        return True

    def list_rooms(self, limit: int = 200) -> list:
        sql = (
            "SELECT room_id, room_name, anchor_nick, room_status, "
            "room_category, room_description, room_cover, cover_url, "
            "live_status, live_title, started_at, stopped_at, scheduled_at, "
            "notice, update_time, fetched_at "
            "FROM T_ydchang_room "
            "WHERE del_flag IS NULL OR del_flag='0' "
            "ORDER BY COALESCE(update_time, '') DESC LIMIT ?"
        )
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(sql, (limit,)).fetchall()
            finally:
                conn.close()
        return [dict(r) for r in rows]

    def get_room_by_id(self, room_id: int) -> dict:
        sql = "SELECT * FROM T_ydchang_room WHERE room_id=?"
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(sql, (room_id,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def count_rooms(self) -> int:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM T_ydchang_room"
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    def get_max_room_id(self) -> int:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT MAX(room_id) FROM T_ydchang_room"
                ).fetchone()
                return row[0] if row and row[0] else 0
            finally:
                conn.close()

    # ── 视频 (T_ydchang_video) ───────────────────────────
    def save_videos(self, videos: list) -> tuple:
        """批量保存视频, INSERT OR IGNORE 去重. Returns (inserted, skipped)."""
        if not videos:
            return (0, 0)
        sql = """
        INSERT OR IGNORE INTO T_ydchang_video
            (record_id, room_id, title, file_url, domain, stream, app, uri,
             duration, start_time, stop_time, start_time_text, stop_time_text,
             fetched_at)
        VALUES
            (:record_id, :room_id, :title, :file_url, :domain, :stream, :app,
             :uri, :duration, :start_time, :stop_time, :start_time_text,
             :stop_time_text, :fetched_at)
        """
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.executemany(sql, videos)
                conn.commit()
                inserted = cur.rowcount
            finally:
                conn.close()
        return (inserted, len(videos) - inserted)

    def list_videos(self, room_id: int = None, limit: int = 200) -> list:
        if room_id is not None:
            sql = (
                "SELECT * FROM T_ydchang_video WHERE room_id=? "
                "ORDER BY start_time DESC LIMIT ?"
            )
            params = (room_id, limit)
        else:
            sql = (
                "SELECT v.*, r.room_name, r.anchor_nick "
                "FROM T_ydchang_video v "
                "LEFT JOIN T_ydchang_room r ON v.room_id = r.room_id "
                "ORDER BY v.start_time DESC LIMIT ?"
            )
            params = (limit,)
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        return [dict(r) for r in rows]

    def count_videos(self, room_id: int = None) -> int:
        if room_id is not None:
            sql = "SELECT COUNT(*) FROM T_ydchang_video WHERE room_id=?"
            params = (room_id,)
        else:
            sql = "SELECT COUNT(*) FROM T_ydchang_video"
            params = ()
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(sql, params).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()
