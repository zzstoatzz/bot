"""Type definitions for agent context"""

from typing import TypedDict


class ConversationContext(TypedDict):
    """Context passed to agent tools via dependency injection"""
    thread_uri: str | None
    author_handle: str