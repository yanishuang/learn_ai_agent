"""Deterministic input policy for the offline reference runner."""

import re
from typing import Literal

from pydantic import ConfigDict

from agent_course.core import FrozenModel, RunContext


class GuardrailDecision(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    code: Literal["ALLOW", "POLICY_DENIED"]
    reason: str | None = None


_HIGH_RISK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\[fixture:blocked-high-risk\]",
        r"绕过(?:权限|授权|安全|审计)",
        r"(?:导出|泄露|窃取).*(?:密钥|密码|令牌|客户数据)",
        r"bypass\s+(?:access|authorization|security|policy)",
        r"(?:export|leak|steal).*(?:secret|password|token|customer data)",
    )
)


class Guardrail:
    """Block a small, explicit set of high-risk requests before model use."""

    def check_input(
        self,
        question: str,
        context: RunContext,
    ) -> GuardrailDecision:
        del context
        if any(pattern.search(question) for pattern in _HIGH_RISK_PATTERNS):
            return GuardrailDecision(
                allowed=False,
                code="POLICY_DENIED",
                reason="high-risk request blocked by input policy",
            )
        return GuardrailDecision(allowed=True, code="ALLOW")


class DefaultGuardrail(Guardrail):
    """Named default used by application composition."""


__all__ = ["DefaultGuardrail", "Guardrail", "GuardrailDecision"]
