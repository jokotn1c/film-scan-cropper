"""Visible film-boundary evidence for dark copies; ratio is supplied by user."""
import cv2
import numpy as np


class FormatRequired(RuntimeError):
    pass


def dark_square_frame(image):
    """Compatibility helper used by older diagnostics; explicit 6x6 only."""
    candidate = dark_frame(image, 1.0)
    if candidate:
        candidate['format'] = '6x6'
    return candidate


def dark_frame(image, ratio=None):
    for turn in range(4):
        s=np.ascontiguousarray(np.rot90(image,turn))
        candidate=_dark_frame(s,ratio)
        if candidate:
            x,y,w,h=candidate['box'];ih,iw=image.shape[:2]
            if turn==1:x,y,w,h=iw-y-h,x,h,w
            elif turn==2:x,y=iw-x-w,ih-y-h
            elif turn==3:x,y,w,h=y,ih-x-w,h,w
            candidate['box']=[x,y,w,h]
            return candidate
    return None


def _dark_frame(image,ratio):
    # Look across both orientations; the exposed table must bound the strip
    # on two sides. A scene silhouette by itself cannot supply this evidence.
    for transposed in (False, True):
        s=cv2.transpose(image) if transposed else image
        gray=cv2.cvtColor(s,cv2.COLOR_BGR2GRAY)
        h,w=gray.shape
        rows=np.median(gray[:,int(.1*w):int(.9*w)],axis=1)
        table=float(np.percentile(rows,90))
        if table < 150:
            continue
        dark=rows < table*.85
        edges=np.diff(np.r_[False,dark,False].astype(int))
        bands=list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))
        # Bright sky may interrupt a row median inside the strip.
        if len(bands)>1:
            bands.append((bands[0][0],bands[-1][1]))
        for start,end in bands:
            length=end-start
            if not (.30 < length/w < 3.1 and start>.04*h and end<.96*h):
                continue
            if min(np.median(rows[:start]),np.median(rows[end:])) < table*.85:
                continue
            region=gray[start:end]
            if np.mean(region<30)<.5:
                continue
            # Recover the visible sky/picture envelope across several thresholds.
            # The frame's missing dark bottom is inferred, never from a roof or
            # horizon cutting through the subject.
            proposals=[]
            for threshold in (64,80,100,120):
                mask=(region>threshold).astype(np.uint8)*255
                margin=max(1,round(.02*w))
                mask[:round(.035*length)]=0;mask[-round(.035*length):]=0
                mask[:,:margin]=0;mask[:,-margin:]=0
                contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                for c in contours:
                    x,y,cw,ch=cv2.boundingRect(c)
                    if not (.84*w<cw<.98*w and .025*length<y<.12*length
                            and ch>.08*length and cv2.contourArea(c)>.03*w*length
                            and x>.015*w and x+cw<.99*w):
                        continue
                    # Ignore isolated lettering: both sides need sustained picture
                    # support rather than just one bright corner reaching outward.
                    proposals.append((x,start+y,cw))
            if len(proposals)<2:
                continue
            widest=max(p[2] for p in proposals)
            proposals=[p for p in proposals if p[2]>.95*widest]
            if len(proposals)<2:
                continue
            if np.max(np.ptp(np.asarray(proposals),axis=0))>.06*w:
                continue
            # Vertical boundaries remain visible in the upper part, even when
            # the lower picture has merged with black. Use signed edge support
            # there instead of a threshold-dependent sky contour's extremes.
            y=min(p[1] for p in proposals)
            upper=gray[round(y+.13*length):round(y+.28*length)]
            gx=cv2.Sobel(cv2.GaussianBlur(upper,(0,0),1),cv2.CV_32F,1,0,ksize=3)
            profile=np.median(gx,axis=0)
            lo,hi=round(.025*w),round(.12*w)
            x=lo+int(np.argmax(profile[lo:hi]))
            lo,hi=round(.94*w),round(.985*w)
            right=lo+int(np.argmin(profile[lo:hi]))
            if profile[x]<8 or profile[right]>-8:
                continue
            side=right-x
            # The top film edge can bow or slope independently of the outer
            # strip. Fit its visible bright envelope, rejecting hanging leaves,
            # then place a square fully inside the sloping picture boundary.
            points=[]
            for col in range(x+round(.03*side),right-round(.03*side),8):
                visible=np.flatnonzero(gray[round(y):round(y+.16*length),col]>64)
                if len(visible):points.append((col,y+visible[0]))
            points=np.asarray(points)
            best=None
            for i,a in enumerate(points):
                for b in points[i+1:]:
                    if b[0]-a[0]<.4*side:continue
                    slope=(b[1]-a[1])/(b[0]-a[0])
                    if abs(slope)>.2:continue
                    offset=a[1]-slope*a[0]
                    inliers=np.abs(points[:,1]-slope*points[:,0]-offset)<4
                    count=int(inliers.sum())
                    if best is None or count>best[0]:best=(count,inliers)
            if best is None or best[0]<.5*len(points):
                continue
            slope,offset=np.polyfit(points[best[1],0],points[best[1],1],1)
            y=max(slope*x+offset,slope*right+offset)+2
            if ratio is None:
                height=min(end-y-2,side)
            else:
                heights=[side/ratio,side*ratio]
                # A panoramic crop can use only the visible upper portion of a
                # very dark frame; the selected ratio supplies the missing
                # height. Keep enough room for the requested height without
                # confusing an isolated scene detail with the full frame.
                heights=[v for v in heights if .20*length<v<end-y]
                if not heights:
                    continue
                height=max(heights)
            if y+height>end:
                continue
            box=[round(x),round(y),round(side),round(height)]
            if transposed:
                x,y,bw,bh=box;box=[y,x,bh,bw]
            return {'box':box,'format':None,'measured':box[2]/box[3],'error':0.,
                    'score':0.,'jumps':[0.]*4,'estimated_dark':True}
    return None
