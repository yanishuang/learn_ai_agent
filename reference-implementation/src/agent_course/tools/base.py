"""Strict, permission-aware tool building blocks."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from agent_course.core import (
    PermissionDeniedError,
    RunContext,
    ToolDefinition,
    ToolResult,
)


class StrictToolArguments(BaseModel):
    """Base model for arguments originating from an untrusted model."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


ArgumentsT = TypeVar("ArgumentsT", bound=StrictToolArguments)


class StructuredTool(ABC, Generic[ArgumentsT]):
    """Validate model input and authorize trusted context before execution."""

    name: str
    description: str
    permission: str
    arguments_type: type[ArgumentsT]

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.arguments_type.model_json_schema(),
        )

    async def execute(
        self,
        arguments: dict,
        *,
        context: RunContext,
    ) -> ToolResult:
        try:
            validated = self.arguments_type.model_validate(arguments)
        except ValidationError:
            return ToolResult(
                name=self.name,
                code="INVALID_ARGUMENTS",
                success=False,
                error="tool arguments failed validation",
            )

        try:
            context.require(self.permission)
        except PermissionDeniedError:
            return ToolResult(
                name=self.name,
                code="PERMISSION_DENIED",
                success=False,
                error="required permission is missing",
            )

        try:
            return await self._execute(validated, context)
        except Exception:
            return ToolResult(
                name=self.name,
                code="TOOL_ERROR",
                success=False,
                error="tool handler failed",
            )

    @abstractmethod
    async def _execute(
        self,
        arguments: ArgumentsT,
        context: RunContext,
    ) -> ToolResult:
        """Run the trusted handler with validated arguments."""


__all__ = ["StrictToolArguments", "StructuredTool"]
