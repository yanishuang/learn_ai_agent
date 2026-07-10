# Task 1 Report: Add Course Validation Before Structural Changes

## Status

Implemented and committed Task 1 validation and CI guardrails.

Commit: `9fd8919 test: add course structure validation`

## Implementation

- Added `scripts/validate_course.py` with `validate_repository(root: Path, *, require_course_structure: bool = True) -> list[str]`.
- Validates Markdown links in `README.md` and recursively under present `chapters/`, `docs/`, `teaching/`, and `labs/` directories. It uses `urllib.parse.urlparse` and `pathlib.Path`, ignores HTTP(S) URLs, anchors, and fenced code blocks, and reports broken local links.
- Validates every non-empty `*.jsonl` line recursively with `json.loads`.
- Defers structure checks until `docs/course-manifest.json` exists, then validates listed chapter paths and exact `# {title}` headings.
- Defers ecosystem maturity checks until `docs/ecosystem-maturity.md` exists, then requires `Stable`, `Preview`, `Experimental`, or `RC` values in its Maturity column.
- Sorts all diagnostics before returning them and provides a CLI that prints `course validation passed` on success or prints each error and exits 1 on failure.
- Added focused pytest coverage in `tests/test_validate_course.py`.
- Added `.github/workflows/course-ci.yml` with Python 3.12 and the required install, test, and validator commands.

## TDD Evidence

### Initial required tests

1. Wrote the required missing-local-link and invalid-JSONL tests verbatim.
2. Ran:

   ```bash
   python3 -m pytest tests/test_validate_course.py -q
   ```

   Initial environment result: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3: No module named pytest`.
3. Installed pytest only for local verification, then reran the same command through:

   ```bash
   python3 -m pip install --user pytest && python3 -m pytest tests/test_validate_course.py -q
   ```

   RED result: collection failed with `ModuleNotFoundError: No module named 'scripts'`.
4. Implemented the minimum Markdown-link and JSONL validation. GREEN result:

   ```text
   2 passed in 0.00s
   ```

### Fenced-link behavior

1. Added the test for HTTP(S), anchors, and fenced Markdown links.
2. Ran:

   ```bash
   python3 -m pytest tests/test_validate_course.py -q
   ```

   RED result: `README.md: broken local link chapters/missing.md` was reported from inside a code fence.
3. Implemented fence-aware link scanning. GREEN result:

   ```text
   3 passed in 0.01s
   ```

### Manifest behavior

1. Added the missing chapter and exact-heading manifest test.
2. Ran:

   ```bash
   python3 -m pytest tests/test_validate_course.py -q
   ```

   RED result: expected manifest errors, received `[]`.
3. Implemented manifest validation only when the file exists and structure checks are required. GREEN result:

   ```text
   4 passed in 0.01s
   ```

### Ecosystem maturity behavior

1. Added the unrecognized-label test and ran:

   ```bash
   python3 -m pytest tests/test_validate_course.py -q
   ```

   RED result: expected `docs/ecosystem-maturity.md:3: invalid maturity label Unknown`, received `[]`.
2. Implemented matrix label validation. GREEN result:

   ```text
   5 passed in 0.01s
   ```
3. Added the missing-label test and reran the same command.

   RED result: received `invalid maturity label ` instead of `missing maturity label`.
4. Added the explicit empty-label diagnostic. GREEN result:

   ```text
   6 passed in 0.01s
   ```

## Final Verification

Ran:

```bash
python3 -m pytest tests/test_validate_course.py -q && python3 scripts/validate_course.py && git diff --check && git status --short
```

Result:

```text
......                                                                   [100%]
6 passed in 0.01s
course validation passed
```

`git diff --check` completed without output. The status at that point showed only the three intended new deliverables before they were staged and committed.

## Files Changed

- `scripts/validate_course.py`
- `tests/test_validate_course.py`
- `.github/workflows/course-ci.yml`

## Self-Review

- Confirmed the public API returns errors rather than terminating the process; only the CLI calls `sys.exit`.
- Confirmed output ordering is deterministic through a final lexical sort.
- Confirmed pre-Task-2 repository validation succeeds with no manifest present.
- Confirmed the workflow pins Python 3.12 and uses the exact three required command strings.
- Confirmed no whitespace errors with `git diff --check`.
- Confirmed only the three owned implementation files were included in commit `9fd8919`.

## Concerns

- Local verification used the available Xcode Python 3.9.6 because Python 3.12 is not installed locally. The committed CI workflow pins Python 3.12, as required.
- `pytest` was installed with `--user` for local verification only; no environment artifacts were added to the repository.

## Important Task 1 Review Finding Fix

- Added a regression test for an ecosystem maturity table row shorter than the Maturity column. Before the fix, the required command produced `IndexError: list index out of range` at `scripts/validate_course.py:137`, with `1 failed, 6 passed`.
- Added minimal bounds handling so an absent maturity cell is treated as empty and reports `docs/ecosystem-maturity.md:3: missing maturity label`.
- Re-ran the exact required test command after the fix:

  ```bash
  python3 -m pytest tests/test_validate_course.py -q
  ```

  GREEN result:

  ```text
  7 passed in 0.01s
  ```

- Ran `python3 scripts/validate_course.py`; result: `course validation passed`.
- Ran `git diff --check`; completed without output.

## Important Task 1 Review Finding Fix: Malformed Course Manifest JSON

- Added `test_malformed_course_manifest_json_is_reported` to verify that malformed `docs/course-manifest.json` returns exactly `docs/course-manifest.json: invalid JSON`.
- Ran:

  ```bash
  python3 -m pytest tests/test_validate_course.py -q
  ```

  RED result:

  ```text
  exit_code=1
  ....F...                                                                 [100%]
  FAILED tests/test_validate_course.py::test_malformed_course_manifest_json_is_reported
  E   json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
  1 failed, 7 passed in 0.03s
  ```

- Added minimal `JSONDecodeError` handling in `_validate_course_manifest`.
- Re-ran the exact test command. GREEN result:

  ```text
  exit_code=0
  ........                                                                 [100%]
  8 passed in 0.01s
  ```

- Ran `python3 scripts/validate_course.py`; exact result: `course validation passed`.
- Ran `git diff --check`; exact result: no output and exit code 0.
