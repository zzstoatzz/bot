"""HTML page templates and JSON data endpoints for phi's web UI."""

from bot.ui.activity import router as activity_router
from bot.ui.pages import home_page, memory_page, status_page

__all__ = [
    "activity_router",
    "home_page",
    "memory_page",
    "status_page",
]
