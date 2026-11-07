"""Per-image detection data shared by rotation and frame searches.

No global cache: image data and evidence live only for one locate operation.
Resampling and detector thresholds remain identical to the original pipeline.
"""
from functools import cached_property
import cv2
import numpy as np
from film_crop import resize_for_detection


class DetectionContext:
    def __init__(self, image):
        self.small, self.scale = resize_for_detection(image, 1200)
        self.rectangle_cache = {}

    def rectangle_data(self, channel_name, threshold, channel):
        """Share contour scans while keeping rotation and frame votes separate."""
        key = (channel_name, threshold)
        if key not in self.rectangle_cache:
            h, w = channel.shape
            contours, _ = cv2.findContours(
                (channel > threshold).astype(np.uint8) * 255,
                cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            votes = []
            boxes = []
            for contour in contours:
                bx, by, bw, bh = cv2.boundingRect(contour)
                bounding_area = bw * bh / (w * h)
                if .15 < bounding_area < .97 and bx < w * .5 < bx + bw and by < h * .5 < by + bh:
                    boxes.append((bx, by, bw, bh))
                # A rotated rectangle cannot have more area than its bounding box.
                if bounding_area <= .18:
                    continue
                (x, y), (cw, ch), angle = cv2.minAreaRect(contour)
                if min(cw, ch) <= 0:
                    continue
                area = cw * ch / (w * h)
                aspect = max(cw, ch) / min(cw, ch)
                if not (.18 < area < .95 and abs(x / w - .5) < .2 and abs(y / h - .5) < .2
                        and (1 <= aspect < 1.85 or abs(aspect - 65 / 24) < .12
                             or abs(aspect - 56 / 24) < .10)):
                    continue
                rectangularity = cv2.contourArea(contour) / (cw * ch)
                if rectangularity < .92:
                    continue
                if bx <= 1 and by <= 1 and bx + bw >= w - 1 and by + bh >= h - 1:
                    continue
                angle = (angle + 45) % 90 - 45
                votes.append((angle, area * rectangularity))
            self.rectangle_cache[key] = (votes, boxes)
        return self.rectangle_cache[key]

    @cached_property
    def brightness(self):
        return np.max(self.small, axis=2)

    @cached_property
    def perforations(self):
        from film_sprockets import paired_perforations
        return paired_perforations(self.small, brightness=self.brightness)
