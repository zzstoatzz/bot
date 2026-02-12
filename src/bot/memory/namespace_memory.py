"""Namespace-based memory with structured observation extraction."""

import hashlib
import logging
from datetime import datetime
from typing import ClassVar

from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from turbopuffer import Turbopuffer

from bot.config import settings

logger = logging.getLogger("bot.memory")


class Observation(BaseModel):
    """A single extracted fact about a user or conversation."""

    content: str  # "interested in rust programming"
    tags: list[str]  # ["interest", "programming"]


class ExtractionResult(BaseModel):
    """Result of extracting observations from a conversation."""

    observations: list[Observation] = []


EXTRACTION_SYSTEM_PROMPT = """\
extract factual observations about the USER from this conversation exchange.
focus on things the user explicitly stated or clearly demonstrated:
- interests they expressed (not topics the bot brought up)
- preferences, opinions, facts about themselves
- what they asked about and WHY (e.g. "curious about current events" not the specific events listed)
skip:
- greetings, filler, things only meaningful in the moment
- content the bot retrieved or generated (trending topics, search results, etc.) — those are NOT the user's interests
- circumstantial details from bot tool output
each observation should be a standalone fact useful in a future conversation.
use short, lowercase tags. return an empty list if nothing is worth extracting.
deduplicate against the existing observations provided."""

_extraction_agent: Agent[None, ExtractionResult] | None = None


def get_extraction_agent() -> Agent[None, ExtractionResult]:
    global _extraction_agent
    if _extraction_agent is None:
        _extraction_agent = Agent(
            name="observation-extractor",
            model=f"anthropic:{settings.extraction_model}",
            output_type=ExtractionResult,
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )
    return _extraction_agent

EPISODIC_SCHEMA = {
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "source": {"type": "string", "filterable": True},  # "tool", "conversation"
    "created_at": {"type": "string"},
}

USER_NAMESPACE_SCHEMA = {
    "kind": {"type": "string", "filterable": True},
    "content": {"type": "string", "full_text_search": True},
    "tags": {"type": "[]string", "filterable": True},
    "created_at": {"type": "string"},
}


