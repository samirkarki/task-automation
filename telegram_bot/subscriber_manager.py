#!/usr/bin/env python3
"""
VIP Subscriber Management Database
Maintains an SQLite database of active Telegram subscribers, subscription expiration,
and payment references (eSewa / Khalti / Fonepay).
"""

import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger("subscriber_manager")
DB_PATH = Path(__file__).resolve().parent / "subscribers.db"


def init_db(db_path: Path = DB_PATH):
    """
    Initializes the subscriber table if it does not exist.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                tier TEXT DEFAULT 'VIP_MONTHLY',
                payment_ref TEXT,
                amount_npr REAL DEFAULT 1000.0,
                start_date TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def add_subscriber(
    telegram_user_id: str,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
    days: int = 30,
    payment_ref: Optional[str] = None,
    amount_npr: float = 1000.0,
    db_path: Path = DB_PATH,
) -> Dict[str, Any]:
    """
    Adds or renews a VIP subscriber.
    """
    init_db(db_path)
    now = datetime.now()
    expiry = now + timedelta(days=days)

    now_str = now.isoformat()
    expiry_str = expiry.isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subscribers (
                telegram_user_id, username, full_name, tier, payment_ref, amount_npr,
                start_date, expiry_date, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                expiry_date = ?,
                is_active = 1,
                payment_ref = ?
        """, (
            str(telegram_user_id), username or "", full_name or "", "VIP_MONTHLY",
            payment_ref or "MANUAL", amount_npr, now_str, expiry_str, now_str,
            expiry_str, payment_ref or "RENEWAL"
        ))
        conn.commit()

    logger.info(f"Registered/renewed VIP subscriber {telegram_user_id} ({username}) until {expiry_str}")
    return {
        "telegram_user_id": telegram_user_id,
        "username": username,
        "expiry_date": expiry_str,
        "is_active": True,
    }


def is_active_subscriber(telegram_user_id: str, db_path: Path = DB_PATH) -> bool:
    """
    Checks if a subscriber has an unexpired active subscription.
    """
    init_db(db_path)
    now_str = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM subscribers
            WHERE telegram_user_id = ? AND is_active = 1 AND expiry_date > ?
        """, (str(telegram_user_id), now_str))
        row = cursor.fetchone()
        return row is not None


def get_active_subscribers_count(db_path: Path = DB_PATH) -> int:
    """
    Returns count of currently active VIP subscribers.
    """
    init_db(db_path)
    now_str = datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM subscribers
            WHERE is_active = 1 AND expiry_date > ?
        """, (now_str,))
        return cursor.fetchone()[0]


if __name__ == "__main__":
    init_db()
    count = get_active_subscribers_count()
    print(f"VIP Subscribers Database initialized. Currently active members: {count}")
