"""Locate a picture using uniform film surround, independently of its format.

Work on source preview colors: orange scene lighting must not invert the
polarity of a positive copy. All distances below are preview-relative.
"""
import itertools
import math

import cv2
import numpy as np

from film_crop import FORMATS, nms_peaks


def boundary_profiles(image):
    """Return inward contrast and unsigned support for each of four sides."""
    profiles = []
    for axis in (0, 1):
        a = image if axis == 0 else image.transpose(1, 0, 2)
        h, w = a.shape[:2]
        a = cv2.GaussianBlur(a, (0, 0), 1).astype(np.float32)
        a = a[round(.08*h):round(.92*h)]
        # Six-pixel strips on either side suppress JPEG noise without hiding
        # a faint edge. Vectorize over positions rather than scanning pixels.
        sums = np.pad(np.cumsum(a, axis=1), ((0, 0), (1, 0), (0, 0)))
        strips = (sums[:, 6:] - sums[:, :-6]) / 6
        for reverse in (False, True):
            b = strips[:, ::-1] if reverse else strips
            outside, inside = b[:, :-14], b[:, 14:]
            diff = inside - outside
            spread = np.mean(np.percentile(outside, 80, axis=0) -
                             np.percentile(outside, 20, axis=0), axis=1)
            bright = np.median(outside.max(axis=2), axis=0)
            norm = (4 + .7*spread) / np.minimum(1, 60/np.maximum(bright, 1))
            signed = np.percentile(diff.max(axis=2), 85, axis=0) / norm
            absolute = np.percentile(np.abs(diff).max(axis=2), 75, axis=0) / norm
            lo, hi = max(2, round(.012*w)-10), min(len(signed), round(.35*w)-10)
            score = np.maximum(signed, .65*absolute)
            peaks = nms_peaks(score[lo:hi].astype(np.float32), 7, 12)
            profiles.append([(w-1-(p+lo+10) if reverse else p+lo+10,
                              float(signed[p+lo]), float(absolute[p+lo]))
                             for p, _ in peaks])
    return profiles


def surrounded_frame(image, requested_format=None):
    """Require four supported borders before classifying their geometry.

    A shadow may reverse one boundary's polarity. At least three edges must
    still independently separate a uniform dark surround from picture detail.
    No missing side is invented from a preferred aspect ratio.
    """
    h, w = image.shape[:2]
    sides = boundary_profiles(image)
    candidates = []
    formats = [requested_format] if requested_format else FORMATS
    for edges in itertools.product(*sides):
        x, right, y, bottom = (e[0] for e in edges)
        cw, ch = right-x+1, bottom-y+1
        if cw < .4*w or ch < .4*h or cw*ch < .38*w*h:
            continue
        signed = np.array([e[1] for e in edges])
        absolute = np.array([e[2] for e in edges])
        support = np.maximum(signed, absolute)
        if np.any((signed < 2) & (absolute > 2.5)):
            continue
        # A much stronger parallel transition inside this rectangle can be
        # the next frame after a gap. Do not join two exposures into one box.
        crosses_gap = False
        for side, selected in enumerate(edges):
            for position, strength, _ in sides[side]:
                depth = (position-selected[0]) * (1 if side in (0, 2) else -1)
                if depth > 15 and strength > max(6, 2*selected[1]):
                    crosses_gap = True
        if crosses_gap:
            continue
        if np.count_nonzero(signed > 2) < 3 or support.min() < .65:
            continue
        measured = cw/ch
        fmt = min(formats, key=lambda k: min(abs(math.log(measured/r))
                  for r in (FORMATS[k], 1/FORMATS[k])))
        error = min(abs(math.log(measured/r)) for r in (FORMATS[fmt], 1/FORMATS[fmt]))
        if error > .065:
            continue
        # Saturate strong edges: a fence inside the picture must not outweigh
        # a fainter complete outer frame with a larger supported area.
        score = float(np.minimum(support, 4).sum() + 5*cw*ch/(w*h) + 3*min(float(support.min()), 4) - 15*error)
        candidates.append(dict(box=[x,y,cw,ch], format=fmt, measured=measured,
                               error=error, score=score, jumps=signed.tolist(),
                               uniform_surround=True))
    return max(candidates, key=lambda q:q['score']) if candidates else None
