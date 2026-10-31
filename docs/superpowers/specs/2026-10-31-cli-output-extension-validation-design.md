# CLI Explicit Output Extension Validation Design

## Intent

Prevent the command line from writing JPEG or TIFF bytes under a misleading explicit filename extension.

## Root Cause

For a single input with `--output-format auto`, the CLI currently treats `.tif` and `.tiff` as TIFF and every other suffix as JPEG. When an explicit format is supplied, it does not compare that format with the `--output` suffix. Consequently, `result.png` can contain JPEG data and `--output-format JPEG --output result.tif` can create a JPEG disguised as TIFF.

## Goals

- Validate explicit single-file `--output` suffixes before calling `process_one`.
- In `auto` mode, accept `.jpg`, `.jpeg`, `.tif`, and `.tiff` case-insensitively and derive the matching format.
- With explicit `JPEG` or `TIFF16`, require a matching suffix.
- Produce a clear argparse error and perform no decoding or output write on invalid combinations.

## Non-Goals

- Do not add PNG encoding or change supported input formats.
- Do not rename an explicit user path automatically.
- Do not change generated GUI/folder output names or low-level `write_image` APIs.

## Approach

Add a small standard-library helper in `film_crop.py` that returns the resolved output format or raises `ValueError` with the allowed suffixes. The CLI catches that validation through `parser.error` before `process_one`. This keeps format policy testable and avoids silently overriding either the requested format or filename.

## Verification

Regression tests exercise real argument parsing with `process_one` mocked only at the image-processing boundary. They cover unsupported auto suffixes, explicit mismatches, accepted JPEG/TIFF suffixes, and case-insensitive extensions, followed by the full source suite.
