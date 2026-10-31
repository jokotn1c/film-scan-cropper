# CLI Folder Output Directory Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop CLI folder mode before it can emit generated outputs into the input directory or use a regular file as an output directory.

**Architecture:** Add two path validations in the existing folder branch before input enumeration. Keep all image and path-planning interfaces unchanged.

**Tech Stack:** Python 3.12+, `argparse`, `pathlib`, `unittest`, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-10-31-cli-folder-output-directory-safety-design.md`

## Global Constraints

- Same resolved input/output directories fail before processing.
- An existing non-directory output path fails before processing.
- Default `input/cropped`, other child directories, and unrelated directories remain valid.
- No input file is deleted, moved, renamed, or filtered by a generated-name pattern.

## Review Focus

- Relative spellings such as `input/.` must compare by resolved path.
- Validation must happen before `process_one` and before output files are created.
- A non-existing output directory remains allowed for the writer to create.
- The default nested `cropped` directory remains allowed.
- Existing collision planning and sorted input order remain unchanged.

---

### Task 1: Validate folder output directory placement

**Files:**
- Modify: `film_crop.py:492-505`
- Modify: `tests/test_cli_output_paths.py`

**Interfaces:**
- Consumes: folder-mode `args.input` and selected `out_dir` paths.
- Produces: early argparse errors for unsafe output-directory choices.

- [ ] **Step 1: Write failing CLI tests**

Add tests asserting same-directory and existing-file output paths exit with code 2, show clear messages, and never call `process_one`. Add a positive assertion that the default child directory still reaches processing.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: unsafe cases currently reach processing or per-item skip handling.

- [ ] **Step 3: Add minimal folder path validation**

Resolve input and output paths; call `parser.error` for equality or an existing non-directory output path before enumerating input files.

- [ ] **Step 4: Run focused and full suites**

Expected: all tests PASS.

- [ ] **Step 5: Verify and commit**

Run compileall, diff whitespace checks, and Git status. Commit as `fix: reject unsafe CLI output directories`.
