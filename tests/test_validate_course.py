from pathlib import Path

from scripts.validate_course import validate_repository


def test_missing_local_markdown_link_is_reported(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("[missing](chapters/99.md)\n", encoding="utf-8")
    assert validate_repository(tmp_path, require_course_structure=False) == [
        "README.md: broken local link chapters/99.md"
    ]


def test_invalid_jsonl_is_reported(tmp_path: Path) -> None:
    evals = tmp_path / "evals"
    evals.mkdir()
    (evals / "cases.jsonl").write_text("{not-json}\n", encoding="utf-8")
    assert validate_repository(tmp_path, require_course_structure=False) == [
        "evals/cases.jsonl:1: invalid JSON"
    ]


def test_nonlocal_and_fenced_markdown_links_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "[website](https://example.com)\n"
        "[section](#course)\n"
        "```markdown\n"
        "[example](chapters/missing.md)\n"
        "```\n",
        encoding="utf-8",
    )
    assert validate_repository(tmp_path, require_course_structure=False) == []


def test_manifest_requires_listed_chapters_and_exact_headings(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01.md").write_text("# Different heading\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text(
        '[{"path": "chapters/01.md", "title": "Expected heading"}, '
        '{"path": "chapters/02.md", "title": "Second chapter"}]\n',
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "chapters/01.md: expected top-level heading # Expected heading",
        "docs/course-manifest.json: missing chapter chapters/02.md",
    ]


def test_ecosystem_matrix_requires_recognized_maturity_labels(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ecosystem-maturity.md").write_text(
        "| Technology | Role | Maturity | Course status | Verified | Primary source |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Example SDK | Agent framework | Unknown | Core | 2026-07-10 | source |\n",
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "docs/ecosystem-maturity.md:3: invalid maturity label Unknown"
    ]


def test_ecosystem_matrix_reports_missing_maturity_labels(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ecosystem-maturity.md").write_text(
        "| Technology | Role | Maturity | Course status | Verified | Primary source |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Example SDK | Agent framework |  | Core | 2026-07-10 | source |\n",
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "docs/ecosystem-maturity.md:3: missing maturity label"
    ]


def test_ecosystem_matrix_reports_missing_maturity_for_short_row(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ecosystem-maturity.md").write_text(
        "| Technology | Role | Maturity | Course status | Verified | Primary source |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Example SDK | Agent framework |\n",
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "docs/ecosystem-maturity.md:3: missing maturity label"
    ]
