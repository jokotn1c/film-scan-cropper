"""Per-image detection data shared by rotation and frame searches.

No global cache: image data and evidence live only for one locate operation.
Resampling and detector thresholds remain identical to the original pipeline.
"""
from functools import cached_property
import numpy as np
from film_crop import resize_for_detection


class DetectionContext:
    def __init__(self, image):
        self.small, self.scale = resize_for_detection(image, 1200)

    @cached_property
    def brightness(self):
        return np.max(self.small, axis=2)

    @cached_property
    def perforations(self):
        from film_sprockets import paired_perforations
        return paired_perforations(self.small, brightness=self.brightness)
