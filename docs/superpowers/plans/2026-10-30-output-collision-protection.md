# Output Collision Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure generated FilmCrop outputs never replace an existing file and receive deterministic `_2`, `_3`, and later suffixes when names collide.

**Architecture:** Add a standard-library-only path-planning module that owns candidate naming, case-insensitive reservations, and existing-path checks. The engine accepts a pre-planned output path; the GUI and CLI plan generated paths before decoding, while the image writer performs a final destination check immediately before committing its temporary file.

**Tech Stack:** Python 3.12+, `pathlib`, `unittest`, existing Tkinter/OpenCV/NumPy/RawPy/Pillow/tifffile application stack

**Spec:** `docs/superpowers/specs/2026-10-30-output-collision-design.md`

## Global Constraints

- Generated output names try the unsuffixed candidate first, then `_2`, `_3`, and later integers.
- A path already present on disk or reserved earlier in the same plan is occupied.
- Reservation comparison is case-insensitive on every supported platform.
- GUI, CLI folder mode, and CLI single-file mode without explicit `--output` must use planned generated paths.
- An existing explicit CLI `--output` must fail before image decoding begins.
- Existing files and directories are never deleted, moved, renamed, or replaced by default.
- Temporary encoded files must still be removed after success or failure.
- Add no third-party dependency for planning or tests.
- Cross-process atomic path reservation and a GUI overwrite-policy selector remain out of scope.

## Review Focus

- A destination appearing after planning but before save must make that item fail without replacing the new destination; Task 2 tests the writer's final check.
- Existing `crop.tif` and `crop_2.tif` must make the next generated path `crop_3.tif`; Task 1 tests consecutive numbering.
- `IMG_crop.tif` and `img_crop.tif` must collide even on a case-sensitive development filesystem; Task 1 tests case-only reservations.
- A directory occupying a candidate filename must be treated exactly like a file; Task 1 tests directory collisions.
- An explicit CLI `--output` collision must stop before `process_one` is called; Task 4 tests the early failure boundary.

---

### Task 1: Standard-library output path planner

**Files:**
- Create: `film_paths.py`
- Create: `tests/test_film_paths.py`

**Interfaces:**
- Produces: `output_path(folder, source, output_format, suffix='crop') -> pathlib.Path`
- Produces: `plan_output_paths(candidates) -> list[pathlib.Path]`
- Produces: `require_output_available(path) -> pathlib.Path`
- `plan_output_paths` preserves candidate order and checks both `Path.exists()` and a case-folded reservation key.

- [ ] **Step 1: Write failing planner tests**

Add `unittest` cases named:

- `test_keeps_free_candidate`
- `test_numbers_after_existing_base`
- `test_skips_existing_numbered_candidates`
- `test_reserves_duplicates_within_batch`
- `test_reservations_are_case_insensitive`
- `test_directory_occupies_candidate`
- `test_require_output_available_rejects_existing_path`

Use `tempfile.TemporaryDirectory`; assert exact names such as `IMG_crop.tif`, `IMG_crop_2.tif`, and `IMG_crop_3.tif`.

- [ ] **Step 2: Run the planner tests and verify the red state**

Run: `python -m unittest discover -s tests -p "test_film_paths.py" -v`

Expected: FAIL because `film_paths` does not exist.

- [ ] **Step 3: Implement the planner interfaces in `film_paths.py`**

Keep the module standard-library-only. `require_output_available` raises `FileExistsError` with the occupied path in the message. `plan_output_paths` treats both files and directories as occupied and starts numbering at `2`.

- [ ] **Step 4: Run the planner tests and verify the green state**

Run: `python -m unittest discover -s tests -p "test_film_paths.py" -v`

Expected: all Task 1 tests PASS.

- [ ] **Step 5: Commit the planner**

```bash
git add film_paths.py tests/test_film_paths.py
git commit -m "feat: plan collision-free output paths"
```

### Task 2: Writer guard and engine output override

**Files:**
- Modify: `film_io.py:1-109`
- Modify: `film_engine.py:157-177`
- Create: `tests/test_output_integration.py`

**Interfaces:**
- Consumes: Task 1 `output_path`, `plan_output_paths`, and `require_output_available`.
- Produces: backward-compatible `film_io.output_path` re-export.
- Produces: `process_file(source, folder, options=Options(), *, output=None)` where `output` may be a planned path.
- When `output is None`, `process_file` plans one safe generated path before writing.

- [ ] **Step 1: Write failing writer and engine tests**

Add tests named:

- `test_write_image_rejects_existing_destination_before_encoding`
- `test_write_image_rechecks_destination_before_replace`
- `test_process_file_uses_supplied_output_path`
- `test_process_file_records_actual_output_path`
- `test_process_file_without_override_avoids_existing_output`

Stub heavy image modules before importing `film_io` and mock the engine's decode, locate, crop, and write collaborators. For the final writer check, make the mocked encoder create the destination after the initial check and assert the original destination bytes remain unchanged.

- [ ] **Step 2: Run Task 2 tests and verify they fail for missing guards/signature**

Run: `python -m unittest discover -s tests -p "test_output_integration.py" -v`

Expected: FAIL because `write_image` still replaces existing destinations and `process_file` has no `output` keyword.

- [ ] **Step 3: Re-export path helpers from `film_io.py` and add two writer checks**

Remove the local `output_path` implementation, import it from `film_paths`, and call `require_output_available(path)` once before encoding and once immediately before `os.replace(temp, path)`. Preserve the existing `finally` cleanup.

- [ ] **Step 4: Add the keyword-only engine output override**

Change the signature to `process_file(source, folder, options=Options(), *, output=None)`. Use the supplied `Path` verbatim; otherwise plan a single generated candidate with Task 1's planner. Ensure the returned record contains the actual path.

