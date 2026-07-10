"""Registry for explicit, structured tool dispatch."""

from collections.abc import Iterable

from agent_course.core import RunContext, ToolDefinition, ToolResult
from agent_course.tools.base import StructuredTool


class ToolRegistry:
    def __init__(self, tools: Iterable[StructuredTool] = ()) -> None:
        self._tools: dict[str, StructuredTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: StructuredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool is already registered: {tool.name}")
        self._tools[tool.name] = tool

    def definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: dict,
        context: RunContext,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                name=name,
                code="UNKNOWN_TOOL",
                success=False,
                error="tool is not registered",
            )
        return await tool.execute(arguments, context=context)


__all__ = ["ToolRegistry"]
