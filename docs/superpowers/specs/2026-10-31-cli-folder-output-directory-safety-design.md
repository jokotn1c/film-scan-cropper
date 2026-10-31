# CLI Folder Output Directory Safety Design

## Intent

Prevent folder-mode runs from placing generated images directly beside inputs where later runs will treat those generated images as new sources.

## Root Cause

Folder mode snapshots every supported file directly inside the input directory. If `--output-dir` is that same directory, the current run processes only the original snapshot, but the next run includes the previously generated JPEG/TIFF outputs and creates a growing chain of derived crops. An existing regular file supplied as `--output-dir` also fails late once per item instead of producing one clear validation error.

## Goals

- Reject an output directory that resolves to the input directory.
- Reject an existing output path that is not a directory.
- Fail through argparse before `process_one` runs.
- Preserve the default `input/cropped`, other child directories, and unrelated output directories.

## Non-Goals

- Do not recursively scan input directories.
- Do not guess which same-directory files are originals versus prior outputs.
- Do not change GUI folder import behavior.

## Approach

Validate the resolved folder paths immediately after choosing `out_dir` and before collecting input files. Reject equality and existing non-directory paths with explicit parser errors. Rejecting same-directory output is safer and more deterministic than filename-pattern filtering, which could hide legitimate originals.

## Verification

CLI tests establish RED for same-directory and file-as-directory inputs, then verify the default child directory and an independent output directory remain valid. Run the full source suite afterward.
