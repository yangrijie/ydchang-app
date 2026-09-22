#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源达投顾文字圈采集器 (APK 端,无 db_manager 依赖)
- 复用 PC 端 ydchang_chatroom_sync.py 的采集与解析逻辑
- 直接使用 services.database.AppDatabase 进行本地存储
- 提供 run_once() 便于前台服务循环调用
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import requests

from services.database import AppDatabase


# ── 常量 ──────────────────────────────────────────────
DEFAULT_TOKEN = "5befc0fa-1aa7-45a4-a764-e64960492806"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Mobile/15E148 MicroMessenger/8.0.40 NetType/WIFI Language/zh_CN"
)
ROOM_API = "https://chatroom-api.ydchang.com.cn/api/rooms/{}"
SLEEP_BETWEEN = 0.3  # 单位秒,与 PC 端一致,避免触发频控


def make_headers(token: str) -> dict:
    return {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://live.ydchang.com.cn/",
        "Origin": "https://live.ydchang.com.cn",
        "Authorization": f"Bearer {token}",
    }


def fetch_room(room_id: int, headers: dict, timeout: int = 15) -> dict | None:
    """调用 /api/rooms/{id}, 返回 data dict 或 None(不存在/失败)."""
    try:
        resp = requests.get(ROOM_API.format(room_id), headers=headers, timeout=timeout)
        result = resp.json()
        if result.get("code") == 200 and result.get("data"):
            return result["data"]
        return None
    except Exception as e:
        print(f"  [ERR] rooms/{room_id}: {type(e).__name__}: {e}")
        return None


def parse_last_msg(body_text: str) -> dict | None:
    """解析 lastMsgBody JSON 字符串.

    支持四种结构:
      1. quote (普通文本/图片)
      2. fileUrl (文件附件)
      3. mentions (@消息) - 返回 None,由调用方降级处理
      4. 其他 - 返回 None
    """
    if not body_text:
        return None
    try:
        obj = json.loads(body_text)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    # 结构 1: quote
    quote = obj.get("quote")
    if quote and isinstance(quote, dict):
        return {
            "msg_id": quote.get("msgId"),
            "sender_nickname": quote.get("senderNickname"),
            "content": quote.get("content"),
            "msg_type": quote.get("msgType"),
            "attachment_url": None,
            "attachment_name": None,
        }

    # 结构 2: fileUrl (文件附件)
    file_url = obj.get("fileUrl")
    if file_url:
        return {
            "msg_id": None,
            "sender_nickname": None,
            "content": obj.get("fileName") or file_url,
            "msg_type": 3,
            "attachment_url": file_url,
            "attachment_name": obj.get("fileName"),
        }

    # 结构 3/4: mentions 或其他 -> None
    return None


