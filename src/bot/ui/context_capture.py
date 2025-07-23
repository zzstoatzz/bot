"""Context capture system for visualizing phi's response context"""

import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

logger = logging.getLogger("bot.context")


@dataclass
class ContextComponent:
    """A component of phi's response context"""

    name: str
    type: Literal["personality", "memory", "thread", "mention", "user"]
    content: str
    size_chars: int
    metadata: dict[str, Any]
    timestamp: str


@dataclass
class ResponseContext:
    """Complete context for a single response"""

    response_id: str
    mention_text: str
    author_handle: str
    thread_uri: str | None
    generated_response: str
    components: list[ContextComponent]
    total_context_chars: int
    timestamp: str


class ContextCapture:
    """Captures and stores context information for responses"""

    def __init__(self, max_stored: int = 50):
        self.max_stored = max_stored
        self.responses: deque = deque(maxlen=max_stored)

    def capture_response_context(
        self,
        mention_text: str,
        author_handle: str,
        thread_uri: str | None,
        generated_response: str,
        components: list[dict[str, Any]],
    ) -> str:
        """Capture context for a response and return unique ID"""
        response_id = f"resp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # Convert components to ContextComponent objects
        context_components = []
        total_chars = 0

        for comp in components:
            component = ContextComponent(
                name=comp["name"],
                type=comp["type"],
                content=comp["content"],
                size_chars=len(comp["content"]),
                metadata=comp.get("metadata", {}),
                timestamp=datetime.now().isoformat(),
            )
            context_components.append(component)
            total_chars += component.size_chars

        # Create response context
        response_context = ResponseContext(
            response_id=response_id,
            mention_text=mention_text,
            author_handle=author_handle,
            thread_uri=thread_uri,
            generated_response=generated_response,
            components=context_components,
            total_context_chars=total_chars,
            timestamp=datetime.now().isoformat(),
        )

        # Store it
        self.responses.appendleft(response_context)

        logger.info(
            f"📊 Captured context for {response_id}: {len(components)} components, {total_chars} chars"
        )
        return response_id

    def get_response_context(self, response_id: str) -> ResponseContext | None:
        """Get context for a specific response"""
        for resp in self.responses:
            if resp.response_id == response_id:
                return resp
        return None

    def get_recent_responses(self, limit: int = 20) -> list[ResponseContext]:
        """Get recent response contexts"""
        return list(self.responses)[:limit]

    def to_dict(self, response_context: ResponseContext) -> dict[str, Any]:
        """Convert ResponseContext to dictionary for JSON serialization"""
        return asdict(response_context)


# Global instance
context_capture = ContextCapture()
