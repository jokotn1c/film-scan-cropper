"""Estimate small copy-stage roll from film rectangles or paired perforations.
Only the detection preview is rotated; source pixels are resampled once at crop.
"""
import math
import cv2
import numpy as np
from film_crop import resize_for_detection
from film_detect import prepare

MAX_ROLL = 10.0

def _hole_angle(s):
    # Work with the long sensor axis horizontal, also covering portrait copies.
    portrait = s.shape[0] > s.shape[1]
    a = cv2.transpose(s) if portrait else s
    h, w = a.shape[:2]
    for threshold in (220, 180, 150):
        contours, _ = cv2.findContours((a.max(axis=2)>threshold).astype(np.uint8)*255,
                                      cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        points = []
        for c in contours:
            (x,y),(cw,ch),_ = cv2.minAreaRect(c)
            lo,hi = min(cw,ch),max(cw,ch)
            if lo > 0 and .015*w<lo<.07*w and .035*h<hi<.14*h and .35<lo/hi<.9 and cv2.contourArea(c)/(lo*hi)>.7:
                points.append((x,y))
        rows = [sorted(p for p in points if p[1]<.28*h),
                sorted(p for p in points if p[1]>.72*h)]
        fits = []
        for row in rows:
            if len(row)<6: break
            p = np.asarray(row)
            # Robust pairwise slope then reject lettering and unrelated highlights.
            slopes = [(b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(p) for b in p[i+1:] if b[0]-a[0]>.2*w]
            if not slopes: break
            slope = np.median(slopes); intercept = np.median(p[:,1]-slope*p[:,0])
            p = p[np.abs(p[:,1]-slope*p[:,0]-intercept)<3]
            if len(p)<6: break
            slope,intercept = np.polyfit(p[:,0],p[:,1],1)
            pitch = np.diff(p[:,0]); step = np.median(pitch)
            if np.std(pitch)/step>.12 or np.ptp(p[:,0])<.45*w: break
            fits.append((slope,intercept,step,len(p)))
        if len(fits)!=2: continue
        a0,b0,p0,n0 = fits[0]; a1,b1,p1,n1 = fits[1]
        if abs(math.degrees(math.atan(a0)-math.atan(a1)))>.3 or abs(p0/p1-1)>.08: continue
        sep = (b1-b0)/math.sqrt(1+((a0+a1)/2)**2)
        pitch = (p0+p1)/2*math.sqrt(1+((a0+a1)/2)**2)
        if not 5.3<sep/pitch<6.7: continue
        angle = math.degrees(math.atan((a0+a1)/2))
        return (-angle if portrait else angle), 'paired_sprockets'
    return None

def estimate_rotation(preview):
    s,_ = resize_for_detection(preview,1200)
    holes = _hole_angle(s)
    if holes is None:
        from film_sprockets import paired_perforations
        evidence = paired_perforations(s)
        if evidence and evidence.get('angle_reliable', True):
            holes = evidence['angle'], 'paired_sprockets'
    if holes:
        angle,method = holes
        return dict(angle=angle, method=method, confident=abs(angle)<=MAX_ROLL)
    s,_ = prepare(s); h,w = s.shape[:2]
    gray = cv2.cvtColor(s,cv2.COLOR_BGR2GRAY)
    votes = []
    for channel in (gray,*cv2.split(s)):
        for t in (8,16,32,64,90,120,160,200,235):
            contours,_ = cv2.findContours((channel>t).astype(np.uint8)*255,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                (x,y),(cw,ch),angle = cv2.minAreaRect(c)
                if min(cw,ch)<=0: continue
                area = cw*ch/(w*h); aspect=max(cw,ch)/min(cw,ch)
                if not (.18<area<.95 and abs(x/w-.5)<.2 and abs(y/h-.5)<.2
                        and (1<=aspect<1.85 or abs(aspect-65/24)<.12 or abs(aspect-56/24)<.10)): continue
                rectangularity=cv2.contourArea(c)/(cw*ch)
                if rectangularity<.92: continue
                # Image-boundary rectangles provide no independent roll evidence.
                bx,by,bw,bh=cv2.boundingRect(c)
                if bx<=1 and by<=1 and bx+bw>=w-1 and by+bh>=h-1: continue
                angle=(angle+45)%90-45
                votes.append((angle,area*rectangularity))
    if not votes: return dict(angle=0.,method='unavailable',confident=False)
    cluster=max(([v for v in votes if abs(v[0]-a)<.3] for a,_ in votes),key=lambda c:sum(v[1] for v in c))
    angle=float(np.median([v[0] for v in cluster]))
    return dict(angle=angle,method='film_rectangle',confident=len(cluster)>=4 and abs(angle)<=MAX_ROLL)

def deskew_preview(preview, angle):
    h,w=preview.shape[:2]
    matrix=cv2.getRotationMatrix2D(((w-1)/2,(h-1)/2),angle,1.)
    # Expand the detection canvas; never cut away a corner before locating it.
    c,s=abs(matrix[0,0]),abs(matrix[0,1])
    nw,nh=math.ceil(w*c+h*s),math.ceil(h*c+w*s)
    matrix[:,2]+=[(nw-w)/2,(nh-h)/2]
    small=cv2.warpAffine(preview,matrix,(nw,nh),flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)
    return small,cv2.invertAffineTransform(matrix)
