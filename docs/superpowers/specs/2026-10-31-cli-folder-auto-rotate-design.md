# CLI Folder Auto-Rotate Flag Design

## Intent

Make `--no-auto-rotate` behave consistently for single-file and folder inputs. A user who disables automatic rotation for a folder batch must have every file processed with `auto_rotate=False`.

## Root Cause

The single-file branch passes `not args.no_auto_rotate` as the final `process_one` argument. The folder branch omits that argument, so `process_one` silently uses its default `auto_rotate=True`.

## Goals

- Pass `auto_rotate=False` to every folder item when `--no-auto-rotate` is present.
- Preserve the current default `auto_rotate=True` when the flag is absent.
- Add a regression test that exercises the real CLI argument parsing and observes the `process_one` call.

## Non-Goals

- No changes to the GUI, rotation estimator, image decoding, or output-path behavior.
- No general refactor of the long `process_one` argument list.
- No new CLI option or dependency.

## Approaches Considered

1. **Add one explicit keyword argument to the folder call — selected.** Pass `auto_rotate=not args.no_auto_rotate`. This directly fixes the missing propagation and avoids relying on another positional argument in an already long call.
2. **Refactor CLI processing into a shared options object.** This could reduce future argument drift, but it expands the change far beyond this isolated defect and raises regression risk.

## Implementation and Verification

Add focused folder-mode tests for both flag states, first confirming the disabled case fails against the current code. Then add the explicit keyword argument, run the focused CLI tests, and run the complete source test suite. Commit the test and minimal production change together on `fix/output-collision`.