class ChatroomCollector:
    """采集器封装,提供 run_msgs / run_rooms / run_once 等方法."""

    def __init__(self, db: AppDatabase, token: str = None):
        self.db = db
        self.token = token or self._load_token()
        self.headers = make_headers(self.token)

    def _load_token(self) -> str:
        return self.db.get_setting("ydchang.token") or DEFAULT_TOKEN

    def reload_token(self, token: str):
        """供设置页修改 token 后调用."""
        self.token = token
        self.headers = make_headers(token)

    def _get_watch_ids(self) -> list[int]:
        ids_str = self.db.get_setting("ydchang.chatroom.watch_ids") or "74"
        return [int(x) for x in ids_str.split(",") if x.strip().isdigit()]

    # ── 模式 1: 消息采集 ─────────────────────────────────
    def run_msgs(self, ids: list[int] = None, on_progress=None) -> dict:
        """采集指定房间的最新消息,按 msg_id 去重.

        Args:
            ids: 房间 ID 列表, 为 None 时使用 watch_ids
            on_progress: 回调 fn(room_id, new_count, total)
        Returns:
            {"new": n, "skipped": n, "total": n, "errors": n}
        """
        if ids is None:
            ids = self._get_watch_ids()
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = {"new": 0, "skipped": 0, "total": len(ids), "errors": 0}

        for rid in ids:
            data = fetch_room(rid, self.headers)
            if data is None:
                stats["errors"] += 1
                if on_progress:
                    on_progress(rid, 0, stats["total"])
                time.sleep(SLEEP_BETWEEN)
                continue

            name = data.get("name", "")
            body_text = data.get("lastMsgBody")
            msg = parse_last_msg(body_text)
            if not msg or not msg.get("msg_id"):
                # 降级: 用 lastMsgContent 作为内容, 用 room_id+time 生成伪 msg_id
                content = data.get("lastMsgContent")
                if not content:
                    stats["errors"] += 1
                    if on_progress:
                        on_progress(rid, 0, stats["total"])
                    time.sleep(SLEEP_BETWEEN)
                    continue
                msg_id = f"c_{rid}_{data.get('lastMsgTime')}"
                msg = {
                    "msg_id": msg_id,
                    "sender_nickname": None,
                    "content": content,
                    "msg_type": 0,
                    "attachment_url": None,
                    "attachment_name": None,
                }

            msg["room_id"] = rid
            msg["msg_time"] = data.get("lastMsgTime")
            msg["fetched_at"] = fetched_at

            if self.db.insert_msg(msg):
                stats["new"] += 1
                sender = msg.get("sender_nickname") or "(未知)"
                print(
                    f"  id={rid}({name}): 新消息 [{sender}] "
                    f"{str(msg['content'])[:40]}..."
                )
            else:
                stats["skipped"] += 1

            if on_progress:
                on_progress(rid, stats["new"], stats["total"])

            time.sleep(SLEEP_BETWEEN)

        return stats

    # ── 模式 2: 文字圈列表 ───────────────────────────────
    def run_rooms(self, start: int = 1, end: int = 100, on_progress=None) -> dict:
        """扫描 start~end, upsert 文字圈."""
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = {
            "found": 0,
            "saved": 0,
            "empty": 0,
            "total": end - start + 1,
        }

        for rid in range(start, end + 1):
            data = fetch_room(rid, self.headers)
            if data is None:
                stats["empty"] += 1
                if on_progress:
                    on_progress(rid, stats["found"], stats["total"])
                time.sleep(SLEEP_BETWEEN)
                continue

            stats["found"] += 1
            name = data.get("name", "")
            rec = {
                "id": rid,
                "mch_id": data.get("mchId"),
                "name": name,
                "type": data.get("type"),
                "avatar_url": data.get("avatarUrl"),
                "description": data.get("description"),
                "owner_id": (
                    str(data.get("ownerId"))
                    if data.get("ownerId") is not None
                    else None
                ),
                "last_msg_content": data.get("lastMsgContent"),
                "last_msg_time": data.get("lastMsgTime"),
                "member_count": data.get("memberCount"),
                "mute_all": 1 if data.get("muteAll") else 0,
                "risk_warning": 1 if data.get("riskWarning") else 0,
                "risk_warning_text": data.get("riskWarningText"),
                "history_visible_days": data.get("historyVisibleDays"),
                "service_end_time": data.get("serviceEndTime"),
                "fetched_at": fetched_at,
            }
            if self.db.upsert_chatroom(rec):
                stats["saved"] += 1

            if on_progress:
                on_progress(rid, stats["found"], stats["total"])

            time.sleep(SLEEP_BETWEEN)

        return stats

    # ── 模式 3: 单次采集 (前台服务用) ───────────────────
    def run_once(self) -> dict:
        """前台服务一次采集,只针对 watch_ids 房间."""
        return self.run_msgs()

    # ── Token 过期检测 ────────────────────────────────────
    def check_token_status(self) -> dict:
        """检测当前 token 是否有效.

        Returns:
            {"valid": bool, "status": str, "detail": str}
            status: "valid" | "expired" | "error"
        """
        try:
            resp = requests.get(
                ROOM_API.format(74), headers=self.headers, timeout=10
            )
            result = resp.json()
            code = result.get("code")
            if code == 200:
                return {"valid": True, "status": "valid",
                        "detail": "Token 有效,API 正常响应"}
            # 401/403 或非 200 通常意味着 token 过期/无效
            if resp.status_code in (401, 403) or code in (401, 403):
                return {"valid": False, "status": "expired",
                        "detail": f"Token 已过期或无效 (HTTP {resp.status_code})"}
            msg = result.get("msg") or result.get("message") or ""
            if "token" in msg.lower() or "auth" in msg.lower() or "登录" in msg:
                return {"valid": False, "status": "expired",
                        "detail": f"Token 已过期: {msg}"}
            return {"valid": True, "status": "valid",
                    "detail": f"API 响应 code={code}"}
        except requests.exceptions.ConnectionError:
            return {"valid": None, "status": "error",
                    "detail": "无法连接服务器,请检查网络"}
        except Exception as e:
            return {"valid": None, "status": "error",
                    "detail": f"检测失败: {type(e).__name__}: {e}"}


