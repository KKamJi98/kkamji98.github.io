"""Paint-aware LOOP gate, independent of the CSS and other audit helpers.

Supported rail: axis-aligned solid equal-width T/B/L borders, unpainted R,
TL/BL elliptical radii and square right corners. Head: square-corner solid
R/B caret with a rigid 2D transform. Unsupported inputs fail closed.
Quarter-annuli are a union of thin convex cells, never filled corner hulls.
Each ellipse chord has Hausdorff error <= ARC_ERROR using |r''| <= max(rx,ry).
Polygon distances are exact for those cells; threshold ambiguity is unresolved.
DOM boxes and quads must share one viewport. Text scope is supplied endpoint
text plus optional element.text (collector should include all descendant text).
"""
import math
import re

ARC_ERROR = 0.0001
EPS = 1e-7


def _points(q):
    if len(q) != 8 or not all(math.isfinite(float(v)) for v in q):
        raise ValueError('invalid-quad')
    return list(zip(map(float, q[::2]), map(float, q[1::2])))


def _rect(b):
    x,y,w,h = (float(b[k]) for k in ('x','y','w','h'))
    if not all(map(math.isfinite,(x,y,w,h))) or w <= 0 or h <= 0:
        raise ValueError('invalid-box')
    return [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]


def _cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _point_segment(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def _inside(p, poly):
    cs=[_cross(a,b,p) for a,b in zip(poly,poly[1:]+poly[:1])]
    return min(cs)>=-EPS or max(cs)<=EPS


def _distance(p,q):
    if _inside(p[0],q) or _inside(q[0],p):
        return 0.0
    best=math.inf
    for a,b in zip(p,p[1:]+p[:1]):
        for c,d in zip(q,q[1:]+q[:1]):
            if _cross(a,b,c)*_cross(a,b,d)<0 and _cross(c,d,a)*_cross(c,d,b)<0:
                return 0.0
            best=min(best,_point_segment(a,c,d),_point_segment(b,c,d),_point_segment(c,a,b),_point_segment(d,a,b))
    return best


def _painted(b):
    w=float(b['width'])
    if not math.isfinite(w) or w<0:
        raise ValueError('border-width')
    c=b['color'].replace(' ','').lower()
    transparent=c=='transparent' or bool(re.fullmatch(r'rgba\([^,]+,[^,]+,[^,]+,0(?:\.0*)?\)',c))
    return w>0 and b['style'] not in ('none','hidden') and not transparent


def _radius(s,w,h):
    parts=s.split()
    if len(parts)==1: parts*=2
    if len(parts)!=2: raise ValueError('radius-syntax')
    out=[]
    for v,span in zip(parts,(w,h)):
        if not re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:px|%)',v):
            raise ValueError('radius-syntax')
        out.append(float(v[:-1])*span/100 if v.endswith('%') else float(v[:-2]))
    return out if all(out) else [0,0]


