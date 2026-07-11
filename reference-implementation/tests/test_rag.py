from pathlib import Path

from agent_course.core import RunContext
from agent_course.rag import DocumentChunk, InMemoryRetriever


SAMPLE_POLICY = Path(__file__).parents[1] / "sample-data" / "hr-policy.md"


def make_context(
    *,
    tenant_id: str = "tenant-1",
    user_id: str = "user-1",
) -> RunContext:
    return RunContext(
        user_id=user_id,
        tenant_id=tenant_id,
        request_id=f"request-{tenant_id}-{user_id}",
        permissions=frozenset({"knowledge:read"}),
    )


def test_search_uses_normalized_overlap_and_returns_a_real_source_quote() -> None:
    source = SAMPLE_POLICY.read_text(encoding="utf-8")
    leave_policy = "Employees receive 15 days of paid annual leave each year."
    assert leave_policy in source
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="hr-leave",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="HR Policy - Annual Leave",
                content=leave_policy,
            ),
            DocumentChunk(
                chunk_id="hr-expenses",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="HR Policy - Expenses",
                content="Expense reports are due within 30 days of purchase.",
            ),
        ]
    )

    hits = retriever.search(
        "How many PAID annual-leave days do employees receive?",
        make_context(),
        top_k=1,
    )

    assert [hit.chunk_id for hit in hits] == ["hr-leave"]
    assert 0 < hits[0].score <= 1
    assert hits[0].citation.quote in source
    assert hits[0].citation.quote in hits[0].content


def test_search_filters_tenant_and_access_control_before_scoring() -> None:
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="wrong-tenant",
                document_id="secret-1",
                tenant_id="tenant-2",
                title="Tenant 2 Plan",
                content="The launch codename is Mercury.",
            ),
            DocumentChunk(
                chunk_id="wrong-user",
                document_id="secret-2",
                tenant_id="tenant-1",
                title="Executive Plan",
                content="The launch codename is Mercury.",
                allowed_user_ids=frozenset({"executive-1"}),
            ),
            DocumentChunk(
                chunk_id="visible",
                document_id="public-1",
                tenant_id="tenant-1",
                title="Public Plan",
                content="The public launch month is September.",
            ),
        ]
    )

    hits = retriever.search("launch codename Mercury", make_context(), top_k=10)

    assert hits == []


def test_search_excludes_chunks_requiring_a_missing_trusted_permission() -> None:
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="payroll",
                document_id="hr-private",
                tenant_id="tenant-1",
                title="Payroll",
                content="The payroll review date is October 10.",
                required_permissions=frozenset({"payroll:read"}),
            )
        ]
    )

    hits = retriever.search("payroll review date", make_context(), top_k=3)

    assert hits == []


def test_answer_refuses_when_authorized_sources_do_not_answer_the_question() -> None:
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="leave",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="Annual Leave",
                content="Employees receive 15 days of paid annual leave each year.",
            )
        ]
    )

    answer = retriever.answer("What is the office WiFi password?", make_context())

    assert answer.refused is True
    assert answer.answer == "根据当前资料无法确认。"
    assert answer.citations == ()


def test_answer_refuses_misleading_single_term_overlap() -> None:
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="leave",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="Annual Leave",
                content="Employees receive 15 days of paid annual leave each year.",
            )
        ]
    )

    assert retriever.search("leave password", make_context(), top_k=3) == []
    answer = retriever.answer("leave password", make_context())

    assert answer.refused is True
    assert answer.answer == "根据当前资料无法确认。"
    assert answer.citations == ()


def test_answer_is_grounded_in_the_top_hit_and_citation() -> None:
    content = "Employees receive 15 days of paid annual leave each year."
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="leave",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="Annual Leave",
                content=content,
            )
        ]
    )

    answer = retriever.answer("paid annual leave days", make_context())

    assert answer.refused is False
    assert answer.answer == f"{content} [1]"
    assert answer.citations[0].quote == content
    assert answer.citations[0].quote in content


def test_query_normalization_maps_pto_allowance_to_annual_leave_days() -> None:
    content = "Employees receive 18 annual leave days each year."
    assert {"pto", "allowance"}.isdisjoint(content.casefold().split())
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="hr-synonym",
                document_id="hr-policy",
                tenant_id="tenant-1",
                title="Annual leave",
                content=content,
            )
        ]
    )

    hits = retriever.search("PTO allowance", make_context(), top_k=1)

    assert [hit.chunk_id for hit in hits] == ["hr-synonym"]
    assert hits[0].citation.quote == content


def test_query_normalization_maps_credential_renewal_to_password_reset() -> None:
    content = "Password reset links expire after 20 minutes."
    assert {"credential", "renewal"}.isdisjoint(content.casefold().split())
    retriever = InMemoryRetriever(
        [
            DocumentChunk(
                chunk_id="it-synonym",
                document_id="it-help",
                tenant_id="tenant-1",
                title="Password reset",
                content=content,
            )
        ]
    )

    hits = retriever.search("credential renewal", make_context(), top_k=1)

    assert [hit.chunk_id for hit in hits] == ["it-synonym"]
    assert hits[0].citation.quote == content
