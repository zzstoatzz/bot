from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from bot.tools import blog
from bot.tools._helpers import PhiDeps


async def test_paused_blog_publish_never_authenticates_or_writes():
    registered = {}
    blog.register(
        SimpleNamespace(tool=lambda fn: registered.setdefault(fn.__name__, fn))
    )
    with (
        patch.object(
            blog,
            "get_override",
            AsyncMock(
                return_value={"active": True, "message": "operator paused publishing"}
            ),
        ),
        patch.object(blog.bot_client, "authenticate", AsyncMock()) as authenticate,
    ):
        result = await registered["publish_blog_post"](
            SimpleNamespace(deps=PhiDeps(author_handle="")), "title", "body"
        )
        assert "operator paused publishing" in result
        authenticate.assert_not_awaited()


def test_blog_tools_register_with_real_agent():
    agent = Agent(TestModel(), deps_type=PhiDeps)
    blog.register(agent)
    assert "publish_blog_post" in agent._function_toolset.tools
