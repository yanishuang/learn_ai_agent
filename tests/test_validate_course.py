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


def test_malformed_course_manifest_json_is_reported(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text("{not-json}\n", encoding="utf-8")

    assert validate_repository(tmp_path) == [
        "docs/course-manifest.json: invalid JSON"
    ]


def test_course_manifest_root_must_be_a_list(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text("{}\n", encoding="utf-8")

    assert validate_repository(tmp_path) == [
        "docs/course-manifest.json: manifest must be a list"
    ]


def test_course_manifest_entries_require_mapping_path_and_title(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text(
        '["chapters/01.md", {"path": "", "title": "Second chapter"}, '
        '{"path": "chapters/03.md", "title": 3}]\n',
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "docs/course-manifest.json: entry 1 must be an object",
        "docs/course-manifest.json: entry 2 path must be a non-empty string",
        "docs/course-manifest.json: entry 3 title must be a non-empty string",
    ]


def test_manifest_heading_inside_backtick_fence_does_not_satisfy_heading(
    tmp_path: Path,
) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01.md").write_text(
        "```markdown\n# Expected heading\n```\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text(
        '[{"path": "chapters/01.md", "title": "Expected heading"}]\n',
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "chapters/01.md: expected top-level heading # Expected heading"
    ]


def test_manifest_heading_inside_tilde_fence_does_not_satisfy_heading(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "01.md").write_text(
        "~~~markdown\n# Expected heading\n~~~\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "course-manifest.json").write_text(
        '[{"path": "chapters/01.md", "title": "Expected heading"}]\n',
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "chapters/01.md: expected top-level heading # Expected heading"
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


def test_ecosystem_matrix_requires_an_exact_maturity_column(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ecosystem-maturity.md").write_text(
        "| Technology | Maturity status |\n"
        "| --- | --- |\n"
        "| Example SDK | Stable |\n",
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == [
        "docs/ecosystem-maturity.md: missing Maturity column"
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
