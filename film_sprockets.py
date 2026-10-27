"""Paired perforation evidence, independent of image orientation and polarity."""
import math
import cv2
import numpy as np


def paired_perforations(image):
    """Return estimated picture bounds and roll in this preview's coordinates.

    Both bright transmitted holes and dark holes in converted positives count.
    Two regular rows must agree on pitch, angle, phase and physical separation.
    """
    # Keep complete-hole evidence first; clipped-hole geometry is less precise.
    return _paired(image, False) or _paired(image, True) or _paired(image, False, adaptive=True)


def _paired(image, allow_clipped, adaptive=False):
    for transpose in (False, True):
        s = cv2.transpose(image) if transpose else image
        h, w = s.shape[:2]
        for polarity, channel, thresholds in (
            ('bright', s.max(axis=2), (220, 180, 150, 120)),
            ('dark', s.max(axis=2), (12, 20, 28, 36, 48, 64)),
        ):
            if adaptive:
                # Underexposed copies may have no pixels above the fixed
                # thresholds. Geometry still has to pass every paired-row test.
                thresholds = sorted(set(int(v) for v in np.percentile(channel,
                                    (15, 25, 40, 55, 70, 80, 90, 95))))
            for threshold in thresholds:
                mask = channel > threshold if polarity == 'bright' else channel < threshold
                contours, _ = cv2.findContours(mask.astype(np.uint8)*255,
                                               cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                points = []
                clipped_count = 0
                for c in contours:
                    x, y, cw, ch = cv2.boundingRect(c)
                    complete = .025*h < ch < .15*h and .35 < cw/ch < .95
                    clipped = (allow_clipped and (y == 0 or y+ch == h)
                               and .005*h < ch < cw*2.79/1.98)
                    if not (.015*w < cw < .08*w and (complete or clipped)
                            and x > 0 and x+cw < w
                            and cv2.contourArea(c)/(cw*ch) > .7):
                        continue
                    moments = cv2.moments(c)
                    cx, cy = moments['m10']/moments['m00'], moments['m01']/moments['m00']
                    if clipped:
                        # Standard 135 perforations measure 1.98 x 2.79 mm.
                        # Use the visible inner edge, not the truncated centroid.
                        cy = y+ch-cw*2.79/1.98/2 if y == 0 else y+cw*2.79/1.98/2
                        clipped_count += 1
                    points.append((cx, cy))
                if allow_clipped and clipped_count < 6:
                    continue
                rows = [sorted(p for p in points if p[1] < .28*h),
                        sorted(p for p in points if p[1] > .72*h)]
                if adaptive:
                    # A film strip can be off-center on a large copy canvas.
                    groups = []
                    for point in sorted(points, key=lambda p:p[1]):
                        if not groups or point[1]-groups[-1][-1][1] > .035*h:
                            groups.append([])
                        groups[-1].append(point)
                    groups = sorted(groups, key=len, reverse=True)[:2]
                    if len(groups) != 2:
                        continue
                    rows = [sorted(row) for row in sorted(groups, key=lambda r:np.mean(r,axis=0)[1])]
                fits = []
                for row in rows:
                    if len(row) < 6:
                        break
                    p = np.asarray(row)
                    slopes = [(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(p)
                              for b in p[i+1:] if b[0]-a[0] > .2*w]
                    if not slopes:
                        break
                    slope = np.median(slopes)
                    intercept = np.median(p[:,1]-slope*p[:,0])
                    # Film curl and estimating a missing outer edge add uncertainty.
                    tolerance = max(3, .1*np.median(np.diff(p[:,0]))) if allow_clipped else 3
                    p = p[np.abs(p[:,1]-slope*p[:,0]-intercept) < tolerance]
                    if len(p) < 6:
                        break
                    slope, intercept = np.polyfit(p[:,0], p[:,1], 1)
                    gaps = np.diff(p[:,0]); pitch = np.median(gaps)
                    if np.std(gaps)/pitch > .12 or np.ptp(p[:,0]) < .45*w:
                        break
                    fits.append((slope, intercept, pitch, p))
                if len(fits) != 2:
                    continue
                a,b,p,top = fits[0]; c,d,q,bottom = fits[1]
                slope = (a+c)/2
                sep = (d-b)/math.sqrt(1+slope*slope)
                step = (p+q)/2 * math.sqrt(1+slope*slope)
                angle = math.degrees(math.atan(slope))
                if (abs(math.degrees(math.atan(a)-math.atan(c))) > (1.5 if allow_clipped else .3)
                        or abs(p/q-1) > .08 or not 5.3 < sep/step < 6.7
                        or abs(angle) > 10):
                    continue
                # Match the same holes across rows; avoid phase-shifted highlights.
                top_along=top[:,0]+slope*top[:,1]
                bottom_along=bottom[:,0]+slope*bottom[:,1]
                phase = np.median([min(abs(bottom_along-x)) for x in top_along])
                if phase > .3*(p+q)/2:
                    continue
                cx = float(np.mean(np.concatenate([top,bottom])[:,0]))
                cy = slope*cx + (b+d)/2
                # RETR_LIST also finds bright holes enclosed by a dark mask.
                # Determine actual contrast rather than the threshold direction.
                contrasts=[]
                for row in (top,bottom):
                    for px,py in row:
                        iy=int(np.clip(round(py),0,h-1))
                        ix=int(np.clip(round(px),0,w-1))
                        ox=int(np.clip(round(px+(p+q)/4),0,w-1))
                        contrasts.append(float(channel[iy,ix])-float(channel[iy,ox]))
                actual_polarity='bright' if np.median(contrasts)>0 else 'dark'
                fw = step*36/4.75; fh = fw/1.5
                box = [cx-fw/2, cy-fh/2, fw, fh]
                if transpose:
                    x,y,bw,bh = box; box = [y,x,bh,bw]
                return {'box': [round(v) for v in box],
                        'angle': -angle if transpose else angle,
                        'polarity': actual_polarity, 'transposed': transpose,
                        'adaptive': adaptive,
                        'clipped': allow_clipped,
                        # Missing outer edges make the recovered row slope too
                        # uncertain to use as an automatic deskew measurement.
                        'angle_reliable': not allow_clipped}
    return None
