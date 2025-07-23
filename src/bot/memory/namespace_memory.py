"""Namespace-based memory implementation using TurboPuffer"""

import hashlib
from datetime import datetime
from enum import Enum
from typing import ClassVar

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from turbopuffer import Turbopuffer

from bot.config import settings


class MemoryType(str, Enum):
    """Types of memories for categorization"""

    PERSONALITY = "personality"
    GUIDELINE = "guideline"
    CAPABILITY = "capability"
    USER_FACT = "user_fact"
    CONVERSATION = "conversation"
    OBSERVATION = "observation"
    SYSTEM = "system"


class MemoryEntry(BaseModel):
    """A single memory entry"""

    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class NamespaceMemory:
    """Simple namespace-based memory using TurboPuffer

    We use separate namespaces for different types of memories:
    - core: Bot personality, guidelines, capabilities
    - users: Per-user conversation history and facts
    """

    NAMESPACES: ClassVar[dict[str, str]] = {
        "core": "phi-core",
        "users": "phi-users",
    }

    def __init__(self, api_key: str | None = None):
        self.client = Turbopuffer(api_key=api_key, region=settings.turbopuffer_region)
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Initialize namespace clients
        self.namespaces = {}
        for key, ns_name in self.NAMESPACES.items():
            self.namespaces[key] = self.client.namespace(ns_name)

    def get_user_namespace(self, handle: str):
        """Get or create user-specific namespace"""
        clean_handle = handle.replace(".", "_").replace("@", "").replace("-", "_")
        ns_name = f"{self.NAMESPACES['users']}-{clean_handle}"
        return self.client.namespace(ns_name)

    def _generate_id(self, namespace: str, label: str, content: str = "") -> str:
        """Generate deterministic ID for memory entry"""
        data = f"{namespace}-{label}-{content[:50]}-{datetime.now().date()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using OpenAI"""
        response = await self.openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding

    async def store_core_memory(
        self,
        label: str,
        content: str,
        memory_type: MemoryType = MemoryType.SYSTEM,
        char_limit: int = 10_000,
    ):
        """Store or update core memory block"""
        # Enforce character limit
        if len(content) > char_limit:
            content = content[: char_limit - 3] + "..."

        block_id = self._generate_id("core", label)

        self.namespaces["core"].write(
            upsert_rows=[
                {
                    "id": block_id,
                    "vector": await self._get_embedding(content),
                    "label": label,
                    "type": memory_type.value,
                    "content": content,
                    "importance": 1.0,  # Core memories are always important
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
            ],
            distance_metric="cosine_distance",
            schema={
                "label": {"type": "string"},
                "type": {"type": "string"},
                "content": {"type": "string", "full_text_search": True},
                "importance": {"type": "float"},
                "created_at": {"type": "string"},
                "updated_at": {"type": "string"},
            },
        )

    async def get_core_memories(self) -> list[MemoryEntry]:
        """Get all core memories"""
        response = self.namespaces["core"].query(
            rank_by=("vector", "ANN", [0.5] * 1536),
            top_k=100,
            include_attributes=["label", "type", "content", "importance", "created_at"],
        )

        entries = []
        if response.rows:
            for row in response.rows:
                entries.append(
                    MemoryEntry(
                        id=row.id,
                        content=row.content,
                        metadata={
                            "label": row.label,
                            "type": row.type,
                            "importance": getattr(row, "importance", 1.0),
                        },
                        created_at=datetime.fromisoformat(row.created_at),
                    )
                )

        return entries

    # User memory operations
    async def store_user_memory(
        self,
        handle: str,
        content: str,
        memory_type: MemoryType = MemoryType.CONVERSATION,
    ):
        """Store memory for a specific user"""
        user_ns = self.get_user_namespace(handle)
        entry_id = self._generate_id(f"user-{handle}", memory_type.value, content)

        user_ns.write(
            upsert_rows=[
                {
                    "id": entry_id,
                    "vector": await self._get_embedding(content),
                    "type": memory_type.value,
                    "content": content,
                    "handle": handle,
                    "created_at": datetime.now().isoformat(),
                }
            ],
            distance_metric="cosine_distance",
            schema={
                "type": {"type": "string"},
                "content": {"type": "string", "full_text_search": True},
                "handle": {"type": "string"},
                "created_at": {"type": "string"},
            },
        )

    async def get_user_memories(
        self, user_handle: str, limit: int = 50
    ) -> list[MemoryEntry]:
        """Get memories for a specific user"""
        user_ns = self.get_user_namespace(user_handle)

        try:
            response = user_ns.query(
                rank_by=("vector", "ANN", [0.5] * 1536),
                top_k=limit,
                include_attributes=["type", "content", "created_at"],
            )

            entries = []
            if response.rows:
                for row in response.rows:
                    entries.append(
                        MemoryEntry(
                            id=row.id,
                            content=row.content,
                            metadata={"user_handle": user_handle, "type": row.type},
                            created_at=datetime.fromisoformat(row.created_at),
                        )
                    )

            return sorted(entries, key=lambda x: x.created_at, reverse=True)

        except Exception as e:
            # If namespace doesn't exist, return empty list
            if "was not found" in str(e):
                return []
            raise

    # Main method used by the bot
    async def build_conversation_context(
        self, user_handle: str, include_core: bool = True
    ) -> str:
        """Build complete context for a conversation"""
        parts = []

        # Core memories (personality, guidelines, etc.)
        if include_core:
            core_memories = await self.get_core_memories()
            if core_memories:
                parts.append("[CORE IDENTITY AND GUIDELINES]")
                for mem in sorted(
                    core_memories,
                    key=lambda x: x.metadata.get("importance", 0),
                    reverse=True,
                ):
                    label = mem.metadata.get("label", "unknown")
                    parts.append(f"[{label}] {mem.content}")

        # User-specific memories
        user_memories = await self.get_user_memories(user_handle)
        if user_memories:
            parts.append(f"\n[USER CONTEXT - @{user_handle}]")
            for mem in user_memories[:10]:  # Most recent 10
                parts.append(f"- {mem.content}")
        elif include_core:
            parts.append(f"\n[USER CONTEXT - @{user_handle}]")
            parts.append("No previous interactions with this user.")

        return "\n".join(parts)
