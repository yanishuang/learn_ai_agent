from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse


MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
MARKDOWN_DIRECTORIES = ("chapters", "docs", "teaching", "labs")
MATURITY_LABELS = {"stable", "preview", "experimental", "rc"}


def validate_repository(root: Path, *, require_course_structure: bool = True) -> list[str]:
    errors: list[str] = []
    for markdown_file in _markdown_files(root):
        errors.extend(_validate_markdown_links(root, markdown_file))

    for jsonl_file in sorted(root.rglob("*.jsonl")):
        errors.extend(_validate_jsonl(root, jsonl_file))

    if require_course_structure:
        errors.extend(_validate_course_manifest(root))
        errors.extend(_validate_ecosystem_maturity(root))

    return sorted(errors)


def _markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    readme = root / "README.md"
    if readme.is_file():
        files.append(readme)

    for directory in MARKDOWN_DIRECTORIES:
        base = root / directory
        if base.is_dir():
            files.extend(sorted(base.rglob("*.md")))

    return files


def _validate_markdown_links(root: Path, markdown_file: Path) -> list[str]:
    errors: list[str] = []
    relative_file = markdown_file.relative_to(root).as_posix()
    content = "\n".join(_lines_outside_fenced_code_blocks(markdown_file))
    for match in MARKDOWN_LINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        parsed = urlparse(target)
        if target.startswith("#") or parsed.scheme in {"http", "https"}:
            continue

        local_path = Path(parsed.path)
        if not local_path or (markdown_file.parent / local_path).exists():
            continue

        errors.append(f"{relative_file}: broken local link {target}")
    return errors


def _lines_outside_fenced_code_blocks(markdown_file: Path) -> list[str]:
    lines: list[str] = []
    fence: str | None = None
    for line in markdown_file.read_text(encoding="utf-8").splitlines():
        match = FENCE_PATTERN.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                lines.append("")
            else:
                lines.append(line)
        else:
            lines.append("")
            if _is_closing_fence(line, fence):
                fence = None
    return lines


def _is_closing_fence(line: str, opening_fence: str) -> bool:
    stripped_line = line.lstrip()
    fence_character = opening_fence[0]
    fence_length = len(stripped_line) - len(stripped_line.lstrip(fence_character))
    return (
        fence_length >= len(opening_fence)
        and stripped_line[fence_length:].strip() == ""
    )


def _validate_jsonl(root: Path, jsonl_file: Path) -> list[str]:
    errors: list[str] = []
    relative_file = jsonl_file.relative_to(root).as_posix()
    for line_number, line in enumerate(jsonl_file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"{relative_file}:{line_number}: invalid JSON")
    return errors


def _validate_course_manifest(root: Path) -> list[str]:
    manifest_file = root / "docs" / "course-manifest.json"
    if not manifest_file.is_file():
        return []

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["docs/course-manifest.json: invalid JSON"]

    if not isinstance(manifest, list):
        return ["docs/course-manifest.json: manifest must be a list"]

    errors: list[str] = []
    resolved_root = root.resolve()
    for entry_number, chapter in enumerate(manifest, start=1):
        if not isinstance(chapter, Mapping):
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} must be an object"
            )
            continue

        path = chapter.get("path")
        title = chapter.get("title")
        has_valid_path = isinstance(path, str) and bool(path.strip())
        has_valid_title = isinstance(title, str) and bool(title.strip())
        if not has_valid_path:
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} path must be a non-empty string"
            )
        if not has_valid_title:
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} title must be a non-empty string"
            )
        if not has_valid_path or not has_valid_title:
            continue

        chapter_path = Path(path)
        if chapter_path.is_absolute() or PureWindowsPath(path).is_absolute():
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} path must be repository-relative"
            )
            continue
        if ".." in chapter_path.parts:
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} path must not contain parent traversal"
            )
            continue

        chapter_file = root / chapter_path
        if not _is_within_root(chapter_file, resolved_root):
            errors.append(
                f"docs/course-manifest.json: entry {entry_number} path escapes repository root"
            )
            continue
        if not chapter_file.is_file():
            errors.append(
                f"docs/course-manifest.json: missing chapter {chapter_path.as_posix()}"
            )
            continue

        expected_heading = f"# {title}"
        headings = _lines_outside_fenced_code_blocks(chapter_file)
        if expected_heading not in headings:
            errors.append(
                f"{chapter_path.as_posix()}: expected top-level heading {expected_heading}"
            )
    return errors


def _is_within_root(path: Path, resolved_root: Path) -> bool:
    try:
        path.resolve().relative_to(resolved_root)
    except (RuntimeError, ValueError):
        return False
    return True


def _validate_ecosystem_maturity(root: Path) -> list[str]:
    matrix_file = root / "docs" / "ecosystem-maturity.md"
    if not matrix_file.is_file():
        return []

    lines = _lines_outside_fenced_code_blocks(matrix_file)
    header_index = next(
        (
            index
            for index, line in enumerate(lines[:-1])
            if _table_cells(line) and _is_table_separator(_table_cells(lines[index + 1]))
        ),
        None,
    )
    if header_index is None:
        return ["docs/ecosystem-maturity.md: missing maturity table"]

    header_cells = _table_cells(lines[header_index])
    if "Maturity" not in header_cells:
        return ["docs/ecosystem-maturity.md: missing Maturity column"]

    maturity_index = header_cells.index("Maturity")
    errors: list[str] = []
    for line_number, line in enumerate(lines[header_index + 1 :], start=header_index + 2):
        cells = _table_cells(line)
        if not cells:
            break
        if _is_table_separator(cells):
            continue
        maturity = cells[maturity_index] if maturity_index < len(cells) else ""
        if not maturity:
            errors.append(f"docs/ecosystem-maturity.md:{line_number}: missing maturity label")
        elif maturity.casefold() not in MATURITY_LABELS:
            errors.append(
                f"docs/ecosystem-maturity.md:{line_number}: invalid maturity label {maturity}"
            )
    return errors


def _table_cells(line: str) -> list[str]:
    if not line.strip().startswith("|") or not line.strip().endswith("|"):
        return []
    return [cell.strip() for cell in line.strip()[1:-1].split("|")]


def _is_table_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def main() -> int:
    errors = validate_repository(Path(__file__).resolve().parents[1])
    if errors:
        print("\n".join(errors))
        return 1

    print("course validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
