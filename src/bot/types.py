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


class StrongRef(BaseModel):
    """AT Protocol strong reference — uri + cid pair."""

    uri: EntityRef
    cid: str


class CosmikCollection(BaseModel):
    """network.cosmik.collection record — a named grouping of cards.

    Schema: at://cosmik.network/com.atproto.lexicon.schema/network.cosmik.collection
    """

    name: str = Field(max_length=100)
    access_type: Literal["OPEN", "CLOSED"] = "OPEN"
    description: str | None = Field(default=None, max_length=500)

    def to_record(self) -> dict:
        record: dict = {"name": self.name, "accessType": self.access_type}
        if self.description:
            record["description"] = self.description
        return record


class CosmikCollectionLink(BaseModel):
    """network.cosmik.collectionLink record — joins a card to a collection.

    Requires strongRefs (uri + cid) for both collection and card.
    """

    collection: StrongRef
    card: StrongRef
    added_by: str
    added_at: str

    def to_record(self) -> dict:
        return {
            "collection": {"uri": self.collection.uri, "cid": self.collection.cid},
            "card": {"uri": self.card.uri, "cid": self.card.cid},
            "addedBy": self.added_by,
            "addedAt": self.added_at,
        }
