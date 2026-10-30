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

def strip_frame(image, requested_format=None):
 """Locate a complete central frame bracketed by two dark film gaps.

 High percentiles require the gaps to stay dark along most of their length;
 a median alone confuses a shadow within the picture with a film separator.
 Work in both strip orientations, and require visible neighboring pictures.
 """
 gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
 found=[]
 for transpose in (False,True):
  g=gray.T if transpose else gray
  h,w=g.shape
  profile=np.percentile(g[int(.15*h):int(.85*h)],85,axis=0)
  floor=float(np.percentile(profile,5))
  dynamic=float(np.percentile(profile,95)-floor)
  threshold=floor+max(3.,.045*dynamic)
  mask=profile<threshold
  changes=np.diff(np.r_[False,mask,False].astype(np.int8))
  bands=[(int(a),int(b)) for a,b in zip(np.where(changes==1)[0],np.where(changes==-1)[0])
         if .008*w<=b-a<=.08*w and a>.03*w and b<.97*w]
  left=[q for q in bands if q[1]<.5*w]
  right=[q for q in bands if q[0]>.5*w]
  if not left or not right:continue
  a,x0=max(left,key=lambda q:q[1]);x1,b=min(right,key=lambda q:q[0])
  fw=x1-x0
  if not .3*w<fw<.85*w:continue
  step=max(4,int(.025*w))
  # Both gaps must separate pictures, not just surround one photograph.
  if min(float(np.median(profile[max(0,a-2*step):a-step])),
         float(np.median(profile[b+step:min(w,b+2*step)])))<threshold+max(5.,.065*dynamic):continue
  row=np.percentile(g[:,x0+int(.12*fw):x1-int(.12*fw)],75,axis=1).astype(np.float32)
  row=cv2.GaussianBlur(row.reshape(-1,1),(1,0),1.2).ravel()
  jump=row[6:]-row[:-6]
  top=int(np.argmax(jump[:int(.25*h)]))+3
  lo=int(.75*h)
  bottom=int(np.argmin(jump[lo:]))+lo+3
  if min(float(jump[top-3]),float(-jump[bottom-3]))<15:continue
  fh=bottom-top
  if fh<.5*h:continue
  measured=fw/fh
  # Broad inter-frame gaps without perforations indicate medium-format
  # strip geometry.  Avoid letting the almost identical half-frame ratio
  # displace 645 in this specific case.
  formats={k:r for k,r in f.FORMATS.items() if k not in f.PANORAMIC_FORMATS}
  medium_gap=min(x0-a,b-x1)>.035*min(fw,fh)
  if medium_gap and requested_format!='half':formats.pop('half',None)
  aspect=max(measured,1/measured)
  fmt=requested_format or min(formats,key=lambda k:abs(math.log(max(formats[k],1/formats[k])/aspect)))
  if fmt not in formats:continue
  error=abs(math.log(max(formats[fmt],1/formats[fmt])/aspect))
  if error>.035:continue
  box=[top,x0,fh,fw] if transpose else [x0,top,fw,fh]
  k=4
  jump_left=float(np.median(g[top+int(.15*fh):bottom-int(.15*fh),x0+k:x0+2*k])-
                  np.median(g[top+int(.15*fh):bottom-int(.15*fh),x0-2*k:x0-k]))
  jump_right=float(np.median(g[top+int(.15*fh):bottom-int(.15*fh),x1-2*k:x1-k])-
                   np.median(g[top+int(.15*fh):bottom-int(.15*fh),x1+k:x1+2*k]))
  jumps=[jump_left,jump_right,float(jump[top-3]),float(-jump[bottom-3])]
  if transpose:jumps=jumps[2:]+jumps[:2]
  found.append(dict(box=box,format=fmt,measured=box[2]/box[3],error=error,
                    score=12.-18*error,jumps=jumps,strip_frame=True,
                    strip_axis=1 if transpose else 0,
                    ambiguous_format=bool(medium_gap and fmt=='645')))
 return min(found,key=lambda q:q['error']) if found else None

