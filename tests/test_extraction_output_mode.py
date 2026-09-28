"""The extractor runs on agent_model; its output must not force tool use.

A tool-mode output type makes pydantic-ai send tool_choice "any", which
Claude Sonnet 5.5 rejects with a 400 ("tool_choice: type "tool" and "any"
are not supported for this model").
"""

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from bot.agent import EXTRACTION_OUTPUT
from bot.memory.extraction import ExtractionResult


async def test_extractor_output_leaves_text_output_allowed():
    seen: list[AgentInfo] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(info)
        return ModelResponse(parts=[TextPart('{"observations": []}')])

    agent = Agent(FunctionModel(respond), output_type=EXTRACTION_OUTPUT)
    result = await agent.run("nothing worth keeping")

    assert result.output == ExtractionResult(observations=[])
    assert seen[0].allow_text_output
    assert seen[0].output_tools == []
