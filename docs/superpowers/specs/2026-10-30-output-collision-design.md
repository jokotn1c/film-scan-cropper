# Output Collision Protection Design

## Intent

Prevent FilmCrop from silently replacing an earlier crop when two inputs generate the same output name or when the output directory already contains that name. The default behavior must preserve every existing file without interrupting ordinary batch processing.

## Goals

- Detect collisions among files in the current batch and against files already present in the output directory.
- Give generated outputs deterministic names: the first available base name, then `_2`, `_3`, and so on.
- Apply the same safety rule to the GUI, CLI folder processing, and CLI single-file processing with an automatically generated output path.
- Record and display the actual planned output path.
- Keep temporary-file encoding and final replacement behavior for a path reserved by the current FilmCrop job.
- Reject an explicitly supplied CLI `--output` path when it already exists.

## Non-goals

- No overwrite/skip/rename selector is added to the GUI in this change.
- Source directory trees are not mirrored into the output directory.
- Existing output files are not deleted, moved, or renamed.
- The project/session resume model is not made persistent in this change.
- This change does not attempt to coordinate output names with another FilmCrop process running at the same time.

## Chosen approach

FilmCrop will pre-plan generated output paths before processing begins. Candidate paths are considered occupied when they already exist on disk or were reserved earlier in the same plan. Comparison is case-insensitive so the plan remains safe on Windows and default macOS filesystems.

Given `IMG_0001_crop.tif`, candidates are tried in this order:

1. `IMG_0001_crop.tif`
2. `IMG_0001_crop_2.tif`
3. `IMG_0001_crop_3.tif`

The ordering of the current job list determines which input receives the unsuffixed name. The path planner will be standard-library-only so it can be tested without importing OpenCV, NumPy, RawPy, or the GUI.

The processing engine will accept a pre-planned output path. Existing callers that do not supply one will continue to derive a candidate from the source, but generated-path entry points must reserve a unique path first.

Immediately before committing an encoded temporary file, the writer will re-check that the destination does not exist. This closes the ordinary gap between planning and saving within FilmCrop. Full cross-process atomic reservation is intentionally out of scope because common removable filesystems such as exFAT do not support the same hard-link primitives as NTFS/APFS.

## Alternatives considered

### Preserve source directory structure

This naturally separates duplicate stems from different rolls, but becomes ambiguous when users add unrelated files or several independent folder roots. It also changes the output layout more substantially than needed.

### Stop and ask on every collision

This gives explicit control but interrupts unattended RAW batches. It remains a reasonable future preference once the GUI offers overwrite policies.

### Continue replacing existing outputs

This preserves current behavior but conflicts with the data-safety goal and can make two GUI rows point to the same final image.

## Error handling

- An explicitly supplied CLI `--output` that already exists raises a clear `FileExistsError` before decoding begins.
- If a planned generated path unexpectedly appears before the final save, that item fails without replacing the new file; the batch continues and reports the collision.
- Temporary encoded files are still removed in `finally` blocks after success or failure.

## Verification

Unit tests will cover:

- no collision;
- collision with an existing base name;
- collision with existing numbered names;
- two or more identical candidates inside one batch;
- case-only name differences;
- conflicts with directories as well as files;
- rejection of an existing explicit CLI output;
- preservation of actual planned paths in processing records.

The existing source-to-bundled-bytecode comparison is unrelated to this change and is not a release test. A rebuilt executable will be verified separately after the implementation and normal source tests pass.
