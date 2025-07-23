"""Simple SQLite database for storing thread history"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class ThreadDatabase:
    """Simple database for storing Bluesky thread conversations"""

    def __init__(self, db_path: Path = Path("threads.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS thread_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_uri TEXT NOT NULL,
                    author_handle TEXT NOT NULL,
                    author_did TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    post_uri TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_uri 
                ON thread_messages(thread_uri)
            """)
            
            # Approval requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_type TEXT NOT NULL,
                    request_data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    resolver_comment TEXT,
                    applied_at TIMESTAMP,
                    CHECK (status IN ('pending', 'approved', 'denied', 'expired'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_approval_status 
                ON approval_requests(status)
            """)

    @contextmanager
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_message(
        self,
        thread_uri: str,
        author_handle: str,
        author_did: str,
        message_text: str,
        post_uri: str,
    ):
        """Add a message to a thread"""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO thread_messages 
                (thread_uri, author_handle, author_did, message_text, post_uri)
                VALUES (?, ?, ?, ?, ?)
            """,
                (thread_uri, author_handle, author_did, message_text, post_uri),
            )

    def get_thread_messages(self, thread_uri: str) -> list[dict[str, Any]]:
        """Get all messages in a thread, ordered chronologically"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM thread_messages 
                WHERE thread_uri = ?
                ORDER BY created_at ASC
            """,
                (thread_uri,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def get_thread_context(self, thread_uri: str) -> str:
        """Get thread messages formatted for AI context"""
        messages = self.get_thread_messages(thread_uri)

        if not messages:
            return "No previous messages in this thread."

        context_parts = ["Previous messages in this thread:"]
        for msg in messages:
            context_parts.append(f"@{msg['author_handle']}: {msg['message_text']}")

        return "\n".join(context_parts)
    
    def create_approval_request(
        self, request_type: str, request_data: str
    ) -> int:
        """Create a new approval request and return its ID"""
        import json
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO approval_requests (request_type, request_data)
                VALUES (?, ?)
                """,
                (request_type, json.dumps(request_data) if isinstance(request_data, dict) else request_data),
            )
            return cursor.lastrowid
    
    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending approval requests"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM approval_requests 
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def resolve_approval(
        self, approval_id: int, approved: bool, comment: str = ""
    ) -> bool:
        """Resolve an approval request"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE approval_requests 
                SET status = ?, resolved_at = CURRENT_TIMESTAMP, resolver_comment = ?
                WHERE id = ? AND status = 'pending'
                """,
                ("approved" if approved else "denied", comment, approval_id),
            )
            return cursor.rowcount > 0
    
    def get_approval_by_id(self, approval_id: int) -> dict[str, Any] | None:
        """Get a specific approval request by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE id = ?",
                (approval_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


# Global database instance
thread_db = ThreadDatabase()