def analyze(im, requested_format=None):
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
 strict_hole_geometry=False
 negative_edge_evidence=False
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
 if hole_box is None:
  from film_sprockets import paired_perforations
  evidence=paired_perforations(raw)
  if evidence:
   hole_box=tuple(evidence['box'])
   strict_hole_geometry=True
   negative_edge_evidence=(evidence.get('clipped',False) or evidence.get('adaptive',False)
                           or np.percentile(brightness,95)<120) and evidence['polarity']=='bright'
   boxes.add(hole_box)
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
   if fm not in {'135',*f.PANORAMIC_FORMATS}:continue
   hx,hy,hw,hh=hole_box
   factor=f.FORMATS[fm]/1.5
   expected_w,expected_h=(hw*factor,hh) if hw>hh else (hw,hh*factor)
   if not (.9*expected_w<cw<1.12*expected_w and .9*expected_h<ch<1.12*expected_h):continue
   if strict_hole_geometry:
    hx,hy,hw,hh=hole_box
    # Hole pitch constrains size, but incomplete hole rows do not precisely
    # locate the frame along the film strip. Across the strip it is reliable.
    xtol,ytol=(.15,.05) if hw>hh else (.05,.15)
    if abs((x+cw/2)-(hx+hw/2))>xtol*hw or abs((y+ch/2)-(hy+hh/2))>ytol*hh:continue
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
  # Perforations establish the 24 mm height, not the exposed frame length.
  # Panoramic frames need four visible boundaries so a long strip containing
  # neighboring 135 frames is never inferred from hole spacing alone.
  if fm in f.PANORAMIC_FORMATS and hole_box is not None:
   if min(vals)>3:pass
   elif max(vals)<-3:vals=[-v for v in vals]
   else:continue
  surround=sum(float(np.mean(a<30)) for a in outs)
  # A monochrome negative can be darker than its unexposed film surround.
  # Only reverse edge evidence after independent paired-hole geometry has
  # constrained the frame; otherwise internal dark scene boxes can win.
  signed_vals=[-v for v in vals] if negative_edge_evidence and np.median(vals)<-3 else vals
  # Absolute blackness is exposure-dependent and becomes misleading on dim
  # copies: a dark part of the picture must not count as a film border.
  if negative_edge_evidence:surround=0
  edge=sum(np.sign(v)*np.sqrt(abs(v)/255) for v in signed_vals)
  score=edge-18*err+2.0*cw*ch/(w*h)+min(signed_vals)/255+2*surround
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
 if hole_box is None and not neg:
  strip=strip_frame(s,requested_format)
  # Replace a square scene box or a box crossing a verified film gap.
  # Non-square candidates with matching orientation keep their established
  # bounds unless the user explicitly requested this strip format.
  if strip is not None and result:
   axis=strip['strip_axis'];start=strip['box'][axis];length=strip['box'][axis+2]
   oldstart=result[0]['box'][axis];oldlength=result[0]['box'][axis+2]
   spans_gap=(oldstart<start-.08*length or oldstart+oldlength>start+1.08*length)
   crossed_orientation=(result[0]['measured']>=1)!=(strip['measured']>=1)
   if (result[0]['format']=='66' or
       (spans_gap and crossed_orientation) or
       (requested_format==strip['format'] and spans_gap)):
    result.insert(0,strip)
 # When most of a square frame merges into its black surround, internal
 # scene rectangles have no four independent boundaries. Use separately
 # verified light-table and visible-picture evidence instead.
 if hole_box is None:
  from film_darkframe import dark_frame, FormatRequired
  evidence=dark_frame(raw)
  if evidence:
   if requested_format is None:
    raise FormatRequired('低亮度画面的边界不完整，请指定画幅后重试。')
   dark_candidate=dark_frame(raw,f.FORMATS[requested_format])
   if dark_candidate is None:
    raise FormatRequired('所选画幅无法在可见底片范围内推算，请检查画幅或更换翻拍图片。')
   dark_candidate['format']=requested_format
   result.insert(0,dark_candidate)
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
    if best.get('estimated_dark'): reasons.append('dark square frame boundary estimated from film strip')
    if best.get('estimated'): reasons.append('boundary estimated from sprocket spacing')
    if best.get('ambiguous'): reasons.append('enclosing frame selected over scene edge')
    if best.get('ambiguous_format'): reasons.append('645/half-frame geometry is close; check format')
    if alternative and not best.get('estimated_dark') and best['score']-alternative['score']<.6:
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