def _rail(st,p):
    q=_points(p['quad']); x,y=q[0]; right,bottom=q[2];w,h=right-x,bottom-y
    if w<=0 or h<=0 or any(math.dist(a,b)>EPS for a,b in zip(q,[(x,y),(right,y),(right,bottom),(x,bottom)])):
        raise ValueError('rail-not-axis-aligned')
    if st['transform'] not in ('none','matrix(1, 0, 0, 1, 0, 0)'):
        raise ValueError('rail-transform')
    borders=st['borders']
    if len(borders)!=4 or [_painted(b) for b in borders]!=[True,False,True,True]:
        raise ValueError('rail-border-paint')
    t=float(borders[0]['width'])
    if any(borders[i]['style']!='solid' or abs(float(borders[i]['width'])-t)>EPS for i in (0,2,3)):
        raise ValueError('rail-border-style-or-width')
    if t>=min(w,h)/2: raise ValueError('rail-thickness')
    rs=[_radius(s,w,h) for s in st['radii']]
    if len(rs)!=4 or any(rs[i]!=[0,0] for i in (1,2)) or not all(rs[i][0]>0 for i in (0,3)):
        raise ValueError('rail-corner-layout')
    ratios=[1.0]
    for span,total in ((w,rs[0][0]+rs[1][0]),(w,rs[3][0]+rs[2][0]),(h,rs[0][1]+rs[3][1]),(h,rs[1][1]+rs[2][1])):
        if total: ratios.append(span/total)
    scale=min(ratios);rs=[[a*scale,b*scale] for a,b in rs]
    if any(min(rs[i])<=t for i in (0,3)):
        raise ValueError('collapsed-inner-radius')
    cells=[]
    def rect(a,b,c,d):
        if c>a and d>b: cells.append([(a,b),(c,b),(c,d),(a,d)])
    rect(x+rs[0][0],y,right,y+t)
    rect(x+rs[3][0],bottom-t,right,bottom)
    rect(x,y+rs[0][1],x+t,bottom-rs[3][1])
    for i,start,cy in ((0,math.pi,y+rs[0][1]),(3,math.pi/2,bottom-rs[3][1])):
        rx,ry=rs[i];cx=x+rx
        n=max(1,math.ceil((math.pi/2)*math.sqrt(max(rx,ry)/(8*ARC_ERROR))))
        if n>8192: raise ValueError('radius-sampling-budget')
        def pt(a,inner):
            return (cx+(rx-t*inner)*math.cos(a),cy+(ry-t*inner)*math.sin(a))
        for j in range(n):
            a=start+j*math.pi/(2*n);b=start+(j+1)*math.pi/(2*n)
            cells.append([pt(a,0),pt(b,0),pt(b,1),pt(a,1)])
    return cells,(right,bottom-t/2),y+t/2,rs


def _head(st,p):
    transform=st['transform']
    match=re.fullmatch(r'matrix\(([^)]+)\)',transform)
    if not match: raise ValueError('head-transform')
    values=[float(v) for v in match[1].split(',')]
    if len(values)!=6 or not all(map(math.isfinite,values)): raise ValueError('head-transform')
    a,b,c,d,_,_=values
    if max(abs(a*a+b*b-1),abs(c*c+d*d-1),abs(a*c+b*d),abs(a*d-b*c-1))>1e-5:
        raise ValueError('head-nonrigid-transform')
    bs=st['borders']
    if len(bs)!=4 or [_painted(b) for b in bs]!=[False,True,True,False] or any(bs[i]['style']!='solid' for i in (1,2)):
        raise ValueError('head-border-style')
    if len(st['radii'])!=4 or any(_radius(r,1,1)!=[0,0] for r in st['radii']):
        raise ValueError('head-radius')
    q=_points(p['quad']);iq=_points(p['innerQuad'])
    u=(q[1][0]-q[0][0],q[1][1]-q[0][1]);v=(q[3][0]-q[0][0],q[3][1]-q[0][1])
    if abs(u[0]*v[0]+u[1]*v[1])>1e-3 or math.dist(q[2],(q[0][0]+u[0]+v[0],q[0][1]+u[1]+v[1]))>1e-3:
        raise ValueError('head-nonrectangular-transform')
    if math.hypot(*u)<EPS or math.hypot(*v)<EPS:
        raise ValueError('head-degenerate')
    uw,vw=math.hypot(*u),math.hypot(*v)
    if max(abs(u[0]/uw-a),abs(u[1]/uw-b),abs(v[0]/vw-c),abs(v[1]/vw-d))>1e-4:
        raise ValueError('head-transform-quad-mismatch')
    widths=[float(x['width']) for x in bs]
    if widths[1]+widths[3]>=uw or widths[0]+widths[2]>=vw:
        raise ValueError('head-inner-collapse')
    local=[(widths[3],widths[0]),(uw-widths[1],widths[0]),(uw-widths[1],vw-widths[2]),(widths[3],vw-widths[2])]
    expected=[(q[0][0]+u[0]*x/uw+v[0]*y/vw,q[0][1]+u[1]*x/uw+v[1]*y/vw) for x,y in local]
    if any(math.dist(x,y)>0.002 for x,y in zip(expected,iq)):
        raise ValueError('head-inner-quad-mismatch')
    # Geometry uses actual outer BR, not max(bbox) or the L-shape centroid.
    tip=q[2]
    orientation=(tip[0]>max(q[1][0],q[3][0])+EPS and q[1][1]<tip[1]<q[3][1] and abs(q[1][0]-q[3][0])<=0.5 and abs((q[1][1]+q[3][1])/2-tip[1])<=0.5)
    polys=[[q[1],q[2],iq[2],iq[1]],[q[2],q[3],iq[3],iq[2]]]
    return polys,tip,orientation


