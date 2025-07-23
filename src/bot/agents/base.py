"""Base classes for bot agents"""

from enum import Enum

from pydantic import BaseModel, Field


class Action(str, Enum):
    """Actions the bot can take in response to a notification"""

    REPLY = "reply"  # Post a reply
    LIKE = "like"  # Like the post
    REPOST = "repost"  # Repost/reblast
    IGNORE = "ignore"  # Don't respond


class Response(BaseModel):
    """Bot response to a notification"""

    action: Action = Field(description="What action to take")
    text: str | None = Field(
        default=None, description="Reply text if action=reply (max 300 chars)"
    )
    reason: str | None = Field(
        default=None,
        description="Brief explanation for the action (mainly for logging)",
    )
