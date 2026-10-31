# CLI Explicit Output Extension Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject explicit CLI output paths whose suffix is unsupported or inconsistent with the encoded format.

**Architecture:** Add one pure suffix-to-format validator in `film_crop.py`, call it only for explicit single-file outputs, and route validation errors through argparse before image processing. Generated paths remain unchanged.

**Tech Stack:** Python 3.12+, `argparse`, `pathlib`, `unittest`, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-10-31-cli-output-extension-validation-design.md`

## Global Constraints

- Auto explicit outputs accept only `.jpg`, `.jpeg`, `.tif`, and `.tiff`, case-insensitively.
- Explicit `JPEG` accepts only `.jpg`/`.jpeg`; explicit `TIFF16` accepts only `.tif`/`.tiff`.
- Invalid combinations fail before `process_one` and before creating an output.
- Generated CLI, GUI, and engine paths remain unchanged.

## Review Focus

- An empty suffix and unrelated suffixes such as `.png` must not default silently to JPEG.
- Uppercase supported extensions must behave like lowercase.
- `--output-format JPEG --output x.tif` and the inverse TIFF/JPEG mismatch must fail.
- Existing explicit output collision checks must still run for valid suffixes.
- Existing implicit output generation and folder planning must remain unchanged.

---

### Task 1: Validate explicit CLI output suffixes

**Files:**
- Modify: `film_crop.py:40-65,444-472`
- Modify: `tests/test_cli_output_paths.py`

**Interfaces:**
- Produces: `explicit_output_format(path: pathlib.Path, requested: str) -> str`, returning `JPEG` or `TIFF16` and raising `ValueError` for invalid suffix/format combinations.
- Consumes: existing argparse `--output` and `--output-format` values.

- [ ] **Step 1: Write failing CLI regression tests**

Add tests for unsupported auto suffix, missing suffix, explicit JPEG/TIFF mismatches, accepted JPEG/TIFF suffixes, and uppercase suffixes. Invalid cases assert `SystemExit(2)`, an informative error, and zero `process_one` calls.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: invalid cases reach `process_one` or resolve to the wrong format because no validator exists.

- [ ] **Step 3: Implement the pure validator and connect it to single-file explicit output handling**

Resolve the format before collision checking and call `parser.error` with the validator's `ValueError` message. Remove the current two-suffix/else-JPEG inference.

- [ ] **Step 4: Run focused and full test suites**

Expected: all tests PASS with zero failures and errors.

- [ ] **Step 5: Verify and commit**

Run compileall, diff whitespace checks, and Git status. Commit as `fix: validate explicit CLI output extensions`.
