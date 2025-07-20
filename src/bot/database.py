"""Simple SQLite database for storing thread history"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from contextlib import contextmanager


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
        post_uri: str
    ):
        """Add a message to a thread"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO thread_messages 
                (thread_uri, author_handle, author_did, message_text, post_uri)
                VALUES (?, ?, ?, ?, ?)
            """, (thread_uri, author_handle, author_did, message_text, post_uri))
    
    def get_thread_messages(self, thread_uri: str) -> List[Dict[str, Any]]:
        """Get all messages in a thread, ordered chronologically"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM thread_messages 
                WHERE thread_uri = ?
                ORDER BY created_at ASC
            """, (thread_uri,))
            
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


# Global database instance
thread_db = ThreadDatabase()