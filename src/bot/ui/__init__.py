"""JSON data endpoints backing the frontend.

The HTML pages used to live here as python templates (home_page,
status_page, memory_page) but have been replaced by the SvelteKit
frontend in `bot/web/`. This module now only exposes the API routers
that the frontend (and external automations) consume.
"""

from bot.ui.activity import router as activity_router

__all__ = ["activity_router"]
