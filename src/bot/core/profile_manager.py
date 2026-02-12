"""Manage bot profile status updates."""

import logging

from atproto import Client

logger = logging.getLogger("bot.profile_manager")

_ONLINE_SUFFIX = "\n\n🟢 user memory, world memory, thread context, atproto records, publication search, post search, trending"
_OFFLINE_SUFFIX = " • 🔴 offline"
_ALL_SUFFIXES = [_ONLINE_SUFFIX, _OFFLINE_SUFFIX]


class ProfileManager:
    """Manages bot profile updates."""

    def __init__(self, client: Client):
        self.client = client
        self.base_bio: str | None = None

    async def initialize(self):
        """Get the current profile and store base bio."""
        try:
            response = self.client.com.atproto.repo.get_record(
                {
                    "repo": self.client.me.did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                }
            )
            self.base_bio = response.value.description or ""
            logger.info(f"initialized with base bio: {self.base_bio}")
        except Exception as e:
            logger.error(f"failed to get current profile: {e}")
            self.base_bio = "i am a bot - contact my operator @zzstoatzz.io with any questions"

    async def set_online_status(self, is_online: bool):
        """Update the bio to reflect online/offline status and capabilities."""
        try:
            if not self.base_bio:
                await self.initialize()

            # Strip any existing suffix to get clean base bio
            clean = self.base_bio
            for suffix in _ALL_SUFFIXES:
                clean = clean.replace(suffix, "")
            clean = clean.rstrip()

            # Store cleaned base for next time
            self.base_bio = clean

            suffix = _ONLINE_SUFFIX if is_online else _OFFLINE_SUFFIX
            new_bio = f"{clean}{suffix}"

            # Get current record to preserve other fields
            current = self.client.com.atproto.repo.get_record(
                {
                    "repo": self.client.me.did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                }
            )

            # Create updated profile record
            profile_data = {"description": new_bio, "$type": "app.bsky.actor.profile"}

            # Preserve other fields if they exist
            if current.value.display_name:
                profile_data["displayName"] = current.value.display_name
            if current.value.avatar:
                profile_data["avatar"] = {
                    "$type": "blob",
                    "ref": {"$link": current.value.avatar.ref.link},
                    "mimeType": current.value.avatar.mime_type,
                    "size": current.value.avatar.size,
                }
            if current.value.banner:
                profile_data["banner"] = {
                    "$type": "blob",
                    "ref": {"$link": current.value.banner.ref.link},
                    "mimeType": current.value.banner.mime_type,
                    "size": current.value.banner.size,
                }

            # Update the profile
            self.client.com.atproto.repo.put_record(
                {
                    "repo": self.client.me.did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                    "record": profile_data,
                }
            )

            logger.info(f"updated profile bio: {new_bio}")

        except Exception as e:
            logger.error(f"failed to update profile status: {e}")
            # Don't fail the whole app if profile update fails
