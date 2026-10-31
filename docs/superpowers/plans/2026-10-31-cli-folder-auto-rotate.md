# CLI Folder Auto-Rotate Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make folder-mode `--no-auto-rotate` propagate the same rotation setting as single-file mode.

**Architecture:** Keep the existing CLI and `process_one` interfaces. Add regression coverage around real argument parsing, then pass `auto_rotate=not args.no_auto_rotate` explicitly from the folder branch.

**Tech Stack:** Python 3.12+, `argparse`, `pathlib`, `unittest`, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-10-31-cli-folder-auto-rotate-design.md`

## Global Constraints

- Folder mode with `--no-auto-rotate` passes `auto_rotate=False` for every supported input file.
- Folder mode without the flag preserves `auto_rotate=True`.
- Single-file, GUI, detection, decoding, and output-path behavior remain unchanged.
- Add no dependency and perform no broad CLI refactor.

## Review Focus

- A folder containing multiple supported files must pass `False` to every `process_one` call when the flag is present.
- Folder mode without the flag must continue to pass `True`.
- Single-file `--no-auto-rotate` must remain `False` after the change.
- Existing folder output pre-planning must still happen before processing.
- Unsupported files and folder iteration order must remain unchanged.

---

### Task 1: Propagate the folder auto-rotate setting

**Files:**
- Modify: `tests/test_cli_output_paths.py`
- Modify: `film_crop.py:475-488`

**Interfaces:**
- Consumes: existing `main()` argument parsing and `process_one(..., auto_rotate=True)`.
- Produces: folder calls with explicit `auto_rotate: bool` matching `not args.no_auto_rotate`.

- [ ] **Step 1: Write failing folder-mode regression tests**

Add `test_folder_no_auto_rotate_disables_rotation_for_every_file` and `test_folder_auto_rotate_remains_enabled_by_default`. Each test creates two supported files, runs the real `main()` parser with `process_one` mocked, and asserts every call has the exact `auto_rotate` keyword value.

- [ ] **Step 2: Run the focused tests and verify RED**

Run the embedded Python unittest discovery command for `test_cli_output_paths.py`.

Expected: both new tests FAIL because folder-mode calls omit the `auto_rotate` keyword.

- [ ] **Step 3: Add the minimal folder propagation fix**

In the folder branch's existing `process_one` call, add `auto_rotate=not args.no_auto_rotate`. Make no other production change.

- [ ] **Step 4: Run focused and full suites**

Run the CLI test module, then all tests under `tests/`.

Expected: all tests PASS with zero failures and zero errors.

- [ ] **Step 5: Verify source integrity and commit**

Run `python -m compileall -q .`, `git diff --check`, and `git status --short`. Commit only `film_crop.py` and `tests/test_cli_output_paths.py` with message `fix: honor no-auto-rotate for folders`.
