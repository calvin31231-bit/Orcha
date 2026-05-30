from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shorts_orchestrator.settings import DB_DIR

DB_PATH = DB_DIR / "shorts_orchestrator.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    account TEXT NOT NULL,
    workflow TEXT NOT NULL,
    topic TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    account TEXT NOT NULL,
    local_file TEXT,
    title TEXT,
    description TEXT,
    youtube_video_id TEXT,
    privacy_status TEXT,
    compliance_json TEXT,
    analytics_json TEXT
);

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    account TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    payload_json TEXT NOT NULL,
    lessons TEXT
);

CREATE TABLE IF NOT EXISTS manager_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    account TEXT NOT NULL,
    report_type TEXT NOT NULL,
    report_text TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_run(account: str, workflow: str, topic: str | None, payload: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs(created_at, account, workflow, topic, payload_json) VALUES (?, ?, ?, ?, ?)",
            (now_iso(), account, workflow, topic, json.dumps(payload, ensure_ascii=False, indent=2)),
        )
        return int(cur.lastrowid)


def save_video(account: str, local_file: str | None, title: str | None, description: str | None,
               youtube_video_id: str | None = None, privacy_status: str | None = None,
               compliance: dict[str, Any] | None = None, analytics: dict[str, Any] | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO videos(created_at, account, local_file, title, description, youtube_video_id,
                    privacy_status, compliance_json, analytics_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now_iso(), account, local_file, title, description, youtube_video_id, privacy_status,
                json.dumps(compliance or {}, ensure_ascii=False, indent=2),
                json.dumps(analytics or {}, ensure_ascii=False, indent=2),
            ),
        )
        return int(cur.lastrowid)


def list_recent_runs(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def list_recent_videos(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]



def list_recent_runs_by_account(account: str, limit: int = 25) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE account=? ORDER BY id DESC LIMIT ?", (account, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def list_recent_videos_by_account(account: str, limit: int = 25) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE account=? ORDER BY id DESC LIMIT ?", (account, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def save_analytics_snapshot(account: str, start_date: str | None, end_date: str | None,
                            payload: dict[str, Any], lessons: str | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO analytics_snapshots(created_at, account, start_date, end_date, payload_json, lessons) VALUES (?, ?, ?, ?, ?, ?)",
            (now_iso(), account, start_date, end_date, json.dumps(payload, ensure_ascii=False, indent=2), lessons),
        )
        return int(cur.lastrowid)


def update_video_analytics(youtube_video_id: str, analytics: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE videos SET analytics_json=? WHERE youtube_video_id=?",
            (json.dumps(analytics, ensure_ascii=False, indent=2), youtube_video_id),
        )


def save_manager_report(account: str, report_type: str, report_text: str, payload: dict[str, Any] | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO manager_reports(created_at, account, report_type, report_text, payload_json) VALUES (?, ?, ?, ?, ?)",
            (now_iso(), account, report_type, report_text, json.dumps(payload or {}, ensure_ascii=False, indent=2)),
        )
        return int(cur.lastrowid)


def list_recent_manager_reports(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM manager_reports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
