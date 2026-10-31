# Release Version Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align every repository-controlled release identifier with FilmCrop `1.9.1`.

**Architecture:** Keep `film_version.VERSION` as the runtime and build source of truth. Update static documentation and workflow strings that cannot import it, and guard all references with a standard-library consistency test.

**Tech Stack:** Python 3.12+, `unittest`, `pathlib`, existing PyInstaller specs and GitHub Actions YAML

**Spec:** `docs/superpowers/specs/2026-10-31-version-consistency-design.md`

## Global Constraints

- The repository-controlled release version is exactly `1.9.1`.
- No image-processing behavior, dependency, external Git tag, binary, or release is changed.
- The test uses only the Python standard library.

## Review Focus

- GUI and PyInstaller builds must continue to consume `film_version.VERSION` rather than duplicating a new constant.
- README and both bundled Chinese instruction files must show `1.9.1` in their primary version text.
- Windows executable instructions must name `FilmCrop-RAW-1.9.1.exe`.
- macOS guide and workflow artifact name must use `FilmCrop-RAW-1.9.1-mac-arm64`.
- Historical update headings may remain historical, but current product and artifact identifiers must not remain at `1.9`.

---

### Task 1: Align and guard repository version metadata

**Files:**
- Create: `tests/test_version_consistency.py`
- Modify: `film_version.py`
- Modify: `README.md`
- Modify: `使用说明.txt`
- Modify: `技术说明.txt`
- Modify: `MACOS-ARM.md`
- Modify: `.github/workflows/build-macos-arm64.yml`

**Interfaces:**
- Consumes: `film_version.VERSION` used by the GUI and both PyInstaller build paths.
- Produces: exact release identifier `1.9.1` and a repository consistency contract.

- [ ] **Step 1: Write the failing version consistency test**

Add tests that assert `film_version.VERSION == '1.9.1'` and verify the primary version/artifact references in README, both Chinese instruction files, the macOS guide, and the macOS workflow.

- [ ] **Step 2: Run the focused test and verify RED**

Run the embedded Python unittest discovery command for `test_version_consistency.py`.

Expected: FAIL because current repository references use `1.9`.

- [ ] **Step 3: Update version metadata and static references**

Change only the current version and artifact identifiers to `1.9.1`. Preserve historical `1.1`, `1.2`, and `1.9` update headings.

- [ ] **Step 4: Run focused and full suites**

Expected: the focused test and complete suite PASS with zero failures and errors.

- [ ] **Step 5: Verify and commit**

Run compileall, diff whitespace checks, and Git status. Commit the implementation and test as `fix: align release version metadata`.
