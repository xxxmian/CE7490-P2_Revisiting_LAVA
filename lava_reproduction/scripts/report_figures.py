"""High-contrast vector figures for the LAVA course report.

The caller passes the imported original ``scripts/build_report.py`` as ``source``.
No experiment values are copied into this module.  Each Drawing carries a
``_data_points`` tuple for exact, machine-readable provenance checks.
"""
from math import ceil, floor
from reportlab.graphics.shapes import Drawing, Group, Line, PolyLine, Circle, Rect, Polygon, String
from reportlab.lib.colors import HexColor, white

NAVY = HexColor('#153F70')
ORANGE = HexColor('#C75C13')
SLATE = HexColor('#3F4650')
INK = HexColor('#17212D')
AXIS = HexColor('#48515D')
GRID = HexColor('#DFE4E9')
THRESHOLD = HexColor('#9F332A')
FONT = 'Helvetica'
BOLD = 'Helvetica-Bold'


def _text(d, x, y, text, size=7.5, anchor='start', color=INK, bold=False):
    d.add(String(x, y, text, fontName=BOLD if bold else FONT,
                 fontSize=size, textAnchor=anchor, fillColor=color))


def _marker(d, shape, x, y, color, radius=2.5):
    kw = dict(fillColor=color, strokeColor=white, strokeWidth=.55)
    if shape == 'circle':
        d.add(Circle(x, y, radius, **kw))
    elif shape == 'square':
        d.add(Rect(x-radius, y-radius, 2*radius, 2*radius, **kw))
    else:
        r = radius * 1.15
        d.add(Polygon([x,y+r,x+r,y,x,y-r,x-r,y], **kw))


def _axes(d, left, bottom, plot_width, plot_height, low, high,
          ticks, xmap, xlabel='Prediction accuracy (%)', ylabel='Gain over Best-Fit (pp)'):
    def ymap(v):
        return bottom + (v-low)/(high-low) * plot_height
    count = int(round((high-low)/.2))
    for k in range(count+1):
        value = round(low + k*.2, 10)
        yy = ymap(value)
        zero = abs(value) < 1e-8
        d.add(Line(left,yy,left+plot_width,yy,
                   strokeColor=AXIS if zero else GRID,
                   strokeWidth=1.05 if zero else .45,
                   strokeDashArray=[3,2] if zero else None))
        label = '0.0' if zero else f'{value:+.1f}'
        _text(d,left-5,yy-2.5,label,7.5,'end')
    d.add(Line(left,bottom,left,bottom+plot_height,strokeColor=AXIS,strokeWidth=.7))
    d.add(Line(left,bottom,left+plot_width,bottom,strokeColor=AXIS,strokeWidth=.7))
    for value in ticks:
        xx = xmap(value)
        d.add(Line(xx,bottom,xx,bottom-3,strokeColor=AXIS,strokeWidth=.7))
        _text(d,xx,bottom-13,f'{100*value:.0f}',7.5,'middle')
    _text(d,left+plot_width/2,5,xlabel,8,'middle')
    group = Group()
    group.add(String(0,0,ylabel,fontName=FONT,fontSize=8,fillColor=INK,textAnchor='middle'))
    group.transform = (0,1,-1,0,10,bottom+plot_height/2)
    d.add(group)
    return ymap


def _series(d, points, accuracies, xmap, ymap, color, shape, offset=0):
    xy = [(xmap(x)+offset,ymap(p['mean'])) for x,p in zip(accuracies,points)]
    d.add(PolyLine([v for pair in xy for v in pair],strokeColor=color,
                   strokeWidth=1.65,strokeLineCap=1,strokeLineJoin=1))
    for (xx,yy), point in zip(xy,points):
        lo,hi = ymap(point['low']),ymap(point['high'])
        d.add(Line(xx,lo,xx,hi,strokeColor=color,strokeWidth=1.0))
        for cap in (lo,hi):
            d.add(Line(xx-2.2,cap,xx+2.2,cap,strokeColor=color,strokeWidth=1.0))
        _marker(d,shape,xx,yy,color)


def _values(rows, accuracies, policy):
    return tuple(dict(policy=policy,accuracy=x,mean=p['mean'],low=p['low'],high=p['high'])
                 for x,p in zip(accuracies,rows))


def make_accuracy_figure(source, width=234, height=174):
    """Original Figure 6.1: all eight initial-split means and 95% CIs."""
    accuracies = [.25,.5,.75,.8,.85,.9,.95,1.]
    points = [source.pick(source.SWEEP,'lava','best_fit',
                          f'{x:g}' if x < 1 else '1.0',split='initial')
              for x in accuracies]
    low = .2*floor(min(p['low'] for p in points)/.2)
    high = .2*ceil(max(p['high'] for p in points)/.2)
    d = Drawing(width,height)
    left,right,bottom,top = 42,8,34,14
    pw,ph = width-left-right,height-bottom-top
    xmap = lambda x: left+4+(pw-8)*(x-.25)/.75
    ymap = _axes(d,left,bottom,pw,ph,low,high,accuracies,xmap)
    _series(d,points,accuracies,xmap,ymap,NAVY,'circle')
    # Name inside the unused upper-left plot area, rather than a large legend.
    yy = bottom+ph-9
    d.add(Line(left+9,yy,left+24,yy,strokeColor=NAVY,strokeWidth=1.65))
    _marker(d,'circle',left+16.5,yy,NAVY,2.3)
    _text(d,left+29,yy-2.5,'LAVA',8,bold=True)
    _text(d,left+pw-3,ymap(0)+4,'Best-Fit = 0',7.5,'end',AXIS)
    d._data_points = _values(points,accuracies,'lava')
    return d


