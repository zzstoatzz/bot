"""Bot status tracking"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BotStatus:
    """Tracks bot status and activity"""

    start_time: datetime = field(default_factory=datetime.now)
    mentions_received: int = 0
    responses_sent: int = 0
    errors: int = 0
    last_mention_time: datetime | None = None
    last_response_time: datetime | None = None
    ai_enabled: bool = False
    polling_active: bool = False

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def uptime_str(self) -> str:
        """Get human-readable uptime"""
        seconds = int(self.uptime_seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")

        return " ".join(parts)

    def record_mention(self):
        """Record a mention received"""
        self.mentions_received += 1
        self.last_mention_time = datetime.now()

    def record_response(self):
        """Record a response sent"""
        self.responses_sent += 1
        self.last_response_time = datetime.now()

    def record_error(self):
        """Record an error"""
        self.errors += 1


# Global status instance
bot_status = BotStatus()
