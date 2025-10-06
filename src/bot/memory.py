"""Simple, interpretable SQLite-based memory for phi.

Design principles:
- Single SQLite database (threads.db)
- Plain text storage (no embeddings, no vector search)
- Interpretable: you can open the db and read everything
- Two types of memory: thread history and user facts
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class Memory:
    """Simple memory system using SQLite."""

    def __init__(self, db_path: Path = Path("threads.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Thread messages - full conversation history per thread
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_uri TEXT PRIMARY KEY,
                    messages TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User memories - simple facts about users
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_handle TEXT NOT NULL,
                    memory_text TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_handle
                ON user_memories(user_handle)
            """)

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Thread memory operations
    def add_thread_message(
        self, thread_uri: str, author_handle: str, message_text: str
    ):
        """Add a message to a thread's history."""
        with self._get_connection() as conn:
            # Get existing messages
            cursor = conn.execute(
                "SELECT messages FROM threads WHERE thread_uri = ?", (thread_uri,)
            )
            row = cursor.fetchone()

            # Parse existing messages or start fresh
            messages = json.loads(row["messages"]) if row else []

            # Append new message
            messages.append(
                {
                    "author": author_handle,
                    "text": message_text,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Update or insert
            conn.execute(
                """
                INSERT INTO threads (thread_uri, messages, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(thread_uri) DO UPDATE SET
                    messages = excluded.messages,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (thread_uri, json.dumps(messages)),
            )

    def get_thread_context(self, thread_uri: str, limit: int = 10) -> str:
        """Get formatted thread context for LLM."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT messages FROM threads WHERE thread_uri = ?", (thread_uri,)
            )
            row = cursor.fetchone()

            if not row:
                return "No previous messages in this thread."

            messages = json.loads(row["messages"])

            # Format last N messages
            recent = messages[-limit:] if len(messages) > limit else messages
            formatted = ["Previous messages in this thread:"]
            for msg in recent:
                formatted.append(f"@{msg['author']}: {msg['text']}")

            return "\n".join(formatted)

    # User memory operations
    def add_user_memory(
        self, user_handle: str, memory_text: str, memory_type: str = "fact"
    ):
        """Store a fact or preference about a user."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_memories (user_handle, memory_text, memory_type)
                VALUES (?, ?, ?)
                """,
                (user_handle, memory_text, memory_type),
            )

    def get_user_context(self, user_handle: str, limit: int = 10) -> str:
        """Get formatted user memory context for LLM."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT memory_text, memory_type, created_at
                FROM user_memories
                WHERE user_handle = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_handle, limit),
            )
            memories = cursor.fetchall()

            if not memories:
                return f"No previous interactions with @{user_handle}."

            formatted = [f"What I remember about @{user_handle}:"]
            for mem in memories:
                formatted.append(f"- {mem['memory_text']}")

            return "\n".join(formatted)

    def build_full_context(
        self, thread_uri: str, user_handle: str, thread_limit: int = 10
    ) -> str:
        """Build complete context for a conversation."""
        parts = []

        # Thread context
        thread_ctx = self.get_thread_context(thread_uri, limit=thread_limit)
        if thread_ctx != "No previous messages in this thread.":
            parts.append(thread_ctx)

        # User context
        user_ctx = self.get_user_context(user_handle)
        if user_ctx != f"No previous interactions with @{user_handle}.":
            parts.append(f"\n{user_ctx}")

        return "\n".join(parts) if parts else "No prior context available."
