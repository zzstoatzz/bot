"""Prepare Bluesky image embeds and matching policy-judge input."""

import io
from typing import Annotated

from atproto_client import models
from atproto_client.models.blob_ref import BlobRef
from PIL import Image
from pydantic import BaseModel, Field
from pydantic_ai import BinaryContent

from bot.core.media import fetch_blob_bytes

MAX_IMAGE_BYTES = 1_000_000


class PostImage(BaseModel):
    blob: Annotated[
        BlobRef, Field(description="blob object returned by generate_image, unchanged")
    ]
    alt: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2000,
            description="image description, including visible meme text",
        ),
    ]


async def prepare_images(did: str, images: list[PostImage]):
    """Read own-PDS blobs so the judge sees exactly what will be attached."""
    if not 1 <= len(images) <= 4:
        raise ValueError("attach between one and four images")
    embeds = []
    pixels = []
    descriptions = []
    for item in images:
        blob = item.blob
        if not 0 < blob.size <= MAX_IMAGE_BYTES:
            raise ValueError("image exceeds the 1MB attachment limit")
        ref = blob.model_dump(mode="json", by_alias=True)["ref"]
        if not isinstance(ref, dict) or not ref.get("$link"):
            raise ValueError(
                "use the original blob reference returned by generate_image"
            )
        cid = ref["$link"]
        data = await fetch_blob_bytes(did, cid, max_bytes=MAX_IMAGE_BYTES)
        if len(data) != blob.size:
            raise ValueError("image size does not match the blob reference")
        with Image.open(io.BytesIO(data)) as image:
            mime = Image.MIME.get(image.format or "")
            if (
                mime not in {"image/jpeg", "image/png", "image/webp"}
                or mime != blob.mime_type
            ):
                raise ValueError(
                    "attachment must be a matching JPEG, PNG, or WebP blob"
                )
            width, height = image.size
            image.verify()
        embeds.append(
            models.AppBskyEmbedImages.Image(
                image=blob,
                alt=item.alt,
                aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(
                    width=width, height=height
                ),
            )
        )
        pixels.append(BinaryContent(data=data, media_type=mime))
        descriptions.append(f"[attached image {cid}: {item.alt}]")
    return (
        models.AppBskyEmbedImages.Main(images=embeds),
        pixels,
        "\n".join(descriptions),
    )
