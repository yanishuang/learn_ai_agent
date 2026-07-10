from __future__ import annotations

import json
import re
import sys
from pathlib import Path
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
            else:
                lines.append(line)
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
            fence = None
    return lines


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

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    errors: list[str] = []
    for chapter in manifest:
        chapter_path = Path(chapter["path"])
        chapter_file = root / chapter_path
        if not chapter_file.is_file():
            errors.append(
                f"docs/course-manifest.json: missing chapter {chapter_path.as_posix()}"
            )
            continue

        expected_heading = f"# {chapter['title']}"
        headings = chapter_file.read_text(encoding="utf-8").splitlines()
        if expected_heading not in headings:
            errors.append(
                f"{chapter_path.as_posix()}: expected top-level heading {expected_heading}"
            )
    return errors


def _validate_ecosystem_maturity(root: Path) -> list[str]:
    matrix_file = root / "docs" / "ecosystem-maturity.md"
    if not matrix_file.is_file():
        return []

    lines = matrix_file.read_text(encoding="utf-8").splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if "Maturity" in _table_cells(line)),
        None,
    )
    if header_index is None:
        return []

    maturity_index = _table_cells(lines[header_index]).index("Maturity")
    errors: list[str] = []
    for line_number, line in enumerate(lines[header_index + 1 :], start=header_index + 2):
        cells = _table_cells(line)
        if not cells:
            break
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
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


def main() -> int:
    errors = validate_repository(Path(__file__).resolve().parents[1])
    if errors:
        print("\n".join(errors))
        return 1

    print("course validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