# ══════════════════════════════════════════════════════════════════
# 直播间 + 视频采集器 (源达投顾直播平台)
# ══════════════════════════════════════════════════════════════════
LIVE_ROOM_API = "https://live-api.ydchang.com.cn/api/v1/live/room/getByRoomId"
PLAYBACK_API = "https://live-api.ydchang.com.cn/api/v1/live/getPlaybackList"


def make_live_headers(token: str) -> dict:
    return {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://live.ydchang.com.cn/",
        "Origin": "https://live.ydchang.com.cn",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _ts_to_text(ts):
    """Unix 时间戳 → 'YYYY-MM-DD HH:MM:SS' (东八区)"""
    if ts is None:
        return None
    try:
        n = int(ts)
        if n > 0:
            from datetime import timezone, timedelta
            dt = datetime.fromtimestamp(n, tz=timezone.utc) + timedelta(hours=8)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None


def fetch_live_room(room_id, headers, timeout=15):
    """调用 getByRoomId, 返回 data dict 或 None."""
    try:
        resp = requests.post(
            LIVE_ROOM_API,
            json={"room_id": str(room_id), "provider": "ALIYUN"},
            headers=headers,
            timeout=timeout,
        )
        result = resp.json()
        if result.get("code") == 200 and result.get("data"):
            return result["data"]
        return None
    except Exception as e:
        print(f"  [ERR] getByRoomId room_id={room_id}: {type(e).__name__}: {e}")
        return None


def fetch_playback_list(room_id, headers, timeout=15):
    """调用 getPlaybackList, 返回回放列表."""
    try:
        resp = requests.get(
            f"{PLAYBACK_API}?roomId={room_id}",
            headers=headers,
            timeout=timeout,
        )
        result = resp.json()
        if result.get("code") == 200:
            data = result.get("data")
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        print(f"  [ERR] getPlaybackList room_id={room_id}: {type(e).__name__}: {e}")
        return []


def _map_room_record(room_id, api_data, fetched_at):
    lr = api_data.get("live_room") or {}
    li = api_data.get("live_info") or {}
    pull = li.get("pull_url_info") or {}
    return {
        "room_id": room_id,
        "room_name": lr.get("room_name"),
        "room_code": lr.get("room_code"),
        "anchor_id": str(lr.get("anchor_id")) if lr.get("anchor_id") else None,
        "anchor_nick": li.get("anchor_nick"),
        "room_type": lr.get("room_type"),
        "room_status": lr.get("room_status"),
        "room_category": lr.get("room_category"),
        "room_description": lr.get("room_description"),
        "room_cover": lr.get("room_cover"),
        "is_password_protected": lr.get("is_password_protected"),
        "max_viewers": lr.get("max_viewers"),
        "room_level": lr.get("room_level"),
        "is_recommend": lr.get("is_recommend"),
        "audit_status": lr.get("audit_status"),
        "live_time_pre": lr.get("live_time_pre"),
        "config": lr.get("config"),
        "create_by": lr.get("create_by"),
        "create_time": lr.get("create_time"),
        "update_by": lr.get("update_by"),
        "update_time": lr.get("update_time"),
        "del_flag": lr.get("del_flag"),
        "live_id": li.get("id"),
        "live_title": li.get("title"),
        "live_status": li.get("status"),
        "external_live_id": li.get("external_live_id"),
        "scheduled_at": li.get("scheduled_at"),
        "started_at": li.get("started_at"),
        "stopped_at": li.get("stopped_at"),
        "cover_url": li.get("cover_url"),
        "notice": li.get("notice"),
        "pull_rtmp_url": pull.get("rtmp_url"),
        "pull_hls_url": pull.get("hls_url"),
        "pull_flv_url": pull.get("flv_url"),
        "fetched_at": fetched_at,
    }


def _map_video_record(room_id, item, fetched_at):
    start_ts = item.get("startTime")
    stop_ts = item.get("stopTime")
    return {
        "record_id": item.get("recordId"),
        "room_id": room_id,
        "title": item.get("title"),
        "file_url": item.get("fileUrl"),
        "domain": item.get("domain"),
        "stream": item.get("stream"),
        "app": item.get("app"),
        "uri": item.get("uri"),
        "duration": item.get("duration"),
        "start_time": start_ts,
        "stop_time": stop_ts,
        "start_time_text": _ts_to_text(start_ts),
        "stop_time_text": _ts_to_text(stop_ts),
        "fetched_at": fetched_at,
    }


class LiveRoomCollector:
    """直播间 + 回放视频采集器."""

    def __init__(self, db: AppDatabase, token: str = None):
        self.db = db
        self.token = token or self._load_token()
        self.headers = make_live_headers(self.token)

    def _load_token(self) -> str:
        return self.db.get_setting("ydchang.token") or DEFAULT_TOKEN

    def reload_token(self, token: str):
        self.token = token
        self.headers = make_live_headers(token)

    # ── 初始化采集: 扫描 roomId 范围 ──────────────────────
    def run_init(self, start=1, end=100, on_progress=None) -> dict:
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats = {"rooms_found": 0, "rooms_saved": 0,
                 "videos_saved": 0, "empty": 0,
                 "total": end - start + 1}

        for rid in range(start, end + 1):
            api_data = fetch_live_room(rid, self.headers)
            if api_data is None:
                stats["empty"] += 1
                if on_progress:
                    on_progress(rid, stats["rooms_found"], stats["total"])
                time.sleep(SLEEP_BETWEEN)
                continue

            stats["rooms_found"] += 1
            rec = _map_room_record(rid, api_data, fetched_at)
            self.db.upsert_room(rec)
            stats["rooms_saved"] += 1

            playback = fetch_playback_list(rid, self.headers)
            if playback:
                video_recs = [_map_video_record(rid, it, fetched_at)
                              for it in playback]
                ok, _ = self.db.save_videos(video_recs)
                stats["videos_saved"] += ok

            if on_progress:
                on_progress(rid, stats["rooms_found"], stats["total"])
            time.sleep(SLEEP_BETWEEN)

        return stats

    # ── 增量同步: 扫描新房间 + 刷新已有回放 ──────────────
    def run_increment(self, scan_range=50, on_progress=None) -> dict:
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        max_rid = self.db.get_max_room_id()
        scan_end = max_rid + scan_range
        stats = {"new_rooms": 0, "new_videos": 0,
                 "refreshed_videos": 0, "total": scan_range}

        # Part 1: 扫描新房间
        for rid in range(max_rid + 1, scan_end + 1):
            api_data = fetch_live_room(rid, self.headers)
            if api_data is None:
                time.sleep(SLEEP_BETWEEN)
                continue
            stats["new_rooms"] += 1
            rec = _map_room_record(rid, api_data, fetched_at)
            self.db.upsert_room(rec)
            playback = fetch_playback_list(rid, self.headers)
            if playback:
                video_recs = [_map_video_record(rid, it, fetched_at)
                              for it in playback]
                ok, _ = self.db.save_videos(video_recs)
                stats["new_videos"] += ok
            if on_progress:
                on_progress(rid, stats["new_rooms"], stats["total"])
            time.sleep(SLEEP_BETWEEN)

        # Part 2: 刷新已有房间回放 (最近 10 个)
        rooms = self.db.list_rooms(limit=10)
        for r in rooms:
            rid = r["room_id"]
            playback = fetch_playback_list(rid, self.headers)
            if playback:
                video_recs = [_map_video_record(rid, it, fetched_at)
                              for it in playback]
                ok, _ = self.db.save_videos(video_recs)
                stats["refreshed_videos"] += ok
            time.sleep(SLEEP_BETWEEN)

        return stats

    # ── 刷新已有房间回放 ─────────────────────────────────
    def run_refresh(self, on_progress=None) -> dict:
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rooms = self.db.list_rooms(limit=200)
        total = len(rooms)
        stats = {"rooms": total, "videos_saved": 0}

        for i, r in enumerate(rooms):
            rid = r["room_id"]
            playback = fetch_playback_list(rid, self.headers)
            if playback:
                video_recs = [_map_video_record(rid, it, fetched_at)
                              for it in playback]
                ok, _ = self.db.save_videos(video_recs)
                stats["videos_saved"] += ok
            if on_progress:
                on_progress(i + 1, stats["videos_saved"], total)
            time.sleep(SLEEP_BETWEEN)

        return stats
