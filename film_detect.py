"""Experimental mixed-film detector. Ratios are inferred from candidate frames.

Orange-mask normalization is used only for detection. Source colors are kept.
Format labels are geometric guesses; use review flags for ambiguous frames.
"""
import cv2
import numpy as np
import math
import film_crop as f

def prepare(im):
 b,g,r=cv2.split(im.astype(np.float32));orange=(r>g*1.2)&(g>b*1.15)&(r>65)
 neg=np.mean(orange)>.25
 if neg:
  v=im.astype(np.float32)
  # Invert only for detection; the delivered photo retains its source pixels.
  hi=np.percentile(v,90,axis=(0,1));v=np.clip(1-v/np.maximum(hi,1),0,1)
  im=(v*255).astype(np.uint8)
 return im,neg

def analyze(im):
 s,sc=f.resize_for_detection(im,1200);s,neg=prepare(s);h,w=s.shape[:2];g=cv2.cvtColor(s,cv2.COLOR_BGR2GRAY);g=cv2.GaussianBlur(g,(0,0),1)
 boxes=set()
 for channel in [g,*cv2.split(s)]:
  for t in [3,8,16,24,40,64,90,120,160,200,235,248]:
   cs,_=cv2.findContours((channel>t).astype(np.uint8)*255,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
   for c in cs:
    x,y,cw,ch=cv2.boundingRect(c);a=cw*ch/(w*h)
    if .15<a<.97 and x<w*.5<x+cw and y<h*.5<y+ch:boxes.add((x,y,cw,ch))
 # Bright paired rows of perforations provide independent 135 evidence.
 holes=[]
 raw=f.resize_for_detection(im,1200)[0]
 # Camera white balance can make transmitted light cyan; grayscale 220 misses it.
 # Search bright channels, requiring two regular rows with matching pitch.
 brightness=np.max(raw,axis=2)
 hole_box=None
 for threshold in [220,180,150,120]:
  found=[]
  cs,_=cv2.findContours((brightness>threshold).astype(np.uint8)*255,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  for c in cs:
   hx,hy,hw,hh=cv2.boundingRect(c)
   if .02*w<hw<.06*w and .04*h<hh<.12*h and .4<hw/hh<.9 and cv2.contourArea(c)/(hw*hh)>.75:
    found.append((hx+hw/2,hy+hh/2,hw,hh))
  top=sorted(q for q in found if q[1]<.25*h)
  bottom=sorted(q for q in found if q[1]>.75*h)
  if len(top)<6 or len(bottom)<6:continue
  td=np.diff([q[0] for q in top]);bd=np.diff([q[0] for q in bottom])
  pitch=float(np.median(td));bp=float(np.median(bd))
  sep=float(np.median([q[1] for q in bottom])-np.median([q[1] for q in top]))
  if np.std(td)/pitch>.15 or np.std(bd)/bp>.15 or abs(bp/pitch-1)>.08 or not 5.3<sep/pitch<6.7:continue
  cx=float(np.mean([q[0] for q in top+bottom]));cy=(np.median([q[1] for q in top])+np.median([q[1] for q in bottom]))/2
  fw=pitch*36/4.75;fh=fw/1.5
  hole_box=(round(cx-fw/2),round(cy-fh/2),round(fw),round(fh))
  boxes.add(hole_box)
  break
 # Rectangular projections cover fragmented scenes (dark monochrome, etc).
 xp,yp=f.edge_profiles(s);xs=f.nms_peaks(xp,16,12);ys=f.nms_peaks(yp,16,12)
 for x0,_ in xs:
  for x1,_ in xs:
   if x1-x0<.35*w or not x0<w*.5<x1:continue
   for y0,_ in ys:
    for y1,_ in ys:
     if y1-y0<.35*h or not y0<h*.5<y1:continue
     boxes.add((x0,y0,x1-x0+1,y1-y0+1))
 result=[]
 for x,y,cw,ch in boxes:
  r=max(cw,ch)/min(cw,ch);fm=min(f.FORMATS,key=lambda k:abs(math.log(max(f.FORMATS[k],1/f.FORMATS[k])/r)));err=abs(math.log(max(f.FORMATS[fm],1/f.FORMATS[fm])/r))
  if err>.04:continue
  if hole_box is not None:
   if fm!='135' or cw<.9*hole_box[2] or ch<.9*hole_box[3] or cw>1.12*hole_box[2] or ch>1.12*hole_box[3]:continue
  # Robust median boundary strips skip corners, holes and frame lettering.
  k=4;ya,yb=y+int(ch*.15),y+int(ch*.85);xa,xb=x+int(cw*.15),x+int(cw*.85)
  vals=[]
  if min(x,y,w-x-cw,h-y-ch)<2*k:continue
  for inside,outside in [
   (g[ya:yb,x+k:x+2*k],g[ya:yb,x-2*k:x-k]),
   (g[ya:yb,x+cw-2*k:x+cw-k],g[ya:yb,x+cw+k:x+cw+2*k]),
   (g[y+k:y+2*k,xa:xb],g[y-2*k:y-k,xa:xb]),
   (g[y+ch-2*k:y+ch-k,xa:xb],g[y+ch+k:y+ch+2*k,xa:xb])]:
   vals.append(float(np.median(inside))-float(np.median(outside)))
  outs=[g[ya:yb,x-2*k:x-k],g[ya:yb,x+cw+k:x+cw+2*k],g[y-2*k:y-k,xa:xb],g[y+ch+k:y+ch+2*k,xa:xb]]
  surround=sum(float(np.mean(a<30)) for a in outs)
  edge=sum(np.sign(v)*np.sqrt(abs(v)/255) for v in vals)
  score=edge-18*err+2.0*cw*ch/(w*h)+min(vals)/255+2*surround
  result.append({'box':[x,y,cw,ch],'format':fm,'measured':cw/ch,'error':err,'score':score,'jumps':vals,'estimated':bool(hole_box is not None and (x,y,cw,ch)==hole_box)})
 result.sort(key=lambda v:v['score'],reverse=True)
 if result:
  top=result[0];tx,ty,tw,th=top['box']
  # A near-equivalent rectangle enclosing the same picture is safer than
  # an internal scene edge; keep the alternative visible in the report.
  enclosing=[]
  for q in result:
   x,y,cw,ch=q['box'];overlap=max(0,min(x+cw,tx+tw)-max(x,tx))*max(0,min(y+ch,ty+th)-max(y,ty))/(tw*th)
   if q['score']>=top['score']-1.1 and overlap>.94 and cw*ch>tw*th*1.04 and cw*ch<tw*th*1.2:
    enclosing.append(q)
  if enclosing:
   chosen=max(enclosing,key=lambda q:q['box'][2]*q['box'][3]);result.remove(chosen);result.insert(0,chosen);chosen['ambiguous']=True
 return result,sc,neg


def detect_auto(image):
    candidates,scale,negative = analyze(image)
    if not candidates:
        raise RuntimeError("No plausible film frame found; specify --format or --corners")
    best = candidates[0]
    x,y,w,h = best['box']
    ratio = f.FORMATS[best['format']]
    ratio = max(ratio,1/ratio) if w>=h else min(ratio,1/ratio)
    alternative = next((q for q in candidates[1:] if q['format'] != best['format']),None)
    reasons=[]
    if best.get('estimated'): reasons.append('boundary estimated from sprocket spacing')
    if best.get('ambiguous'): reasons.append('enclosing frame selected over scene edge')
    if alternative and best['score']-alternative['score']<.6:
        reasons.append('competing format: '+alternative['format'])
    if best['error']>.025: reasons.append('measured ratio differs from preset by over 2.5%')
    if min(best['jumps'])<3: reasons.append('one or more frame edges have low contrast')
    return {
        'format':best['format'], 'ratio':ratio,
        'measured_ratio':best['measured'],
        'bounds':[x/scale,(x+w-1)/scale,y/scale,(y+h-1)/scale],
        'negative_hint':bool(negative),
        'needs_review':bool(reasons), 'review_reasons':reasons,
        'alternative_format':alternative['format'] if alternative else None,
        'score':float(best['score']),
    }


