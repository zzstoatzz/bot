"""Validated types for atproto records phi creates."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field


# --- validators ---


def _validate_entity_ref(v: str) -> str:
    """Must be a URL or at:// URI."""
    if v.startswith(("at://", "https://", "http://")):
        return v
    raise ValueError(f"must be a URL or at:// URI, got: {v!r}")


EntityRef = Annotated[str, AfterValidator(_validate_entity_ref)]

ConnectionType = Literal[
    "related",
    "supports",
    "opposes",
    "addresses",
    "helpful",
    "explainer",
    "leads_to",
    "supplements",
]


# --- content models ---


class NoteContent(BaseModel):
    """Content for a NOTE-type cosmik card."""

    text: str = Field(max_length=10000)


class UrlContent(BaseModel):
    """Content for a URL-type cosmik card."""

    url: EntityRef
    title: str | None = None
    description: str | None = None


# --- records ---


class CosmikConnection(BaseModel):
    """network.cosmik.connection record.

    A directed edge between two entities (URLs or cards) with optional
    semantic type and note. Schema lives at:
    at://cosmik.network/com.atproto.lexicon.schema/network.cosmik.connection
    """

    source: EntityRef = Field(description="source entity — URL or at:// URI")
    target: EntityRef = Field(description="target entity — URL or at:// URI")
    connection_type: ConnectionType | None = Field(
        default=None,
        alias="connectionType",
        description="semantic relationship type",
    )
    note: str | None = Field(
        default=None,
        max_length=1000,
        description="optional context about the connection",
    )

    def to_record(self) -> dict:
        """Serialize to the shape expected by com.atproto.repo.createRecord."""
        record: dict = {"source": self.source, "target": self.target}
        if self.connection_type:
            record["connectionType"] = self.connection_type
        if self.note:
            record["note"] = self.note
        return record


class CosmikNoteCard(BaseModel):
    """network.cosmik.card record — NOTE type.

    A text note stored on-protocol as a cosmik card. Indexed by semble.
    """

    type: Literal["NOTE"] = "NOTE"
    content: NoteContent

    def to_record(self) -> dict:
        return {"type": self.type, "content": {"text": self.content.text}}


class CosmikUrlCard(BaseModel):
    """network.cosmik.card record — URL type.

    A bookmarked URL stored on-protocol as a cosmik card. Indexed by semble.
    """

    type: Literal["URL"] = "URL"
    content: UrlContent

    def to_record(self) -> dict:
        record: dict = {"type": self.type, "content": {"url": self.content.url}}
        if self.content.title:
            record["content"]["title"] = self.content.title
        if self.content.description:
            record["content"]["description"] = self.content.description
        return record
