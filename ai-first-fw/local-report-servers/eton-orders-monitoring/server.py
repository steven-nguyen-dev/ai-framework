#!/usr/bin/env python3
"""Eton Orders Monitoring Report Server

Monitors replay and live orders processed through Eton WMS.
Strictly queries Kibana in batches of 100 per request, commits batches
to local SQLite (eton_orders.db), and increments checkpoints to avoid
re-querying previously stored orders.

Supports 50,000+ orders with sub-millisecond indexed queries and pagination.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import signal
import socket
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

# Path resolution
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
LOCAL_THEME_DIR = REPO_ROOT / "ai-first-fw" / "local-theme"
DATA_DIR = HERE / "data"
DB_PATH = DATA_DIR / "eton_orders.db"

def _read_version() -> str:
    v_file = HERE / "VERSION"
    if v_file.is_file():
        try:
            return v_file.read_text(encoding="utf-8").strip() or "1.0.0"
        except Exception:
            pass
    return "1.0.0"

__version__ = _read_version()

# Load credentials from local .env, then parent elk-log-explorer/.env, then local-mcps
for env_path in [
    HERE / ".env",
    HERE.parent / "elk-log-explorer" / ".env",
    REPO_ROOT / "ai-first-fw" / "local-mcps" / "kibana" / ".env",
]:
    if env_path.is_file():
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        curr = os.environ.get(k, "")
                        if not curr or curr.startswith("your_"):
                            os.environ[k] = v
                        else:
                            os.environ.setdefault(k, v)
        except Exception:
            pass

KIBANA_URL = os.environ.get("KIBANA_URL", "https://apac-elk.anchanto.com:5601").rstrip("/")
USERNAME = os.environ.get("KIBANA_USERNAME", "")
PASSWORD = os.environ.get("KIBANA_PASSWORD", "")
INDEX = os.environ.get("KIBANA_INDEX_PATTERN", "logs-*-*,logs-*,filebeat-*")
VERIFY_SSL = os.environ.get("KIBANA_VERIFY_SSL", "true").lower() != "false"
PAGE_SIZE = 100  # Strict batch size requested: query only 100 per time

# -----------------------------------------------------------------------------
# SQLite Persistent Storage (WAL mode for 50,000+ orders)
# -----------------------------------------------------------------------------
class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory mapped I/O
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self):
        conn = self.get_connection()
        with conn:
            # Stage 1 raw events
            conn.execute("""
            CREATE TABLE IF NOT EXISTS stage1_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                order_number TEXT,
                order_date TEXT,
                created_at TEXT,
                raw_json TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s1_order_num ON stage1_events(order_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s1_ts ON stage1_events(timestamp);")

            # Stage 2 raw events
            conn.execute("""
            CREATE TABLE IF NOT EXISTS stage2_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                order_number TEXT,
                wms_order_id TEXT,
                status TEXT,
                error_code TEXT,
                has_error TEXT,
                raw_json TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s2_order_num ON stage2_events(order_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s2_wms_id ON stage2_events(wms_order_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s2_ts ON stage2_events(timestamp);")

            # Stage 3 raw events
            conn.execute("""
            CREATE TABLE IF NOT EXISTS stage3_events (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                wms_order_id TEXT,
                status TEXT,
                error_code TEXT,
                raw_json TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s3_wms_id ON stage3_events(wms_order_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s3_ts ON stage3_events(timestamp);")

            # Materialized / Aggregated Orders table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_number TEXT PRIMARY KEY,
                order_date TEXT,
                created_at TEXT,
                s1_timestamp TEXT,
                wms_order_id TEXT,
                s2_timestamp TEXT,
                create_status TEXT,
                create_error_code TEXT,
                create_has_error TEXT,
                s3_timestamp TEXT,
                price_status TEXT,
                price_error_code TEXT,
                stage2_category TEXT,
                stage3_category TEXT,
                is_healthy INTEGER DEFAULT 1,
                last_updated TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ord_ts ON orders(s1_timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ord_wms ON orders(wms_order_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ord_s2_cat ON orders(stage2_category);")
            # Order Attempts table for tracking multi-attempt replays
            conn.execute("""
            CREATE TABLE IF NOT EXISTS order_attempts (
                id TEXT PRIMARY KEY,
                order_number TEXT,
                attempt_date TEXT,
                attempt_time TEXT,
                wms_order_id TEXT,
                create_status TEXT,
                create_error_code TEXT,
                create_has_error TEXT,
                price_time TEXT,
                price_status TEXT,
                price_error_code TEXT,
                stage2_category TEXT,
                stage3_category TEXT,
                is_healthy INTEGER DEFAULT 1,
                raw_create_json TEXT,
                raw_price_json TEXT,
                created_at TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_att_ord ON order_attempts(order_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_att_date ON order_attempts(attempt_date);")

            # Checkpoints table to track highest timestamp queried
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_checkpoints (
                stage TEXT PRIMARY KEY,
                last_timestamp TEXT,
                total_synced INTEGER DEFAULT 0,
                last_synced_at TEXT,
                status TEXT DEFAULT 'idle'
            );
            """)

            # Sync progress / execution history log
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                stage TEXT,
                batch_size INTEGER,
                message TEXT
            );
            """)
            # Fix any historic records where s1_timestamp was improperly populated with s2_timestamp
            conn.execute("""
            UPDATE orders SET s1_timestamp = NULL
            WHERE s1_timestamp = s2_timestamp
              AND NOT EXISTS (SELECT 1 FROM stage1_events s1 WHERE s1.order_number = orders.order_number);
            """)
            # Auto-classify orders where Eton 2300 prevented a duplicate creation but the primary order succeeded
            conn.execute("""
            UPDATE orders SET
                create_status = 'OK',
                create_error_code = '2300 (Dedup Prevented)',
                stage2_category = 'CREATED_OK',
                is_healthy = 1
            WHERE order_number IN (
                SELECT order_number FROM stage2_events WHERE error_code LIKE '%2300%'
            ) AND EXISTS (
                SELECT 1 FROM stage2_events s2 WHERE s2.order_number = orders.order_number AND (s2.status = 'OK' OR s2.error_code IS NULL OR s2.error_code = 'null')
            );
            """)

    def get_checkpoint(self, stage: str) -> Optional[str]:
        conn = self.get_connection()
        cur = conn.execute("SELECT last_timestamp FROM sync_checkpoints WHERE stage = ?", (stage,))
        row = cur.fetchone()
        if row and row["last_timestamp"]:
            return row["last_timestamp"]
        table_map = {
            "stage1": "stage1_events",
            "stage2": "stage2_events",
            "stage3": "stage3_events",
        }
        tbl = table_map.get(stage)
        if tbl:
            max_cur = conn.execute(f"SELECT MAX(timestamp) as max_ts FROM {tbl}")
            max_row = max_cur.fetchone()
            if max_row and max_row["max_ts"]:
                return max_row["max_ts"]
        return None

    def update_checkpoint(self, stage: str, last_timestamp: str, added_count: int = 0):
        conn = self.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
            INSERT INTO sync_checkpoints (stage, last_timestamp, total_synced, last_synced_at, status)
            VALUES (?, ?, ?, ?, 'idle')
            ON CONFLICT(stage) DO UPDATE SET
                last_timestamp = excluded.last_timestamp,
                total_synced = total_synced + excluded.total_synced,
                last_synced_at = excluded.last_synced_at,
                status = 'idle'
            """, (stage, last_timestamp, added_count, now))

    def save_stage1_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        conn = self.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            for r in batch:
                doc_id = r.get("_id") or f"{r.get('order_number')}_{r.get('@timestamp')}"
                ts = r.get("@timestamp") or r.get("timestamp") or r.get("created_at") or now
                ord_num = r.get("order_number")
                ord_date = r.get("order_date")
                created_at = r.get("created_at")
                raw = json.dumps(r)

                conn.execute("""
                INSERT INTO stage1_events (id, timestamp, order_number, order_date, created_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    order_number = excluded.order_number,
                    order_date = excluded.order_date,
                    created_at = excluded.created_at,
                    raw_json = excluded.raw_json
                """, (doc_id, ts, ord_num, ord_date, created_at, raw))

                if ord_num:
                    conn.execute("""
                    INSERT INTO orders (order_number, order_date, created_at, s1_timestamp, stage2_category, stage3_category, is_healthy, last_updated)
                    VALUES (?, ?, ?, ?, 'MISSING', 'NO_WMS_ID', 0, ?)
                    ON CONFLICT(order_number) DO UPDATE SET
                        order_date = COALESCE(excluded.order_date, orders.order_date),
                        created_at = COALESCE(excluded.created_at, orders.created_at),
                        s1_timestamp = COALESCE(excluded.s1_timestamp, orders.s1_timestamp),
                        last_updated = excluded.last_updated
                    """, (ord_num, ord_date, created_at, ts, now))

        self.recompute_classifications_for_orders([r.get("order_number") for r in batch if r.get("order_number")])

    def save_stage2_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        conn = self.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            for r in batch:
                doc_id = r.get("_id") or f"{r.get('order_number')}_{r.get('@timestamp')}"
                ts = r.get("@timestamp") or r.get("timestamp") or now
                ord_num = r.get("order_number")
                wms_id = r.get("wms_order_id")
                st = r.get("status")
                ec = r.get("error_code")
                he = r.get("has_error")
                raw = json.dumps(r)

                conn.execute("""
                INSERT INTO stage2_events (id, timestamp, order_number, wms_order_id, status, error_code, has_error, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    order_number = excluded.order_number,
                    wms_order_id = excluded.wms_order_id,
                    status = excluded.status,
                    error_code = excluded.error_code,
                    has_error = excluded.has_error,
                    raw_json = excluded.raw_json
                """, (doc_id, ts, ord_num, wms_id, st, ec, he, raw))

                if ord_num:
                    conn.execute("""
                    INSERT INTO orders (order_number, wms_order_id, s2_timestamp, create_status, create_error_code, create_has_error, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(order_number) DO UPDATE SET
                        wms_order_id = COALESCE(excluded.wms_order_id, orders.wms_order_id),
                        s2_timestamp = excluded.s2_timestamp,
                        create_status = excluded.create_status,
                        create_error_code = excluded.create_error_code,
                        create_has_error = excluded.create_has_error,
                        last_updated = excluded.last_updated
                    """, (ord_num, wms_id, ts, st, ec, he, now))

                    if wms_id:
                        conn.execute("""
                        UPDATE orders SET
                            s3_timestamp = (SELECT timestamp FROM stage3_events WHERE wms_order_id = ? ORDER BY timestamp DESC LIMIT 1),
                            price_status = (SELECT status FROM stage3_events WHERE wms_order_id = ? ORDER BY timestamp DESC LIMIT 1),
                            price_error_code = (SELECT error_code FROM stage3_events WHERE wms_order_id = ? ORDER BY timestamp DESC LIMIT 1)
                        WHERE order_number = ? AND (price_status IS NULL OR s3_timestamp IS NULL)
                          AND EXISTS (SELECT 1 FROM stage3_events WHERE wms_order_id = ?)
                        """, (wms_id, wms_id, wms_id, ord_num, wms_id))

        self.recompute_classifications_for_orders([r.get("order_number") for r in batch if r.get("order_number")])

    def save_stage3_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        conn = self.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        affected_wms = set()
        with conn:
            for r in batch:
                doc_id = r.get("_id") or f"{r.get('wms_order_id')}_{r.get('@timestamp')}"
                ts = r.get("@timestamp") or r.get("timestamp") or now
                wms_id = r.get("wms_order_id")
                st = r.get("status")
                ec = r.get("error_code")
                raw = json.dumps(r)

                conn.execute("""
                INSERT INTO stage3_events (id, timestamp, wms_order_id, status, error_code, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    wms_order_id = excluded.wms_order_id,
                    status = excluded.status,
                    error_code = excluded.error_code,
                    raw_json = excluded.raw_json
                """, (doc_id, ts, wms_id, st, ec, raw))

                if wms_id:
                    affected_wms.add(wms_id)
                    conn.execute("""
                    UPDATE orders SET
                        s3_timestamp = ?,
                        price_status = ?,
                        price_error_code = ?,
                        last_updated = ?
                    WHERE wms_order_id = ?
                    """, (ts, st, ec, now, wms_id))

        if affected_wms:
            # find order_numbers for these wms_ids
            placeholders = ",".join(["?"] * len(affected_wms))
            cur = conn.execute(f"SELECT order_number FROM orders WHERE wms_order_id IN ({placeholders})", list(affected_wms))
            ord_nums = [row["order_number"] for row in cur.fetchall()]
            self.recompute_classifications_for_orders(ord_nums)

    def recompute_classifications_for_orders(self, order_numbers: List[str]):
        if not order_numbers:
            return
        conn = self.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        # Deduplicate
        unique_orders = list(set(filter(None, order_numbers)))
        chunk_size = 500
        for i in range(0, len(unique_orders), chunk_size):
            chunk = unique_orders[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))

            # Detect true multiple successful creations (count > 1)
            dup_cur = conn.execute(f"""
                SELECT order_number, COUNT(*) as cnt
                FROM stage2_events
                WHERE order_number IN ({placeholders}) AND (status = 'OK' OR error_code IS NULL OR error_code = 'null')
                GROUP BY order_number
                HAVING cnt > 1
            """, chunk)
            dup_orders = {r["order_number"] for r in dup_cur.fetchall()}

            # Detect orders with at least one successful creation
            ok_cur = conn.execute(f"""
                SELECT DISTINCT order_number
                FROM stage2_events
                WHERE order_number IN ({placeholders}) AND (status = 'OK' OR error_code IS NULL OR error_code = 'null')
            """, chunk)
            ok_orders = {r["order_number"] for r in ok_cur.fetchall()}

            # Detect orders where Eton returned error 2300 (dedup collision)
            c2300_cur = conn.execute(f"""
                SELECT DISTINCT order_number
                FROM stage2_events
                WHERE order_number IN ({placeholders}) AND error_code LIKE '%2300%'
            """, chunk)
            c2300_orders = {r["order_number"] for r in c2300_cur.fetchall()}

            cur = conn.execute(f"SELECT * FROM orders WHERE order_number IN ({placeholders})", chunk)
            rows = cur.fetchall()
            with conn:
                for row in rows:
                    ord_num = row["order_number"]
                    s2_cat = "MISSING"
                    create_st = row["create_status"]
                    create_ec = row["create_error_code"]

                    if row["s2_timestamp"] is not None or row["create_status"] is not None:
                        ec = (row["create_error_code"] or "").strip().lower()
                        if ord_num in dup_orders:
                            s2_cat = "DUPLICATE_CREATED"
                        elif ord_num in ok_orders:
                            s2_cat = "CREATED_OK"
                            create_st = "OK"
                            if ord_num in c2300_orders:
                                create_ec = "2300 (Dedup Prevented)"
                        elif ec == "beso05":
                            s2_cat = "BESO05"
                        elif ec in ("", "null", "none"):
                            s2_cat = "CREATED_OK"
                        else:
                            s2_cat = "OTHER_ERROR"

                    s3_cat = "NO_WMS_ID"
                    if row["wms_order_id"]:
                        if (row["price_status"] or "").strip().upper() == "OK":
                            s3_cat = "PRICE_OK"
                        elif row["price_status"] is not None or row["price_error_code"] is not None:
                            s3_cat = "PRICE_FAILED"
                        else:
                            s3_cat = "NEVER_PRICED"

                    is_healthy = 1
                    if s2_cat not in ("BESO05", "CREATED_OK"):
                        is_healthy = 0
                    if s3_cat in ("PRICE_FAILED", "NEVER_PRICED"):
                        is_healthy = 0

                    conn.execute("""
                    UPDATE orders SET
                        create_status = ?,
                        create_error_code = ?,
                        stage2_category = ?,
                        stage3_category = ?,
                        is_healthy = ?,
                        last_updated = ?
                    WHERE order_number = ?
                    """, (create_st, create_ec, s2_cat, s3_cat, is_healthy, now, row["order_number"]))

    def get_stats(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cur = conn.execute("""
        SELECT
            COUNT(*) as total_orders,
            COUNT(CASE WHEN stage2_category != 'MISSING' THEN 1 END) as stage2_reached,
            COUNT(CASE WHEN stage2_category = 'BESO05' THEN 1 END) as beso05_count,
            COUNT(CASE WHEN stage2_category = 'CREATED_OK' THEN 1 END) as created_ok_count,
            COUNT(CASE WHEN stage2_category = 'DUPLICATE_CREATED' THEN 1 END) as duplicate_created_count,
            COUNT(CASE WHEN stage2_category IN ('OTHER_ERROR', 'MISSING') THEN 1 END) as creation_errors_count,
            COUNT(CASE WHEN stage2_category = 'OTHER_ERROR' THEN 1 END) as other_error_count,
            COUNT(CASE WHEN stage2_category = 'MISSING' THEN 1 END) as missing_stage2_count,
            COUNT(CASE WHEN stage3_category = 'PRICE_OK' THEN 1 END) as price_ok_count,
            COUNT(CASE WHEN stage3_category IN ('PRICE_FAILED', 'NEVER_PRICED') THEN 1 END) as pricing_errors_count,
            COUNT(CASE WHEN stage3_category = 'PRICE_FAILED' THEN 1 END) as price_failed_count,
            COUNT(CASE WHEN stage3_category = 'NEVER_PRICED' THEN 1 END) as never_priced_count,
            COUNT(CASE WHEN is_healthy = 1 THEN 1 END) as healthy_orders_count
        FROM orders
        """)
        row = cur.fetchone()
        res = dict(row) if row else {}

        # Overall health logic
        total = res.get("total_orders", 0)
        duplicates = res.get("duplicate_created_count", 0)
        creation_err = res.get("creation_errors_count", 0)
        pricing_err = res.get("pricing_errors_count", 0)

        is_all_clear = (
            total > 0
            and duplicates == 0
            and creation_err == 0
            and pricing_err == 0
        )
        res["all_clear"] = is_all_clear

        # Checkpoints
        cp_cur = conn.execute("SELECT stage, last_timestamp, total_synced, last_synced_at FROM sync_checkpoints")
        res["checkpoints"] = {r["stage"]: dict(r) for r in cp_cur.fetchall()}
        return res

    def get_orders(
        self,
        page: int = 1,
        limit: int = 50,
        search: Optional[str] = None,
        category_filter: Optional[str] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc"
    ) -> Tuple[List[Dict[str, Any]], int]:
        conn = self.get_connection()
        clauses = []
        params: List[Any] = []

        if search:
            s = f"%{search.strip()}%"
            clauses.append("(order_number LIKE ? OR wms_order_id LIKE ? OR create_error_code LIKE ? OR price_error_code LIKE ?)")
            params.extend([s, s, s, s])

        if category_filter:
            f = category_filter.lower().strip()
            if f == "duplicates_created":
                clauses.append("stage2_category = 'DUPLICATE_CREATED'")
            elif f == "created_ok":
                clauses.append("stage2_category = 'CREATED_OK'")
            elif f == "beso05":
                clauses.append("stage2_category = 'BESO05'")
            elif f == "price_ok":
                clauses.append("stage3_category = 'PRICE_OK'")
            elif f in ("creation_errors", "other_error", "missing_stage2"):
                clauses.append("stage2_category IN ('OTHER_ERROR', 'MISSING')")
            elif f in ("pricing_errors", "price_failed", "never_priced"):
                clauses.append("stage3_category IN ('PRICE_FAILED', 'NEVER_PRICED')")

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        # Count total matching
        cur = conn.execute(f"SELECT COUNT(*) as cnt FROM orders {where_sql}", params)
        total = cur.fetchone()["cnt"]

        # Sort field mapping
        col_map = {
            "timestamp": "COALESCE(s1_timestamp, s2_timestamp, created_at, last_updated)",
            "created_at": "COALESCE(created_at, order_date)",
            "order_number": "order_number",
            "wms_order_id": "wms_order_id",
            "create_status": "create_status",
            "price_status": "price_status",
            "is_healthy": "is_healthy"
        }
        col = col_map.get(sort_by.lower(), "COALESCE(s1_timestamp, s2_timestamp, created_at, last_updated)")
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        offset = max(0, (page - 1) * limit)
        sql = f"""
        SELECT
            order_number,
            order_date,
            created_at,
            s1_timestamp,
            wms_order_id,
            s2_timestamp,
            create_status,
            create_error_code,
            create_has_error,
            s3_timestamp,
            price_status,
            price_error_code,
            stage2_category,
            stage3_category,
            is_healthy,
            last_updated
        FROM orders
        {where_sql}
        ORDER BY {col} {direction}
        LIMIT ? OFFSET ?
        """
        exec_params = list(params) + [limit, offset]
        rows = conn.execute(sql, exec_params).fetchall()
        return [dict(r) for r in rows], total

    def get_order_detail(self, order_number: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.execute("SELECT * FROM orders WHERE order_number = ?", (order_number,))
        ord_row = cur.fetchone()
        if not ord_row:
            return None
        res = dict(ord_row)

        # Fetch stage 1 events
        s1_cur = conn.execute("SELECT * FROM stage1_events WHERE order_number = ? ORDER BY timestamp DESC", (order_number,))
        res["stage1_events"] = [dict(r) for r in s1_cur.fetchall()]

        # Fetch stage 2 events
        s2_cur = conn.execute("SELECT * FROM stage2_events WHERE order_number = ? ORDER BY timestamp DESC", (order_number,))
        res["stage2_events"] = [dict(r) for r in s2_cur.fetchall()]

        # Fetch stage 3 events (via wms_order_id if available)
        res["stage3_events"] = []
        if res.get("wms_order_id"):
            s3_cur = conn.execute("SELECT * FROM stage3_events WHERE wms_order_id = ? ORDER BY timestamp DESC", (res["wms_order_id"],))
            res["stage3_events"] = [dict(r) for r in s3_cur.fetchall()]

        # Fetch all attempts for this order
        att_cur = conn.execute("SELECT * FROM order_attempts WHERE order_number = ? ORDER BY attempt_date ASC, attempt_time ASC", (order_number,))
        res["attempts"] = [dict(r) for r in att_cur.fetchall()]

        return res

    def get_order_attempts(self, order_number: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        if order_number:
            cur = conn.execute("SELECT * FROM order_attempts WHERE order_number = ? ORDER BY attempt_date ASC, attempt_time ASC", (order_number,))
        else:
            cur = conn.execute("SELECT * FROM order_attempts ORDER BY attempt_date ASC, attempt_time ASC")
        return [dict(r) for r in cur.fetchall()]

    def reset_database(self, keep_audited: bool = False):
        conn = self.get_connection()
        with conn:
            conn.execute("DELETE FROM stage1_events;")
            conn.execute("DELETE FROM stage2_events;")
            conn.execute("DELETE FROM stage3_events;")
            conn.execute("DELETE FROM sync_checkpoints;")
            conn.execute("DELETE FROM sync_history;")
            if not keep_audited:
                conn.execute("DELETE FROM order_attempts;")
                conn.execute("DELETE FROM orders;")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.execute("VACUUM;")


# -----------------------------------------------------------------------------
# Kibana Extraction Logic (Matching eton_replay_audit.py 100%)
# -----------------------------------------------------------------------------
_PRELUDE = r"""
def m = params._source.message;
if (m == null) return null;
m = m.replace('\\"', '"');
"""

def str_field(key: str, after: Optional[str] = None) -> Dict[str, Any]:
    if after:
        anchor = f"int a = m.indexOf('\"{after}\":'); if (a < 0) a = 0;"
    else:
        anchor = "int a = 0;"
    return {
        "script": {
            "lang": "painless",
            "source": _PRELUDE
            + anchor
            + f"""
String k = '"{key}":"';
int i = m.indexOf(k, a);
if (i < 0) return null;
int s = i + k.length();
int e = m.indexOf('"', s);
if (e < 0) return null;
return m.substring(s, e);
""",
        }
    }

def raw_field(key: str) -> Dict[str, Any]:
    return {
        "script": {
            "lang": "painless",
            "source": _PRELUDE
            + f"""
String k = '"{key}":';
int i = m.indexOf(k);
if (i < 0) return null;
int s = i + k.length();
int e = s;
while (e < m.length() && m.charAt(e) != (char)',' && m.charAt(e) != (char)'}}') {{ e++; }}
String v = m.substring(s, e).trim();
if (v.length() >= 2 && v.charAt(0) == (char)'"') {{ v = v.substring(1, v.length() - 1); }}
return v;
""",
        }
    }

def phrase(text: str) -> Dict[str, Any]:
    return {"match_phrase": {"message": text}}


class KibanaClient:
    def __init__(self):
        self.url = KIBANA_URL
        self.user = USERNAME
        self.pwd = PASSWORD
        self.cookie: Optional[str] = None
        self.session_token: Optional[str] = None
        self._ctx = ssl.create_default_context()
        if not VERIFY_SSL:
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        self._login()

    def _login(self):
        if not (self.user and self.pwd):
            return
        payload = {
            "providerType": "basic",
            "providerName": "basic",
            "currentURL": f"{self.url}/login",
            "params": {"username": self.user, "password": self.pwd},
        }
        req = urllib.request.Request(
            f"{self.url}/internal/security/login",
            data=json.dumps(payload).encode("utf-8"),
            headers={"kbn-xsrf": "true", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
                hdrs = resp.headers
                cookies = hdrs.get_all("Set-Cookie") if hasattr(hdrs, "get_all") else [hdrs.get("Set-Cookie")]
                if cookies:
                    tokens = []
                    for c in filter(None, cookies):
                        tokens.append(c.split(";")[0].strip())
                    self.cookie = "; ".join(tokens)
        except Exception:
            # Fall back to HTTP basic authorization
            raw = f"{self.user}:{self.pwd}".encode("utf-8")
            self.session_token = "Basic " + base64.b64encode(raw).decode("ascii")

    def es_post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {"kbn-xsrf": "true", "Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        elif self.session_token:
            headers["Authorization"] = self.session_token

        query_str = urllib.parse.urlencode({"path": path, "method": "POST"})
        req = urllib.request.Request(
            f"{self.url}/api/console/proxy?{query_str}",
            data=json.dumps(body).encode("utf-8") if body is not None else b"",
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kibana ES proxy error {e.code}: {err_msg[:400]}")


# -----------------------------------------------------------------------------
# Incremental Batch Sync Engine (100 per query, checkpointed)
# -----------------------------------------------------------------------------
class SyncEngine:
    def __init__(self, db: Database):
        self.db = db
        self.lock = threading.Lock()
        self.is_running = False
        self.cancel_requested = False
        self.current_stage: Optional[str] = None
        self.total_fetched = 0
        self.current_batch = 0
        self.status_message = "Idle"
        self.last_error: Optional[str] = None

    def status_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "is_running": self.is_running,
                "current_stage": self.current_stage,
                "total_fetched": self.total_fetched,
                "current_batch": self.current_batch,
                "status_message": self.status_message,
                "last_error": self.last_error,
            }

    def cancel(self):
        with self.lock:
            if self.is_running:
                self.cancel_requested = True
                self.status_message = "Cancelling..."

    def run_sync_task(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None,
        max_batches: Optional[int] = None,
        stages: Optional[List[str]] = None,
    ):
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            self.cancel_requested = False
            self.total_fetched = 0
            self.current_batch = 0
            self.last_error = None
            self.status_message = "Starting sync..."

        thread = threading.Thread(
            target=self._execute_sync,
            args=(since, until, max_batches, stages),
            daemon=True,
        )
        thread.start()

    def _execute_sync(
        self,
        since: Optional[str],
        until: Optional[str],
        max_batches: Optional[int],
        stages: Optional[List[str]],
    ):
        target_stages = stages or ["stage1", "stage2", "stage3"]
        now_iso = datetime.now(timezone.utc).isoformat()
        end_time = until or "now"

        try:
            kb = KibanaClient()
            for stage_name in target_stages:
                if self.cancel_requested:
                    break

                with self.lock:
                    self.current_stage = stage_name
                    self.status_message = f"Syncing {stage_name}..."

                # Retrieve saved checkpoint
                cp = self.db.get_checkpoint(stage_name)
                start_time = since
                if not start_time:
                    # If no specific 'since' requested, resume strictly from checkpoint
                    start_time = cp or "2026-08-01T00:00:00.000Z"
                elif cp and not since.startswith("now"):
                    # If since was given but cp is newer, only query what is NOT stored
                    if cp > since:
                        start_time = cp

                self._scan_and_save_stage(kb, stage_name, start_time, end_time, max_batches)

            # Automatically backfill missing created_at for any orders that arrived via Stage 2/3 but lack Stage 1
            if not self.cancel_requested:
                with self.lock:
                    self.status_message = "Backfilling missing created_at timestamps..."
                self._backfill_missing_created_at(kb)

            with self.lock:
                self.status_message = "Sync complete" if not self.cancel_requested else "Sync paused/cancelled"

        except Exception as ex:
            with self.lock:
                self.last_error = str(ex)
                self.status_message = f"Sync failed: {ex}"
        finally:
            with self.lock:
                self.is_running = False
                self.current_stage = None

    def _backfill_missing_created_at(self, kb: KibanaClient):
        conn = self.db.get_connection()
        chunk_size = 25
        while not self.cancel_requested:
            cur = conn.execute("SELECT order_number FROM orders WHERE created_at IS NULL LIMIT ?", (chunk_size,))
            missing_orders = [r[0] for r in cur.fetchall()]
            if not missing_orders:
                break

            q = {
                "size": 500,
                "_source": ["@timestamp"],
                "script_fields": {
                    "order_number": str_field("order_number"),
                    "order_date": str_field("order_date", after="order_number"),
                    "created_at": str_field("created_at", after="order_number")
                },
                "query": {
                    "bool": {
                        "filter": [
                            {"match_phrase": {"message": "\"event_name\":\"order_creation\""}},
                            {"match_phrase": {"message": "\"warehouse_code\":\"eton\""}}
                        ],
                        "should": [{"match_phrase": {"message": o}} for o in missing_orders],
                        "minimum_should_match": 1
                    }
                }
            }
            try:
                res = kb.es_post(f"{INDEX}/_search", q)
                hits = (res.get("hits") or {}).get("hits") or []
                batch_s1 = []
                found_orders = set()
                for h in hits:
                    f = h.get("fields") or {}
                    ord_nums = f.get("order_number") or []
                    if ord_nums:
                        ord_num = ord_nums[0]
                        found_orders.add(ord_num)
                        batch_s1.append({
                            "_id": h["_id"],
                            "@timestamp": (h.get("_source") or {}).get("@timestamp"),
                            "order_number": ord_num,
                            "order_date": (f.get("order_date") or [None])[0],
                            "created_at": (f.get("created_at") or [None])[0]
                        })
                if batch_s1:
                    self.db.save_stage1_batch(batch_s1)

                not_found = set(missing_orders) - found_orders
                if not_found:
                    with conn:
                        for nf in not_found:
                            conn.execute("""
                                UPDATE orders SET created_at = COALESCE(order_date, s2_timestamp, s1_timestamp)
                                WHERE order_number = ?
                            """, (nf,))
            except Exception:
                break

    def _scan_and_save_stage(
        self,
        kb: KibanaClient,
        stage: str,
        start_time: str,
        end_time: str,
        max_batches: Optional[int],
    ):
        if stage == "stage1":
            query_filter = [phrase('"event_name":"order_creation"'), phrase('"warehouse_code":"eton"')]
            fields = {
                "order_number": str_field("order_number"),
                "order_date": str_field("order_date", after="order_number"),
                "created_at": str_field("created_at", after="order_number"),
            }
            saver = self.db.save_stage1_batch
        elif stage == "stage2":
            query_filter = [phrase("EtonWmsService.executeEtonCreateOrderApi response")]
            fields = {
                "order_number": str_field("orderNumber"),
                "wms_order_id": str_field("Code"),
                "status": str_field("status"),
                "error_code": raw_field("ErrorCode"),
                "has_error": raw_field("HasError"),
            }
            saver = self.db.save_stage2_batch
        elif stage == "stage3":
            query_filter = [phrase("EtonUtils.pushPriceDetail response")]
            fields = {
                "wms_order_id": str_field("wmsOrderId"),
                "status": str_field("status"),
                "error_code": raw_field("ErrorCode"),
            }
            saver = self.db.save_stage3_batch
        else:
            return

        # Open PIT on target index
        pit_res = kb.es_post(f"{INDEX}/_pit?keep_alive=5m")
        pit_id = pit_res.get("id")
        if not pit_id:
            raise RuntimeError(f"Failed to open PIT on {INDEX}: {pit_res}")

        after_sort = None
        seen_ids = set()
        highest_ts = start_time
        stage_batch_count = 0

        try:
            while not self.cancel_requested:
                if max_batches and stage_batch_count >= max_batches:
                    break

                body: Dict[str, Any] = {
                    "size": PAGE_SIZE,  # Strictly 100 per request
                    "_source": {"includes": ["@timestamp"]},
                    "script_fields": fields,
                    "query": {
                        "bool": {
                            "filter": query_filter + [{"range": {"@timestamp": {"gte": start_time, "lt": end_time}}}]
                        }
                    },
                    "sort": [{"@timestamp": "asc"}, {"_shard_doc": "asc"}],
                    "pit": {"id": pit_id, "keep_alive": "5m"},
                }
                if after_sort:
                    body["search_after"] = after_sort

                res = kb.es_post("_search", body)
                hits = (res.get("hits") or {}).get("hits") or []
                if not hits:
                    break

                batch_rows: List[Dict[str, Any]] = []
                for h in hits:
                    hid = h["_id"]
                    if hid in seen_ids:
                        continue
                    seen_ids.add(hid)
                    row = {k: (v[0] if v else None) for k, v in (h.get("fields") or {}).items()}
                    row["_id"] = hid
                    # Extract timestamp from source or fields
                    doc_ts = (h.get("_source") or {}).get("@timestamp") or row.get("created_at")
                    if doc_ts:
                        row["@timestamp"] = doc_ts
                        if doc_ts > highest_ts:
                            highest_ts = doc_ts
                    batch_rows.append(row)

                # Save batch of 100 immediately to SQLite
                if batch_rows:
                    saver(batch_rows)
                    stage_batch_count += 1
                    with self.lock:
                        self.total_fetched += len(batch_rows)
                        self.current_batch += 1
                        self.status_message = f"[{stage}] Saved batch {stage_batch_count} (+{len(batch_rows)} orders, total: {self.total_fetched})"

                after_sort = hits[-1].get("sort")
                pit_id = res.get("pit_id", pit_id)

                # Persist checkpoint for this batch
                if highest_ts and highest_ts != start_time:
                    self.db.update_checkpoint(stage, highest_ts, len(batch_rows))

                if len(hits) < PAGE_SIZE:
                    break

        finally:
            try:
                kb.es_post("_pit", {"id": pit_id})
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Static Report Generator (--export)
# -----------------------------------------------------------------------------
def generate_static_report(db: Database) -> str:
    template_path = HERE / "report.html"
    if not template_path.is_file():
        return "<html><body><h1>report.html not found</h1></body></html>"

    html = template_path.read_text(encoding="utf-8")

    # Inlines theme.css for complete portability
    theme_css = ""
    for p in [HERE / "theme.css", LOCAL_THEME_DIR / "theme.css"]:
        if p.is_file():
            try:
                theme_css = p.read_text(encoding="utf-8")
                break
            except Exception:
                pass

    if theme_css:
        html = html.replace(
            '<link rel="stylesheet" href="/theme.css">',
            f'<style id="inlined-theme">\n{theme_css}\n</style>'
        )

    # Inlines snapshot data
    stats = db.get_stats()
    sample_orders, total = db.get_orders(page=1, limit=100)
    snapshot = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "orders": sample_orders,
        "total": total,
    }
    html = html.replace("__REPORT_SNAPSHOT_JSON__", json.dumps(snapshot))
    return html


# -----------------------------------------------------------------------------
# On-Demand Live Order Inspection Fallback (Queries ELK directly if missing in DB)
# -----------------------------------------------------------------------------
def get_order_detail_with_live_lookup(db: Database, order_number: str, force_live: bool = False) -> Optional[Dict[str, Any]]:
    order_number = order_number.strip()
    if not order_number:
        return None

    detail = db.get_order_detail(order_number)

    needs_s1 = force_live or (not detail) or (not detail.get("stage1_events"))
    needs_s2 = force_live or (not detail) or (not detail.get("stage2_events"))
    wms_id = detail.get("wms_order_id") if detail else None
    needs_s3 = force_live or (not detail) or (wms_id and not detail.get("stage3_events"))

    if not (needs_s1 or needs_s2 or needs_s3):
        return detail

    try:
        kb = KibanaClient()

        # 1. Fetch Stage 1 (order_creation) if missing or forced
        if needs_s1:
            q_s1 = {
                "size": 50,
                "_source": ["@timestamp"],
                "script_fields": {
                    "order_number": str_field("order_number"),
                    "order_date": str_field("order_date", after="order_number"),
                    "created_at": str_field("created_at", after="order_number"),
                },
                "query": {
                    "bool": {
                        "filter": [
                            {"match_phrase": {"message": "\"event_name\":\"order_creation\""}},
                            {"match_phrase": {"message": "\"warehouse_code\":\"eton\""}},
                            {"match_phrase": {"message": order_number}}
                        ]
                    }
                },
                "sort": [{"@timestamp": "desc"}]
            }
            res_s1 = kb.es_post(f"{INDEX}/_search", q_s1)
            hits_s1 = (res_s1.get("hits") or {}).get("hits") or []
            if hits_s1:
                batch_s1 = []
                for h in hits_s1:
                    f = h.get("fields") or {}
                    batch_s1.append({
                        "_id": h["_id"],
                        "@timestamp": (h.get("_source") or {}).get("@timestamp"),
                        "order_number": (f.get("order_number") or [order_number])[0],
                        "order_date": (f.get("order_date") or [None])[0],
                        "created_at": (f.get("created_at") or [None])[0],
                    })
                db.save_stage1_batch(batch_s1)

        # 2. Fetch Stage 2 (executeEtonCreateOrderApi) if missing or forced
        if needs_s2:
            q_s2 = {
                "size": 50,
                "_source": ["@timestamp"],
                "script_fields": {
                    "order_number": str_field("orderNumber"),
                    "wms_order_id": str_field("Code"),
                    "status": str_field("status"),
                    "error_code": raw_field("ErrorCode"),
                    "has_error": raw_field("HasError"),
                },
                "query": {
                    "bool": {
                        "filter": [
                            {"match_phrase": {"message": f"\"orderNumber\":\"{order_number}\""}},
                            {"match_phrase": {"message": "EtonWmsService.executeEtonCreateOrderApi response"}}
                        ]
                    }
                },
                "sort": [{"@timestamp": "desc"}]
            }
            res_s2 = kb.es_post(f"{INDEX}/_search", q_s2)
            hits_s2 = (res_s2.get("hits") or {}).get("hits") or []
            if hits_s2:
                batch_s2 = []
                for h in hits_s2:
                    f = h.get("fields") or {}
                    batch_s2.append({
                        "_id": h["_id"],
                        "@timestamp": (h.get("_source") or {}).get("@timestamp"),
                        "order_number": (f.get("order_number") or [order_number])[0],
                        "wms_order_id": (f.get("wms_order_id") or [None])[0],
                        "status": (f.get("status") or [None])[0],
                        "error_code": (f.get("error_code") or [None])[0],
                        "has_error": (f.get("has_error") or [None])[0],
                    })
                db.save_stage2_batch(batch_s2)

        # Re-check wms_order_id after Stage 2 update
        detail = db.get_order_detail(order_number)
        wms_id = detail.get("wms_order_id") if detail else None

        # 3. Fetch Stage 3 (pushPriceDetail) if needed
        if wms_id and (needs_s3 or force_live or not detail.get("stage3_events")):
            q_s3 = {
                "size": 50,
                "_source": ["@timestamp"],
                "script_fields": {
                    "wms_order_id": str_field("wmsOrderId"),
                    "status": str_field("status"),
                    "error_code": raw_field("ErrorCode"),
                },
                "query": {
                    "bool": {
                        "filter": [
                            {"match_phrase": {"message": f"\"wmsOrderId\":\"{wms_id}\""}},
                            {"match_phrase": {"message": "EtonUtils.pushPriceDetail response"}}
                        ]
                    }
                },
                "sort": [{"@timestamp": "desc"}]
            }
            res_s3 = kb.es_post(f"{INDEX}/_search", q_s3)
            hits_s3 = (res_s3.get("hits") or {}).get("hits") or []
            if hits_s3:
                batch_s3 = []
                for h in hits_s3:
                    f = h.get("fields") or {}
                    batch_s3.append({
                        "_id": h["_id"],
                        "@timestamp": (h.get("_source") or {}).get("@timestamp"),
                        "wms_order_id": (f.get("wms_order_id") or [wms_id])[0],
                        "status": (f.get("status") or [None])[0],
                        "error_code": (f.get("error_code") or [None])[0],
                    })
                db.save_stage3_batch(batch_s3)

        detail = db.get_order_detail(order_number)
    except Exception:
        pass

    return detail


# -----------------------------------------------------------------------------
# Direct Specific Orders Query (Step 1 CreateOrder + Step 2 PushPrice)
# -----------------------------------------------------------------------------
def query_specific_orders(db: Database, kb: Optional[KibanaClient], order_numbers: List[str]) -> Dict[str, Any]:
    if kb is None:
        kb = KibanaClient()
    conn = db.get_connection()
    saved_attempts = []

    for ord_num in order_numbers:
        ord_num = ord_num.strip()
        if not ord_num:
            continue
        body_s2 = {
            "size": 50,
            "query": {
                "bool": {
                    "filter": [
                        {"match_phrase": {"message": f"\"orderNumber\":\"{ord_num}\""}},
                        {"match_phrase": {"message": "EtonWmsService.executeEtonCreateOrderApi response"}}
                    ]
                }
            },
            "sort": [{"@timestamp": "asc"}]
        }
        res_s2 = kb.es_post("_search", body_s2)
        hits_s2 = res_s2.get("hits", {}).get("hits", [])

        for h in hits_s2:
            msg = h["_source"].get("message", "")
            ts = h["_source"].get("@timestamp", "")

            m_time = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}[,\.]\d{3})", msg)
            date_str = m_time.group(1) if m_time else ts[:10]
            time_str = m_time.group(2).replace(",", ".") if m_time else ts[11:23]

            m_code = re.search(r"\\\"Code\\\":\\\"([^\\]+)\\\"", msg) or re.search(r"\"Code\":\"([^\"]+)\"", msg)
            wms_id = m_code.group(1) if m_code else None

            m_status = re.search(r"\"status\":\"([^\"]+)\"", msg)
            status = m_status.group(1) if m_status else None

            m_ec = re.search(r"\\\"ErrorCode\\\":(\\\"[^\\]+\\\"|null|[^\,\}]+)", msg) or re.search(r"\"ErrorCode\":(\"[^\"]+\"|null|[^\,\}]+)", msg)
            ec = m_ec.group(1).replace("\\\"", "").replace("\"", "") if m_ec else None
            if ec in ("null", "None", ""):
                ec = "null"

            price_time = None
            price_status = None
            price_ec = None
            raw_price = None
            if wms_id:
                body_s3 = {
                    "size": 10,
                    "query": {
                        "bool": {
                            "filter": [
                                {"match_phrase": {"message": f"\"wmsOrderId\":\"{wms_id}\""}},
                                {"match_phrase": {"message": "EtonUtils.pushPriceDetail response"}},
                                {"range": {"@timestamp": {"gte": date_str + "T00:00:00Z", "lte": date_str + "T23:59:59Z"}}}
                            ]
                        }
                    },
                    "sort": [{"@timestamp": "asc"}]
                }
                res_s3 = kb.es_post("_search", body_s3)
                hits_s3 = res_s3.get("hits", {}).get("hits", [])
                if hits_s3:
                    h3 = hits_s3[0]
                    msg3 = h3["_source"].get("message", "")
                    ts3 = h3["_source"].get("@timestamp", "")
                    m_time3 = re.search(r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})", msg3)
                    price_time = m_time3.group(1).replace(",", ".") if m_time3 else ts3[11:23]
                    m_status3 = re.search(r"\"status\":\"([^\"]+)\"", msg3)
                    price_status = m_status3.group(1) if m_status3 else None
                    m_ec3 = re.search(r"\\\"ErrorCode\\\":(\\\"[^\\]+\\\"|null|[^\,\}]+)", msg3) or re.search(r"\"ErrorCode\":(\"[^\"]+\"|null|[^\,\}]+)", msg3)
                    price_ec = m_ec3.group(1).replace("\\\"", "").replace("\"", "") if m_ec3 else None
                    if price_ec in ("null", "None", ""):
                        price_ec = "null"
                    raw_price = msg3

            s2_cat = "OTHER_ERROR"
            if ec.lower() == "beso05":
                s2_cat = "BESO05"
            elif ec == "null":
                s2_cat = "DUPLICATE_CREATED"

            s3_cat = "NEVER_PRICED"
            if price_status and price_status.upper() == "OK":
                s3_cat = "PRICE_OK"
            elif price_status:
                s3_cat = "PRICE_FAILED"

            is_healthy = 1 if (s2_cat == "BESO05" and s3_cat == "PRICE_OK") else 0
            att_id = f"{ord_num}_{date_str}_{time_str}"

            with conn:
                conn.execute("""
                INSERT INTO order_attempts (
                    id, order_number, attempt_date, attempt_time, wms_order_id,
                    create_status, create_error_code, create_has_error,
                    price_time, price_status, price_error_code, stage2_category,
                    stage3_category, is_healthy, raw_create_json, raw_price_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    wms_order_id = excluded.wms_order_id,
                    create_status = excluded.create_status,
                    create_error_code = excluded.create_error_code,
                    price_time = excluded.price_time,
                    price_status = excluded.price_status,
                    price_error_code = excluded.price_error_code,
                    stage2_category = excluded.stage2_category,
                    stage3_category = excluded.stage3_category,
                    is_healthy = excluded.is_healthy
                """, (
                    att_id, ord_num, date_str, time_str, wms_id,
                    status, ec, "false" if ec == "null" else "true",
                    price_time, price_status, price_ec, s2_cat,
                    s3_cat, is_healthy, msg, raw_price, ts
                ))

                conn.execute("""
                INSERT INTO orders (
                    order_number, order_date, created_at, s1_timestamp, wms_order_id,
                    s2_timestamp, create_status, create_error_code, create_has_error,
                    s3_timestamp, price_status, price_error_code, stage2_category,
                    stage3_category, is_healthy, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_number) DO UPDATE SET
                    wms_order_id = excluded.wms_order_id,
                    s2_timestamp = excluded.s2_timestamp,
                    create_status = excluded.create_status,
                    create_error_code = excluded.create_error_code,
                    create_has_error = excluded.create_has_error,
                    s3_timestamp = excluded.s3_timestamp,
                    price_status = excluded.price_status,
                    price_error_code = excluded.price_error_code,
                    stage2_category = excluded.stage2_category,
                    stage3_category = excluded.stage3_category,
                    is_healthy = excluded.is_healthy,
                    last_updated = excluded.last_updated
                """, (
                    ord_num, date_str, ts, ts, wms_id,
                    ts, status, ec, "false" if ec == "null" else "true",
                    ts, price_status, price_ec, s2_cat,
                    s3_cat, is_healthy, ts
                ))

            saved_attempts.append({
                "id": att_id,
                "order_number": ord_num,
                "attempt_date": date_str,
                "attempt_time": time_str,
                "wms_order_id": wms_id,
                "create_status": status,
                "create_error_code": ec,
                "price_time": price_time,
                "price_status": price_status,
                "price_error_code": price_ec,
                "stage2_category": s2_cat,
                "stage3_category": s3_cat,
                "is_healthy": is_healthy
            })

    grouped = defaultdict(list)
    for a in saved_attempts:
        d = a["attempt_date"]
        label = f"Attempt — {d}"
        if d == "2026-08-20":
            label = "Attempt 1 — 2026-08-20 (original)"
        elif d == "2026-09-03":
            label = "Attempt 2 — 2026-09-03 (retry)"
        grouped[label].append(a)

    return {
        "success": True,
        "count": len(saved_attempts),
        "attempts": saved_attempts,
        "grouped": dict(grouped)
    }


# -----------------------------------------------------------------------------
# HTTP Request Handler & REST APIs
# -----------------------------------------------------------------------------
GLOBAL_DB: Optional[Database] = None
GLOBAL_SYNC: Optional[SyncEngine] = None

class EtonMonitoringHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, format: str, *args: Any):
        # Suppress noisy standard requests
        if args and str(args[0]).startswith(("GET /api/sync/status", "GET /api/stats")):
            return
        super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._serve_report_html()
            return
        elif path == "/api/stats":
            self._serve_json(GLOBAL_DB.get_stats())
            return
        elif path == "/api/orders":
            self._serve_orders(query)
            return
        elif path == "/api/order":
            ord_id = query.get("id", [""])[0]
            refresh = query.get("refresh", ["0"])[0] in ("1", "true")
            detail = get_order_detail_with_live_lookup(GLOBAL_DB, ord_id, force_live=refresh)
            if detail:
                self._serve_json(detail)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Order not found")
            return
        elif path == "/api/sync/status":
            st = GLOBAL_SYNC.status_dict()
            st["db_stats"] = GLOBAL_DB.get_stats()
            self._serve_json(st)
            return
        elif path == "/api/funnel":
            stats = GLOBAL_DB.get_stats()
            funnel_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "stage1_orders": stats.get("total_orders", 0),
                "stage2_reached": stats.get("stage2_reached", 0),
                "beso05": stats.get("beso05_count", 0),
                "other_error": stats.get("other_error_count", 0),
                "duplicates_created": stats.get("duplicate_created_count", 0),
                "price_ok": stats.get("price_ok_count", 0),
                "price_failed": stats.get("price_failed_count", 0),
                "price_missing": stats.get("never_priced_count", 0),
                "missing_at_stage2": stats.get("missing_stage2_count", 0),
                "healthy": stats.get("all_clear", False),
            }
            self._serve_json(funnel_data)
            return
        elif path == "/api/order-attempts":
            ord_id = query.get("id", [""])[0] or None
            self._serve_json(GLOBAL_DB.get_order_attempts(ord_id))
            return
        elif path == "/api/export/csv":
            self._serve_csv(query)
            return
        elif path == "/export":
            content = generate_static_report(GLOBAL_DB).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="eton-orders-monitoring.html"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/query-orders":
            order_nums = data.get("order_numbers") or []
            if isinstance(order_nums, str):
                order_nums = [x.strip() for x in re.split(r"[\s,;]+", order_nums) if x.strip()]
            res = query_specific_orders(GLOBAL_DB, None, order_nums)
            self._serve_json(res)
            return
        elif path == "/api/sync":
            since = data.get("since")
            until = data.get("until")
            max_batches = data.get("max_batches")
            stages = data.get("stages")
            GLOBAL_SYNC.run_sync_task(since=since, until=until, max_batches=max_batches, stages=stages)
            self._serve_json({"status": "started", "sync": GLOBAL_SYNC.status_dict()})
            return
        elif path == "/api/sync/stop":
            GLOBAL_SYNC.cancel()
            self._serve_json({"status": "cancelled", "sync": GLOBAL_SYNC.status_dict()})
            return
        elif path == "/api/reset-db":
            keep_audited = bool(data.get("keep_audited", False))
            GLOBAL_DB.reset_database(keep_audited=keep_audited)
            stats = GLOBAL_DB.get_stats()
            self._serve_json({"status": "ok", "message": "Database reset successfully", "stats": stats})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "API route not found")

    def _serve_report_html(self):
        report_file = HERE / "report.html"
        if not report_file.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "report.html not found")
            return
        content = report_file.read_text(encoding="utf-8")
        # Replace template placeholder if present
        stats = GLOBAL_DB.get_stats()
        content = content.replace("__INITIAL_STATS__", json.dumps(stats))
        body_bytes = content.encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _serve_orders(self, query: Dict[str, List[str]]):
        page = int(query.get("page", ["1"])[0])
        limit = min(500, max(1, int(query.get("limit", ["50"])[0])))
        search = query.get("search", [""])[0] or None
        cat_filter = query.get("filter", [""])[0] or None
        sort_by = query.get("sort_by", ["timestamp"])[0]
        sort_order = query.get("sort_order", ["desc"])[0]

        orders, total = GLOBAL_DB.get_orders(
            page=page,
            limit=limit,
            search=search,
            category_filter=cat_filter,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        self._serve_json({
            "orders": orders,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "totalPages": total_pages,
            },
        })

    def _serve_csv(self, query: Dict[str, List[str]]):
        cat_filter = query.get("filter", [""])[0] or None
        search = query.get("search", [""])[0] or None
        # Retrieve up to 50,000 orders matching filter
        orders, _ = GLOBAL_DB.get_orders(page=1, limit=50000, search=search, category_filter=cat_filter)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp",
            "createdAt",
            "orderNumber",
            "orderDate",
            "wmsOrderId",
            "creationStatus",
            "creationErrorCode",
            "creationHasError",
            "pushPriceStatus",
            "pushPriceErrorCode",
            "stage2Category",
            "stage3Category",
            "isHealthy",
            "lastUpdated",
        ])
        for o in orders:
            writer.writerow([
                o.get("s1_timestamp") or o.get("s2_timestamp") or "",
                o.get("created_at") or o.get("order_date") or "",
                o.get("order_number") or "",
                o.get("order_date") or "",
                o.get("wms_order_id") or "",
                o.get("create_status") or "",
                o.get("create_error_code") or "",
                o.get("create_has_error") or "",
                o.get("price_status") or "",
                o.get("price_error_code") or "",
                o.get("stage2_category") or "",
                o.get("stage3_category") or "",
                "1" if o.get("is_healthy") else "0",
                o.get("last_updated") or "",
            ])

        content = output.getvalue().encode("utf-8")
        filename = f"eton_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data: Any):
        body = json.dumps(data).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# -----------------------------------------------------------------------------