class NamespaceMemory:
    """Namespace-based memory using TurboPuffer with structured observation extraction.

    Each user gets their own namespace with two kinds of rows:
    - kind: "interaction" - raw log of what happened
    - kind: "observation" - extracted facts (one per observation)
    """

    NAMESPACES: ClassVar[dict[str, str]] = {
        "core": "phi-core",
        "users": "phi-users",
        "episodic": "phi-episodic",
    }

    def __init__(self, api_key: str | None = None):
        self.client = Turbopuffer(api_key=api_key, region=settings.turbopuffer_region)
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        self.namespaces = {}
        for key, ns_name in self.NAMESPACES.items():
            self.namespaces[key] = self.client.namespace(ns_name)

    async def close(self):
        """Close the async OpenAI client."""
        await self.openai_client.close()

    def get_user_namespace(self, handle: str):
        """Get or create user-specific namespace."""
        clean_handle = handle.replace(".", "_").replace("@", "").replace("-", "_")
        ns_name = f"{self.NAMESPACES['users']}-{clean_handle}"
        return self.client.namespace(ns_name)

    def _generate_id(self, namespace: str, label: str, content: str = "") -> str:
        """Generate unique ID for a memory row."""
        timestamp = datetime.now().isoformat()
        data = f"{namespace}-{label}-{timestamp}-{content}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using OpenAI."""
        response = await self.openai_client.embeddings.create(
            model="text-embedding-3-small", input=text
        )
        return response.data[0].embedding

    # --- core memory (unchanged) ---

    async def store_core_memory(self, label: str, content: str, memory_type: str = "system", char_limit: int = 10_000):
        """Store or update core memory block."""
        if len(content) > char_limit:
            content = content[: char_limit - 3] + "..."

        block_id = self._generate_id("core", label)

        self.namespaces["core"].write(
            upsert_rows=[
                {
                    "id": block_id,
                    "vector": await self._get_embedding(content),
                    "label": label,
                    "type": memory_type,
                    "content": content,
                    "importance": 1.0,
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

    async def get_core_memories(self) -> list[dict]:
        """Get all core memories."""
        response = self.namespaces["core"].query(
            rank_by=("vector", "ANN", [0.5] * 1536),
            top_k=100,
            include_attributes=["label", "type", "content", "importance", "created_at"],
        )

        entries = []
        if response.rows:
            for row in response.rows:
                entries.append({
                    "id": row.id,
                    "content": row.content,
                    "label": getattr(row, "label", "unknown"),
                    "type": getattr(row, "type", "system"),
                    "importance": getattr(row, "importance", 1.0),
                    "created_at": row.created_at,
                })
        return entries

    # --- user memory ---

    async def store_interaction(self, handle: str, user_text: str, bot_text: str):
        """Store a raw interaction log (user message + bot reply)."""
        user_ns = self.get_user_namespace(handle)
        content = f"user: {user_text}\nbot: {bot_text}"
        entry_id = self._generate_id(f"user-{handle}", "interaction", content)

        user_ns.write(
            upsert_rows=[
                {
                    "id": entry_id,
                    "vector": await self._get_embedding(content),
                    "kind": "interaction",
                    "content": content,
                    "tags": [],
                    "created_at": datetime.now().isoformat(),
                }
            ],
            distance_metric="cosine_distance",
            schema=USER_NAMESPACE_SCHEMA,
        )

    async def store_observations(self, handle: str, observations: list[Observation]):
        """Store extracted observations as individual rows."""
        if not observations:
            return

        user_ns = self.get_user_namespace(handle)
        rows = []
        for obs in observations:
            entry_id = self._generate_id(f"user-{handle}", "observation", obs.content)
            rows.append({
                "id": entry_id,
                "vector": await self._get_embedding(obs.content),
                "kind": "observation",
                "content": obs.content,
                "tags": obs.tags,
                "created_at": datetime.now().isoformat(),
            })

        user_ns.write(
            upsert_rows=rows,
            distance_metric="cosine_distance",
            schema=USER_NAMESPACE_SCHEMA,
        )

    async def extract_and_store(self, handle: str, user_text: str, bot_text: str):
        """Extract observations from an exchange and store them. Meant to be fire-and-forget."""
        try:
            # fetch existing observations for dedup context
            existing = await self._get_observations(handle, top_k=20)
            existing_text = "\n".join(f"- {o}" for o in existing) if existing else "none yet"

            prompt = (
                f"existing observations about this user:\n{existing_text}\n\n"
                f"new exchange:\nuser: {user_text}\nbot: {bot_text}"
            )
            result = await get_extraction_agent().run(prompt)
            if result.output.observations:
                await self.store_observations(handle, result.output.observations)
                obs_summary = ", ".join(o.content[:60] for o in result.output.observations)
                logger.info(f"extracted {len(result.output.observations)} observations for @{handle}: {obs_summary}")
            else:
                logger.debug(f"no new observations for @{handle}")
        except Exception as e:
            logger.warning(f"observation extraction failed for @{handle}: {e}")

    async def _get_observations(self, handle: str, top_k: int = 20) -> list[str]:
        """Get existing observation content strings for a user."""
        user_ns = self.get_user_namespace(handle)
        try:
            response = user_ns.query(
                rank_by=("vector", "ANN", [0.5] * 1536),
                top_k=top_k,
                filters={"kind": ["Eq", "observation"]},
                include_attributes=["content"],
            )
            if response.rows:
                return [row.content for row in response.rows]
        except Exception as e:
            if "attribute not found" in str(e):
                return []  # old namespace without kind column - no observations yet
            if "was not found" not in str(e):
                raise
        return []

    async def build_user_context(self, handle: str, query_text: str, include_core: bool = True) -> str:
        """Build context for a conversation from observations and recent interactions."""
        parts = []

        if include_core:
            core_memories = await self.get_core_memories()
            if core_memories:
                parts.append("[CORE IDENTITY AND GUIDELINES]")
                for mem in sorted(core_memories, key=lambda x: x.get("importance", 0), reverse=True):
                    label = mem.get("label", "unknown")
                    parts.append(f"[{label}] {mem['content']}")

        user_ns = self.get_user_namespace(handle)
        try:
            query_embedding = await self._get_embedding(query_text)

            observations: list[str] = []
            interactions: list[str] = []

            try:
                # semantic search for relevant observations
                obs_response = user_ns.query(
                    rank_by=("vector", "ANN", query_embedding),
                    top_k=10,
                    filters={"kind": ["Eq", "observation"]},
                    include_attributes=["content", "tags"],
                )
                if obs_response.rows:
                    observations = [row.content for row in obs_response.rows]

                # recent interactions for conversational context
                interaction_response = user_ns.query(
                    rank_by=("vector", "ANN", query_embedding),
                    top_k=5,
                    filters={"kind": ["Eq", "interaction"]},
                    include_attributes=["content", "created_at"],
                )
                if interaction_response.rows:
                    interactions = [row.content for row in interaction_response.rows]
            except Exception as e:
                if "attribute not found" not in str(e):
                    raise
                # old namespace without kind column - fall back to unfiltered search
                logger.debug(f"kind attribute not found for @{handle}, falling back to unfiltered search")
                response = user_ns.query(
                    rank_by=("vector", "ANN", query_embedding),
                    top_k=10,
                    include_attributes=["content"],
                )
                if response.rows:
                    interactions = [row.content for row in response.rows]

            if observations:
                parts.append(f"\n[KNOWN FACTS ABOUT @{handle}]")
                for obs in observations:
                    parts.append(f"- {obs}")

            if interactions:
                parts.append(f"\n[RECENT INTERACTIONS WITH @{handle}]")
                for interaction in interactions:
                    parts.append(f"- {interaction}")

            if not observations and not interactions:
                parts.append(f"\n[USER CONTEXT - @{handle}]")
                parts.append("no previous interactions with this user.")

        except Exception as e:
            if "was not found" not in str(e):
                logger.warning(f"failed to retrieve user context for @{handle}: {e}")
            parts.append(f"\n[USER CONTEXT - @{handle}]")
            parts.append("no previous interactions with this user.")

        return "\n".join(parts)

    async def search(self, handle: str, query: str, top_k: int = 10) -> list[dict]:
        """Unfiltered semantic search across all memory kinds for a user."""
        user_ns = self.get_user_namespace(handle)
        try:
            query_embedding = await self._get_embedding(query)
            response = user_ns.query(
                rank_by=("vector", "ANN", query_embedding),
                top_k=top_k,
                include_attributes=["content", "created_at"],
            )
            results = []
            if response.rows:
                for row in response.rows:
                    results.append({
                        "kind": getattr(row, "kind", "unknown"),
                        "content": row.content,
                        "tags": getattr(row, "tags", []),
                        "created_at": getattr(row, "created_at", ""),
                    })
            return results
        except Exception as e:
            if "was not found" in str(e):
                return []
            raise

    # --- episodic memory (phi's own world knowledge) ---

    async def store_episodic_memory(self, content: str, tags: list[str], source: str = "tool"):
        """Store an episodic memory — something phi learned about the world."""
        entry_id = self._generate_id("episodic", source, content)
        self.namespaces["episodic"].write(
            upsert_rows=[
                {
                    "id": entry_id,
                    "vector": await self._get_embedding(content),
                    "content": content,
                    "tags": tags,
                    "source": source,
                    "created_at": datetime.now().isoformat(),
                }
            ],
            distance_metric="cosine_distance",
            schema=EPISODIC_SCHEMA,
        )
        logger.info(f"stored episodic memory [{source}]: {content[:80]}")

    async def search_episodic(self, query: str, top_k: int = 10) -> list[dict]:
        """Semantic search over phi's episodic memories."""
        try:
            query_embedding = await self._get_embedding(query)
            response = self.namespaces["episodic"].query(
                rank_by=("vector", "ANN", query_embedding),
                top_k=top_k,
                include_attributes=["content", "tags", "source", "created_at"],
            )
            results = []
            if response.rows:
                for row in response.rows:
                    results.append({
                        "content": row.content,
                        "tags": getattr(row, "tags", []),
                        "source": getattr(row, "source", "unknown"),
                        "created_at": getattr(row, "created_at", ""),
                    })
            return results
        except Exception as e:
            if "was not found" in str(e):
                return []
            raise

    async def get_episodic_context(self, query_text: str, top_k: int = 5) -> str:
        """Get formatted episodic context for injection into conversation prompt."""
        results = await self.search_episodic(query_text, top_k=top_k)
        if not results:
            return ""
        lines = ["[PHI'S RELEVANT MEMORIES]"]
        for r in results:
            tags = f" [{', '.join(r['tags'])}]" if r.get("tags") else ""
            lines.append(f"- {r['content']}{tags}")
        return "\n".join(lines)

    async def after_interaction(self, handle: str, user_text: str, bot_text: str):
        """Post-interaction hook: store interaction then extract observations."""
        await self.store_interaction(handle, user_text, bot_text)
        await self.extract_and_store(handle, user_text, bot_text)