def inspect_loop(element):
    """Return findings/unresolved string codes and measured CSS-pixel metrics."""
    result: dict = dict(findings=[], unresolved=[], metrics={})
    for end in ('source','target'):
        ref=element.get(end+'Ref',{})
        if (ref.get('count')!=1 or not ref.get('id') or 'sd-node' not in ref.get('cls','').split() or element.get(end+'Inside') is not True):
            result['unresolved'].append('loop-'+end+'-endpoint')
    if result['unresolved']: return result
    try:
        if element.get('role')!='loop' or 'sd-loop' not in element.get('cls','').split(): raise ValueError('role')
        outer=_rect(element['box'])
        source=_rect(element['sourceRef']['box']);target=_rect(element['targetRef']['box'])
        if not all(_inside(p,outer) for p in source+target): raise ValueError('endpoint-outside-box')
        if source[0][1]<target[0][1]: raise ValueError('endpoint-order')
        for kind in ('before','after'):
            st=element[kind]
            if st.get('color') not in (None,'transparent','rgba(0, 0, 0, 0)') or st.get('background') not in (None,'none'):
                raise ValueError('pseudo-background')
        ps=element['pseudos']
        if len(ps)!=2 or sorted(p['type'] for p in ps)!=['after','before']: raise ValueError('pseudo-count')
        ps={p['type']:p for p in ps}
        rail,tail,rail_y,radii=_rail(element['before'],ps['before'])
        head,tip,orientation=_head(element['after'],ps['after'])
        if not orientation: result['findings'].append('loop-head-orientation')
        source_delta=source[0][0]-tail[0]
        target_delta=target[0][0]-tip[0]
        source_distance=math.hypot(source_delta,max(source[0][1]-tail[1],tail[1]-source[3][1],0))
        target_distance=math.hypot(target_delta,max(target[0][1]-tip[1],tip[1]-target[3][1],0))
        gap=min(_distance(a,b) for a in rail for b in head)
        texts=element['sourceRef']['text']+element['targetRef']['text']+element.get('text',[])
        if not texts: raise ValueError('missing-text-rects')
        clearance=min(_distance(p,_rect(b)) for b in texts for p in rail+head)
        m=result['metrics'];m.update(source_contact=source_distance,target_contact=target_distance,target_signed_gap=target_delta,source_signed_gap=source_delta,head_rail_alignment=abs(tip[1]-rail_y),head_rail_gap=gap,text_clearance=clearance,paint_distance_error_bound=ARC_ERROR,clamped_radii=radii)
        for name,value in (('source-contact',source_distance),('target-contact',target_distance),('head-rail-alignment',abs(tip[1]-rail_y))):
            if value>0.5+EPS: result['findings'].append('loop-'+name)
        for name,value,limit,minimum in (('head-rail-gap',gap,0.5,False),('text-clearance',clearance,4,True)):
            if (value+ARC_ERROR<limit if minimum else value-ARC_ERROR>limit): result['findings'].append('loop-'+name)
            elif abs(value-limit)<=ARC_ERROR: result['unresolved'].append('loop-'+name+'-numerical-boundary')
    except (KeyError,TypeError,ValueError,IndexError,OverflowError) as exc:
        result['unresolved'].append('loop-unsupported:'+str(exc))
    return result
