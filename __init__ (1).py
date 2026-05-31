# database/db.py
import aiosqlite
import time
from typing import Optional, List

import config


class Database:
    def __init__(self, path: str):
        self.path = path

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        await self.conn.close()

    async def _create_tables(self):
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned INTEGER DEFAULT 0,
                joined_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS files (
                file_code TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_name TEXT,
                file_size INTEGER DEFAULT 0,
                caption TEXT,
                storage_chat_id INTEGER,
                storage_message_id INTEGER,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                invite_link TEXT,
                added_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                message_text TEXT,
                message_type TEXT DEFAULT 'text',
                sent_at INTEGER
            );
            """
        )
        await self.conn.commit()

        cur = await self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", ("force_join",)
        )
        row = await cur.fetchone()
        if row is None:
            await self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ("force_join", "1"),
            )
            await self.conn.commit()

    # ---------- کاربران ----------
    async def add_user(self, user_id: int, username: str, first_name: str):
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, int(time.time())),
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        return await cur.fetchone()

    async def get_all_user_ids(self) -> List[int]:
        cur = await self.conn.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r["user_id"] for r in rows]

    async def count_users(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM users")
        row = await cur.fetchone()
        return row["c"]

    async def count_banned(self) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_banned = 1"
        )
        row = await cur.fetchone()
        return row["c"]

    async def ban_user(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,)
        )
        await self.conn.commit()

    async def unban_user(self, user_id: int):
        await self.conn.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,)
        )
        await self.conn.commit()

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return bool(user and user["is_banned"] == 1)

    # ---------- ادمین‌ها ----------
    async def add_admin(self, user_id: int, username: str):
        await self.conn.execute(
            """
            INSERT INTO admins (user_id, username, added_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, username, int(time.time())),
        )
        await self.conn.commit()

    async def remove_admin(self, user_id: int):
        await self.conn.execute(
            "DELETE FROM admins WHERE user_id = ?", (user_id,)
        )
        await self.conn.commit()

    async def get_admins(self) -> List[aiosqlite.Row]:
        cur = await self.conn.execute("SELECT * FROM admins ORDER BY added_at")
        return await cur.fetchall()

    async def is_admin(self, user_id: int) -> bool:
        if user_id == config.OWNER_ID:
            return True
        cur = await self.conn.execute(
            "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
        )
        return await cur.fetchone() is not None

    async def count_admins(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM admins")
        row = await cur.fetchone()
        return row["c"] + 1

    # ---------- فایل‌ها ----------
    async def add_file(self, file_code, file_id, file_type, file_name, file_size, caption, storage_chat_id, storage_message_id):
        await self.conn.execute(
            """
            INSERT INTO files
            (file_code, file_id, file_type, file_name, file_size, caption,
             storage_chat_id, storage_message_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_code, file_id, file_type, file_name, file_size, caption,
             storage_chat_id, storage_message_id, int(time.time())),
        )
        await self.conn.commit()

    async def get_file(self, file_code: str) -> Optional[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM files WHERE file_code = ?", (file_code,)
        )
        return await cur.fetchone()

    async def delete_file(self, file_code: str):
        await self.conn.execute("DELETE FROM files WHERE file_code = ?", (file_code,))
        await self.conn.commit()

    async def list_files(self, limit: int = 50, offset: int = 0) -> List[aiosqlite.Row]:
        cur = await self.conn.execute(
            "SELECT * FROM files ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return await cur.fetchall()

    async def search_files(self, query: str) -> List[aiosqlite.Row]:
        like = f"%{query}%"
        cur = await self.conn.execute(
            "SELECT * FROM files WHERE file_name LIKE ? OR file_code LIKE ? ORDER BY created_at DESC LIMIT 50",
            (like, like),
        )
        return await cur.fetchall()

    async def count_files(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM files")
        row = await cur.fetchone()
        return row["c"]

    # ---------- کانال‌ها ----------
    async def add_channel(self, channel_id, title, username, invite_link):
        await self.conn.execute(
            """
            INSERT INTO channels (channel_id, title, username, invite_link, added_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                title = excluded.title,
                username = excluded.username,
                invite_link = excluded.invite_link
            """,
            (channel_id, title, username, invite_link, int(time.time())),
        )
        await self.conn.commit()

    async def remove_channel(self, channel_id: int):
        await self.conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await self.conn.commit()

    async def get_channels(self) -> List[aiosqlite.Row]:
        cur = await self.conn.execute("SELECT * FROM channels ORDER BY added_at")
        return await cur.fetchall()

    # ---------- تنظیمات ----------
    async def get_setting(self, key: str) -> Optional[str]:
        cur = await self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str):
        await self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await self.conn.commit()

    async def is_force_join(self) -> bool:
        val = await self.get_setting("force_join")
        return val == "1"

    # ---------- پیام‌های پشتیبانی ----------
    async def add_support_message(self, user_id: int, username: str, first_name: str, message_text: str, message_type: str = "text"):
        await self.conn.execute(
            """
            INSERT INTO support_messages (user_id, username, first_name, message_text, message_type, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, first_name, message_text, message_type, int(time.time())),
        )
        await self.conn.commit()

    async def get_support_messages(self, filter_type: str = "all", limit: int = 10, offset: int = 0) -> List[aiosqlite.Row]:
        now = int(time.time())
        if filter_type == "today":
            since = now - 86400
        elif filter_type == "week":
            since = now - 604800
        else:
            since = 0
        cur = await self.conn.execute(
            "SELECT * FROM support_messages WHERE sent_at >= ? ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            (since, limit, offset),
        )
        return await cur.fetchall()

    async def count_support_messages(self, filter_type: str = "all") -> int:
        now = int(time.time())
        if filter_type == "today":
            since = now - 86400
        elif filter_type == "week":
            since = now - 604800
        else:
            since = 0
        cur = await self.conn.execute(
            "SELECT COUNT(*) AS c FROM support_messages WHERE sent_at >= ?", (since,)
        )
        row = await cur.fetchone()
        return row["c"]


db = Database(config.DB_PATH)
