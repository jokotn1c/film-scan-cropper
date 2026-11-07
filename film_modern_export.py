"""Modern UI compatibility entry for the shared processing pipeline."""
from dataclasses import replace
from film_engine import Options
from film_pipeline import process_image


def export_one(source, folder, options=Options(), box=None):
    if box is not None:
        options = replace(options, manual_box=tuple(box))
    if options.collision_policy is None:
        options = replace(options, collision_policy='number')
    return process_image(source, folder, options)
