# CLI Dry-Run Output Planning Design

## Intent

Let users inspect the exact output paths a CLI operation would use before spending time decoding images or writing files.

## Goals

- Add a `--dry-run` flag for single-file and folder inputs.
- Run normal argument, output-extension, collision, and output-directory safety validation.
- Print one deterministic `PLAN <source> -> <output>` line per input in processing order.
- Use the real collision planner, including `_2`, `_3`, and batch reservations.
- Perform no image processing, output-directory creation, report creation, or file writes.

## Non-Goals

- Do not add a GUI control in this task.
- Do not emit JSON or change ordinary processing output.
- Do not bypass errors for occupied explicit `--output` paths.

## Approach

Add one argparse boolean. After the existing single-file path is resolved, print and return before `process_one`. After folder candidates are planned, print the complete ordered mapping and return before the processing loop. This reuses production planning rather than duplicating naming logic.

## Verification

Tests exercise real parsing and path planning with the image-processing boundary mocked. They assert exact planned paths, batch duplicate numbering, zero processing calls, and absence of a newly requested output directory.
