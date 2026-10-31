"""Plan generated output paths without importing the image-processing stack."""

from pathlib import Path


def output_path(folder, source, output_format, suffix="crop"):
    """Build the default generated output path for one source image."""
    extension = ".tif" if output_format == "TIFF16" else ".jpg"
    safe_suffix = suffix.replace(":", "x").replace("/", "_").replace("\\", "_")
    return Path(folder) / f"{Path(source).stem}_{safe_suffix}{extension}"


def _path_key(path):
    """Return the case-insensitive key used for output reservations."""
    return str(Path(path).absolute()).casefold()


def _existing_keys(parent):
    """Return case-insensitive keys for every filesystem entry in parent."""
    parent = Path(parent)
    if not parent.is_dir():
        return set()
    return {_path_key(child) for child in parent.iterdir()}


def plan_output_paths(candidates):
    """Reserve collision-free paths in input order using _2, _3, ... suffixes."""
    planned = []
    occupied = set()
    scanned_parents = set()

    for value in candidates:
        base = Path(value)
        parent_key = _path_key(base.parent)
        if parent_key not in scanned_parents:
            occupied.update(_existing_keys(base.parent))
            scanned_parents.add(parent_key)

        candidate = base
        number = 2
        while _path_key(candidate) in occupied:
            candidate = base.with_name(f"{base.stem}_{number}{base.suffix}")
            number += 1

        planned.append(candidate)
        occupied.add(_path_key(candidate))

    return planned


def require_output_available(path):
    """Reject a path if any same-name entry already occupies it."""
    path = Path(path)
    if _path_key(path) in _existing_keys(path.parent):
        raise FileExistsError(f"Output path already exists: {path}")
    return path
