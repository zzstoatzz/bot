"""Manage bot profile status updates"""

import logging
from enum import Enum

from atproto import Client

logger = logging.getLogger("bot.profile_manager")


class OnlineStatus(str, Enum):
    """Online status indicators for bot profile"""
    ONLINE = "🟢 online"
    OFFLINE = "🔴 offline"


class ProfileManager:
    """Manages bot profile updates"""

    def __init__(self, client: Client):
        self.client = client
        self.base_bio: str | None = None
        self.current_record: dict | None = None

    async def initialize(self):
        """Get the current profile and store base bio"""
        try:
            # Get current profile record
            response = self.client.com.atproto.repo.get_record(
                {
                    "repo": self.client.me.did,
                    "collection": "app.bsky.actor.profile",
                    "rkey": "self",
                }
            )

            self.current_record = response
            self.base_bio = response.value.description or ""
            logger.info(f"Initialized with base bio: {self.base_bio}")

        except Exception as e:
            logger.error(f"Failed to get current profile: {e}")
            # Set a default if we can't get the current one
            self.base_bio = "i am a bot - contact my operator @zzstoatzz.io with any questions"

    async def set_online_status(self, is_online: bool):
        """Update the bio to reflect online/offline status"""
        try:
            if not self.base_bio:
                await self.initialize()

            # Create status suffix
            status = OnlineStatus.ONLINE if is_online else OnlineStatus.OFFLINE

            # Get the actual base bio by removing any existing status
            bio_without_status = self.base_bio
            # Remove both correct status values and any enum string representations
            for old_status in OnlineStatus:
                bio_without_status = bio_without_status.replace(
                    f" • {old_status.value}", ""
                ).strip()
                # Also clean up any enum string representations that got in there
                bio_without_status = bio_without_status.replace(
                    f" • {old_status.name}", ""
                ).strip()
                bio_without_status = bio_without_status.replace(
                    f" • OnlineStatus.{old_status.name}", ""
                ).strip()

            # Store cleaned base bio for next time
            if bio_without_status != self.base_bio:
                self.base_bio = bio_without_status

            # Add new status
            new_bio = f"{bio_without_status} • {status.value}"

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

            logger.info(f"Updated profile bio: {new_bio}")

        except Exception as e:
            logger.error(f"Failed to update profile status: {e}")
            # Don't fail the whole app if profile update fails