def make_fusion_figure(source, width=486, height=190):
    """Original Figure 9.1, preserving all three series and Oracle reference."""
    accuracies = [.25,.5,.75,.85,1.]
    names = [('vm_ca_bayes','VM-CA-Bayes',NAVY,'circle'),
             ('lava_bayes','LAVA-Bayes',ORANGE,'square'),
             ('lava','LAVA',SLATE,'diamond')]
    data = {p:[source.pick(source.IMP['test'],p,'best_fit',s) for s in source.ACC]
            for p,_,_,_ in names}
    oracle = source.pick(source.IMP['test'],'lava','best_fit','oracle')['mean']
    low = .2*floor(min(p['low'] for rows in data.values() for p in rows)/.2)
    high = .2*ceil(max([oracle]+[p['high'] for rows in data.values() for p in rows])/.2)
    d = Drawing(width,height)
    left,right,bottom,top = 43,10,34,29
    pw,ph = width-left-right,height-bottom-top
    xmap = lambda x: left+7+(pw-14)*(x-.25)/.75
    ymap = _axes(d,left,bottom,pw,ph,low,high,accuracies,xmap)
    oy = ymap(oracle)
    d.add(Line(left,oy,left+pw,oy,strokeColor=SLATE,strokeWidth=.85,strokeDashArray=[5,3]))
    _text(d,left+8,oy+4,f'Oracle LAVA {oracle:+.2f} pp',7.5,color=SLATE)
    for i,(policy,name,color,shape) in enumerate(names):
        # Visual dodge separates overlapping CI whiskers; tick values remain exact.
        _series(d,data[policy],accuracies,xmap,ymap,color,shape,(i-1)*2.3)
    legend_width = 254
    x0 = left+(pw-legend_width)/2
    for pos,(policy,name,color,shape) in zip([0,101,194],names):
        x=x0+pos; y=height-10
        d.add(Line(x,y,x+17,y,strokeColor=color,strokeWidth=1.65))
        _marker(d,shape,x+8.5,y,color,2.3)
        _text(d,x+22,y-2.7,name,8,bold=True)
    _text(d,left+pw-3,ymap(0)+4,'Best-Fit = 0',7.5,'end',AXIS)
    d._data_points = tuple(v for policy,_,_,_ in names
                          for v in _values(data[policy],accuracies,policy))
    d._oracle_mean = oracle
    return d


def make_confidence_figure(source, width=486, height=180):
    """Original Figure 7.1 with dark bars, exact profile class probabilities."""
    profiles = list(source.C['profiles'])
    data = [(name,source.profile_probs(name)) for name in profiles]
    d = Drawing(width,height)
    left,right,bottom,top=39,10,27,29
    pw,ph=width-left-right,height-bottom-top
    for k in range(6):
        value=k*.2;yy=bottom+ph*value
        d.add(Line(left,yy,left+pw,yy,strokeColor=GRID,strokeWidth=.45))
        _text(d,left-5,yy-2.5,f'{value:.1f}',7.5,'end')
    d.add(Line(left,bottom,left,bottom+ph,strokeColor=AXIS,strokeWidth=.7))
    d.add(Line(left,bottom,left+pw,bottom,strokeColor=AXIS,strokeWidth=.7))
    ygate=bottom+ph*.3
    d.add(Line(left,ygate,left+pw,ygate,strokeColor=THRESHOLD,strokeWidth=1.1,strokeDashArray=[4,2]))
    gw=pw/len(data);bw=min(31,gw*.24)
    values=[]
    for i,(name,(probabilities,mean,index)) in enumerate(data):
        vals=[max(probabilities),probabilities[index]]
        cx=left+gw*(i+.5)
        for j,value in enumerate(vals):
            xx=cx+(j-.5)*(bw+5)-bw/2
            d.add(Rect(xx,bottom,bw,ph*value,fillColor=[NAVY,ORANGE][j],strokeColor=None))
            _text(d,xx+bw/2,bottom+ph*value+4,f'{value:.3f}',7.5,'middle',bold=True)
        _text(d,cx,bottom-13,name.capitalize(),8,'middle')
        values.append(dict(profile=name,most_likely=max(probabilities),gate_confidence=probabilities[index]))
    labels=[('Most likely class',NAVY,0),('Gate confidence',ORANGE,144)]
    for text,color,offset in labels:
        xx=left+offset; yy=height-12
        d.add(Rect(xx,yy-2,8,7,fillColor=color,strokeColor=None))
        _text(d,xx+13,yy-1,text,8,bold=True)
    _text(d,left+pw,height-13,'Gate threshold = 0.3',7.5,'end',THRESHOLD)
    group=Group();group.add(String(0,0,'Probability',fontName=FONT,fontSize=8,fillColor=INK,textAnchor='middle'))
    group.transform=(0,1,-1,0,10,bottom+ph/2);d.add(group)
    d._data_points=tuple(values)
    return d