- [ ] **Step 5: Run Task 1 and Task 2 tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit writer and engine integration**

```bash
git add film_io.py film_engine.py tests/test_output_integration.py
git commit -m "fix: prevent output replacement during save"
```

### Task 3: GUI batch pre-planning

**Files:**
- Modify: `film_gui.py:25-41,261-386`
- Modify: `tests/test_output_integration.py`

**Interfaces:**
- Consumes: Task 1 `output_path` and `plan_output_paths`.
- Consumes: Task 2 `process_file(..., output=planned_path)`.
- Produces: `FilmApp.active_outputs: dict[str, pathlib.Path]` for the current batch.
- Produces: `FilmApp.plan_job_outputs(jobs, folder) -> dict[str, pathlib.Path]`, usable on an object constructed without opening a Tk window.

- [ ] **Step 1: Write failing GUI planning tests**

Add tests named:

- `test_gui_plan_assigns_unique_paths_to_duplicate_stems`
- `test_gui_plan_respects_each_jobs_format_and_border_suffix`
- `test_worker_passes_planned_path_to_engine`

Construct `FilmApp` with `object.__new__`, supply `active_options`, and stub GUI-only imports. Assert two sources named `IMG_0001.ARW` receive `IMG_0001_crop.tif` and `IMG_0001_crop_2.tif` in job order.

- [ ] **Step 2: Run the GUI planning tests and verify they fail**

Run: `python -m unittest discover -s tests -p "test_output_integration.py" -v`

Expected: FAIL because `active_outputs` and `plan_job_outputs` do not exist.

- [ ] **Step 3: Implement `FilmApp.plan_job_outputs` and initialize `active_outputs`**

Build one candidate per job from its effective options: `border` when `keep_border` is true, otherwise `crop`; use that job's output format for the extension. Plan the full list in one call so batch duplicates are reserved deterministically.

- [ ] **Step 4: Pass planned paths through `worker`**

Populate `active_outputs` before starting the worker and call `process_file(path, folder, effective_options, output=self.active_outputs[iid])`. Do not change current session resume signatures in this task.

- [ ] **Step 5: Run all tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit GUI planning**

```bash
git add film_gui.py tests/test_output_integration.py
git commit -m "fix: reserve unique GUI batch outputs"
```

### Task 4: CLI safety and user documentation

**Files:**
- Modify: `film_crop.py:424-481`
- Modify: `README.md`
- Modify: `使用说明.txt`
- Modify: `技术说明.txt`
- Create: `tests/test_cli_output_paths.py`

**Interfaces:**
- Consumes: Task 1 `output_path`, `plan_output_paths`, and `require_output_available`.
- Single-file implicit output plans one generated candidate.
- Single-file explicit `--output` calls `require_output_available` before `process_one`.
- Folder mode plans all candidates before processing the first file.

- [ ] **Step 1: Write failing CLI behavior tests**

Add tests named:

- `test_explicit_existing_output_fails_before_process_one`
- `test_implicit_single_output_gets_numbered_name`
- `test_folder_outputs_are_planned_before_processing`
- `test_folder_plan_skips_existing_numbered_outputs`

Patch `process_one` so tests assert its calls without decoding images. For the explicit collision test, assert `process_one` is never called.

- [ ] **Step 2: Run CLI tests and verify the red state**

Run: `python -m unittest discover -s tests -p "test_cli_output_paths.py" -v`

Expected: FAIL because CLI entry points still use unplanned candidates and permit replacement.

- [ ] **Step 3: Implement single-file CLI protection**

When `args.output` is supplied, reject an occupied path before `process_one`. Otherwise reserve one generated candidate and pass it to `process_one`.

- [ ] **Step 4: Implement folder-wide CLI planning**

Compute every file's effective output format and base candidate first, plan the full candidate list once, then process `path`, `format`, and planned `output` tuples in the original sorted order.

- [ ] **Step 5: Update user-facing overwrite documentation**

Replace every statement that same-name results overwrite with the exact `_2`, `_3` behavior. State that an explicit CLI `--output` must not already exist.

- [ ] **Step 6: Run the full source test suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 7: Commit CLI and documentation integration**

```bash
git add film_crop.py README.md 使用说明.txt 技术说明.txt tests/test_cli_output_paths.py
git commit -m "fix: protect CLI outputs from collisions"
```

### Task 5: Full regression and package verification

**Files:**
- Modify only if verification exposes a defect in the preceding tasks.

**Interfaces:**
- Consumes: the completed source implementation and all tests from Tasks 1-4.
- Produces: verified source behavior and, when the documented build environment is available, a newly built Windows executable.

- [ ] **Step 1: Run the complete unit suite from a clean process**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with zero errors and zero failures.

- [ ] **Step 2: Compile every Python source file**

Run: `python -m compileall -q .`

Expected: exit code `0` and no syntax errors.

- [ ] **Step 3: Inspect the branch diff and whitespace**

Run: `git diff --check v1.9.0...HEAD`

Expected: exit code `0` and no output.

Run: `git status --short`

Expected: no uncommitted files except documented build artifacts excluded by `.gitignore`.

- [ ] **Step 4: Build the Windows executable when dependencies are available**

Run: `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`

Expected: exit code `0` and a new `outputs/FilmCrop-RAW-1.9.exe`.

- [ ] **Step 5: Run a packaged collision smoke test**

Using two test sources with the same stem from different directories, process them into one empty output directory and verify two distinct outputs exist. Repeat with the base output already present and verify it remains byte-for-byte unchanged while the new result receives `_2` or the next free number.

- [ ] **Step 6: Commit only verification-driven repairs**

If Step 1-5 required code changes, rerun all verification commands and commit the focused repair. Do not commit generated executables or local test images unless the repository's release policy explicitly requires them.
