"""Tenant-scoped deterministic order lookup tool."""

from pydantic import Field

from agent_course.core import RunContext, ToolResult
from agent_course.tools.base import StrictToolArguments, StructuredTool


class QueryOrderStatusArguments(StrictToolArguments):
    order_id: str = Field(min_length=1, max_length=64)


_ORDERS = {
    ("tenant-1", "O1001"): "shipped",
    ("tenant-1", "O1002"): "processing",
    ("tenant-2", "O1001"): "cancelled",
}


class QueryOrderStatusTool(StructuredTool[QueryOrderStatusArguments]):
    """Look up an order using identity supplied only by ``RunContext``."""

    name = "query_order_status"
    description = "Query an order status within the caller's tenant."
    permission = "orders:read"
    arguments_type = QueryOrderStatusArguments

    def __init__(self) -> None:
        self.execution_count = 0

    async def _execute(
        self,
        arguments: QueryOrderStatusArguments,
        context: RunContext,
    ) -> ToolResult:
        self.execution_count += 1
        status = _ORDERS.get((context.tenant_id, arguments.order_id))
        if status is None:
            return ToolResult(
                name=self.name,
                code="NOT_FOUND",
                success=False,
                error="order was not found in the caller's tenant",
            )
        return ToolResult(
            name=self.name,
            code="OK",
            success=True,
            output={
                "order_id": arguments.order_id,
                "status": status,
                "tenant_id": context.tenant_id,
                "requested_by": context.user_id,
            },
        )


__all__ = ["QueryOrderStatusArguments", "QueryOrderStatusTool"]