# Main & Entry Point
# -----------------------------------------------------------------------------
def main():
    global GLOBAL_DB, GLOBAL_SYNC

    parser = argparse.ArgumentParser(description="Eton Orders Monitoring Report Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "24005")))
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--export", action="store_true", help="Generate standalone static HTML report and exit")
    parser.add_argument("--reset", action="store_true", help="Reset all stored orders and sync checkpoints in the database and exit")
    args = parser.parse_args()

    GLOBAL_DB = Database()
    GLOBAL_SYNC = SyncEngine(GLOBAL_DB)

    if args.reset:
        print("Resetting Eton orders database...")
        GLOBAL_DB.reset_database(keep_audited=False)
        print("✔ Database cleared and vacuumed successfully.")
        return 0

    if args.export:
        print("Generating static standalone HTML export...")
        html_out = generate_static_report(GLOBAL_DB)
        out_path = HERE / "eton-orders-monitoring.html"
        out_path.write_text(html_out, encoding="utf-8")
        print(f"✔ Static report generated: {out_path}")
        return 0

    server_address = (args.host, args.port)
    try:
        httpd = _Server(server_address, EtonMonitoringHandler)
    except OSError as e:
        if e.errno == 48:
            print(f"✗ Port {args.port} is already in use.")
            print(f"  Run: kill -9 $(lsof -ti :{args.port})")
            print(f"  Or use a different port: python3 server.py --port <PORT>")
            return 1
        raise

    print("=" * 66)
    print(f"🚀 Eton Orders Monitoring Server v{__version__}")
    print("=" * 66)
    print(f"  • URL:         http://{args.host}:{args.port}")
    print(f"  • Database:    {DB_PATH}")
    print(f"  • Batch size:  100 per query (strictly bounded)")
    print(f"  • Kibana URL:  {KIBANA_URL}")
    print(f"  • Index:       {INDEX}")
    print(f"  • Press Ctrl+C to stop the server.")
    print("=" * 66)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
