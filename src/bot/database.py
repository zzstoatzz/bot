"""Simple SQLite database for approval requests"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class ThreadDatabase:
    """Database for storing approval requests (future self-modification features)"""

    def __init__(self, db_path: Path = Path("threads.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
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
                    thread_uri TEXT,
                    notified_at TIMESTAMP,
                    operator_notified_at TIMESTAMP,
                    CHECK (status IN ('pending', 'approved', 'denied', 'expired'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_approval_status 
                ON approval_requests(status)
            """)
            
            # Add missing columns if they don't exist (migrations)
            for column in ["notified_at", "operator_notified_at"]:
                try:
                    conn.execute(f"ALTER TABLE approval_requests ADD COLUMN {column} TIMESTAMP")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass

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

    def create_approval_request(
        self, request_type: str, request_data: str, thread_uri: str | None = None
    ) -> int:
        """Create a new approval request and return its ID"""
        import json
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO approval_requests (request_type, request_data, thread_uri)
                VALUES (?, ?, ?)
                """,
                (request_type, json.dumps(request_data) if isinstance(request_data, dict) else request_data, thread_uri),
            )
            return cursor.lastrowid
    
    def get_pending_approvals(self, include_notified: bool = True) -> list[dict[str, Any]]:
        """Get pending approval requests
        
        Args:
            include_notified: If False, only return approvals not yet notified to operator
        """
        with self._get_connection() as conn:
            if include_notified:
                cursor = conn.execute(
                    """
                    SELECT * FROM approval_requests 
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    """
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM approval_requests 
                    WHERE status = 'pending' AND operator_notified_at IS NULL
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
    
    def get_recently_applied_approvals(self) -> list[dict[str, Any]]:
        """Get approvals that were recently applied and need thread notification"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM approval_requests 
                WHERE status = 'approved' 
                AND applied_at IS NOT NULL
                AND thread_uri IS NOT NULL
                AND (notified_at IS NULL OR notified_at < applied_at)
                ORDER BY applied_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_approval_notified(self, approval_id: int) -> bool:
        """Mark that we've notified the thread about this approval"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE approval_requests SET notified_at = CURRENT_TIMESTAMP WHERE id = ?",
                (approval_id,),
            )
            return cursor.rowcount > 0
    
    def mark_operator_notified(self, approval_ids: list[int]) -> int:
        """Mark that we've notified the operator about these approvals"""
        if not approval_ids:
            return 0
        with self._get_connection() as conn:
            placeholders = ",".join("?" * len(approval_ids))
            cursor = conn.execute(
                f"UPDATE approval_requests SET operator_notified_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                approval_ids,
            )
            return cursor.rowcount


# Global database instance
thread_db = ThreadDatabase()
