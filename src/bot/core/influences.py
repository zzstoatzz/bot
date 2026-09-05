"""Phi-owned influence choices; separate from personality and operator likes."""

from datetime import datetime
from typing import Literal

import httpx
from atproto import AtUri
from atproto_client import models
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

COLLECTION = "io.zzstoatzz.phi.influence"


class Influence(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    subject: models.ComAtprotoRepoStrongRef.Main
    reason: str = Field(min_length=1, max_length=800)
    works: list[HttpUrl] = Field(default_factory=list, max_length=10)
    active: bool
    selected_by: Literal["phi", "operator"] = Field(alias="selectedBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @model_validator(mode="after")
    def profile_identity(self):
        target = AtUri.from_str(self.subject.uri)
        if (
            not target.host.startswith("did:")
            or target.collection != "app.bsky.actor.profile"
            or target.rkey != "self"
        ):
            raise ValueError(
                "subject must pin an actor's DID-based profile/self record"
            )
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("choice timestamps must include a timezone")
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt cannot precede createdAt")
        return self

    @property
    def actor_did(self) -> str:
        return AtUri.from_str(self.subject.uri).host


class InfluenceVersion(BaseModel):
    uri: str
    cid: str
    value: Influence


async def read_influences(
    client: httpx.AsyncClient, pds: str, repo_did: str
) -> list[InfluenceVersion]:
    """Read every choice, including retired records, without guessing on failures."""
    choices = []
    cursor = None
    seen = set()
    while True:
        params = {"repo": repo_did, "collection": COLLECTION, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        response = await client.get(
            f"{pds.rstrip('/')}/xrpc/com.atproto.repo.listRecords", params=params
        )
        response.raise_for_status()
        page = response.json()
        for record in page["records"]:
            version = InfluenceVersion.model_validate(record)
            uri = AtUri.from_str(version.uri)
            if uri.host != repo_did or uri.collection != COLLECTION:
                raise ValueError(
                    "influence record belongs to another repository or collection"
                )
            choices.append(version)
        cursor = page.get("cursor")
        if not cursor:
            return choices
        if cursor in seen:
            raise ValueError("influence pagination repeated its cursor")
        seen.add(cursor)
