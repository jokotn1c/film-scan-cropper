# CLI Dry-Run Output Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a no-write CLI mode that prints the exact collision-safe output plan for single files and folders.

**Architecture:** Reuse the existing argument validation and path planner, branching only after paths are fully resolved. Dry-run exits before the image-processing calls.

**Tech Stack:** Python 3.12+, `argparse`, `pathlib`, `unittest`, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-10-31-cli-dry-run-design.md`

## Global Constraints

- Output is exactly one `PLAN <source> -> <output>` line per planned input.
- Dry-run performs no decode, crop, output-directory creation, output write, or report write.
- All existing validation and collision numbering rules still apply.
- Ordinary non-dry-run behavior remains unchanged.

## Review Focus

- Single-file implicit output must show the next available numbered name.
- Folder sources with duplicate stems must receive unique names in sorted order.
- A non-existing output directory must remain absent after dry-run.
- An occupied explicit single-file output must still fail rather than auto-number.
- Invalid explicit suffix and same-folder output validation must still precede dry-run output.

---

### Task 1: Add CLI dry-run planning

**Files:**
- Modify: `film_crop.py:445-520`
- Modify: `tests/test_cli_output_paths.py`
- Modify: `README.md`

**Interfaces:**
- Produces: CLI `--dry-run` flag and `PLAN <source> -> <output>` output contract.
- Consumes: existing `output_path`, `plan_output_paths`, and explicit-output validation.

- [ ] **Step 1: Write failing dry-run tests**

Add single-file and folder tests that capture stdout, assert exact planned paths, assert zero `process_one` calls, and assert the requested output directory was not created.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: argparse rejects `--dry-run` because the option does not exist.

- [ ] **Step 3: Implement the minimal dry-run branches**

Add the flag and return after printing the resolved single plan or complete folder plan. Do not create directories.

- [ ] **Step 4: Document the command and run focused/full suites**

Add a concise README example and behavior note. Expected: all tests PASS.

- [ ] **Step 5: Verify and commit**

Run compileall, diff whitespace checks, and Git status. Commit as `feat: add CLI output planning dry run`.
