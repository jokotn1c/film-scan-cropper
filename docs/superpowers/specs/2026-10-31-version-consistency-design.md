# Release Version Consistency Design

## Intent

Make every in-repository application, build, artifact, and user-facing version reference identify the current release as `1.9.1`.

## Evidence and Authority

The GitHub release page title and the distributed Windows attachment identify the release as `1.9.1`. The Git tag remains `v1.9.0`, while `film_version.py` and documentation currently use `1.9`. For repository-controlled metadata, `film_version.VERSION = '1.9.1'` is the authoritative value. Changing or recreating the external Git tag is out of scope.

## Goals

- Set the application and build version to `1.9.1` through `film_version.py`.
- Update Windows/macOS artifact documentation and workflow naming to `1.9.1`.
- Update the README and bundled Chinese instructions to display `1.9.1`.
- Add a focused consistency test so a partial future version update fails visibly.

## Non-Goals

- Do not modify, delete, or recreate the GitHub `v1.9.0` tag or release.
- Do not build or publish binaries in this task.
- Do not change image-processing behavior or dependencies.

## Approach

Use the existing `film_version.py` constant as the runtime/build source of truth and update the few human-readable or workflow strings that cannot import it. A standard-library test pins the intended release version and checks each repository-controlled reference. A dynamic workflow-output refactor was considered but rejected as unnecessary complexity for a small static release identifier.

## Verification

Establish RED with the consistency test against the current `1.9` files, update only version metadata and documentation, then run the focused test, full suite, compile check, and Git whitespace/status checks.
