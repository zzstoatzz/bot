from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class CachedStaticFiles(StaticFiles):
    """SvelteKit names everything under `_app/immutable/` by content hash, so
    those files never change; the html shell is what points at new ones."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("_app/immutable/"):
                response.headers["Cache-Control"] = (
                    "public, max-age=31536000, immutable"
                )
            elif response.media_type == "text/html":
                response.headers["Cache-Control"] = "no-cache"
        return response
