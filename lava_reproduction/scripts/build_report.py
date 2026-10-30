#!/usr/bin/env python3
"""Build the course report PDF from recorded results (requires: pip install reportlab).
Every number is read from results/ or recomputed from configs; nothing is typed in by hand."""
import argparse,csv,json,math,statistics,sys
from pathlib import Path
from xml.sax.saxutils import escape
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from lava.model import BayesPredictor,Predictor,Request,mixture_remaining,trace
from lava.stats import paired_diffs,t_test
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor,white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT,TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether,CondPageBreak
from reportlab.graphics.shapes import Drawing,Line,Rect,Circle,String,PolyLine,Polygon

FONT_DIR=Path('/System/Library/Fonts/Supplemental')
for name,file in [('Arial','Arial.ttf'),('Arial-Bold','Arial Bold.ttf'),('Arial-Italic','Arial Italic.ttf'),('Arial-BoldItalic','Arial Bold Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT_DIR/file)))
for b,i,n in [(0,0,'Arial'),(1,0,'Arial-Bold'),(0,1,'Arial-Italic'),(1,1,'Arial-BoldItalic')]:addMapping('Arial',b,i,n)

REVISED='29 October 2026'
INK,NAVY,MUTED,RULE,HEAD_BG=HexColor('#1F2933'),HexColor('#2F5D8A'),HexColor('#6B7785'),HexColor('#D5DAE0'),HexColor('#E8EEF4')
POS,NEG,BOX=HexColor('#D5EBDC'),HexColor('#F4D3D1'),HexColor('#EEF3F8')
# Same series colours as the slides: LAVA slate, LAVA-Bayes orange, VM-CA-Bayes navy.
C_LAVA,C_LB,C_VB,C_ORANGE=HexColor('#6B7785'),HexColor('#D9822B'),HexColor('#2F5D8A'),HexColor('#D9822B')
GRID,AXIS=HexColor('#E1E0D9'),HexColor('#9C9A92')
S=dict(
    title=ParagraphStyle('title',fontName='Arial',fontSize=26,leading=31,textColor=HexColor('#233142'),spaceAfter=10),
    subtitle=ParagraphStyle('subtitle',fontName='Arial',fontSize=14.5,leading=19,textColor=NAVY,spaceAfter=14),
    meta=ParagraphStyle('meta',fontName='Arial',fontSize=8.5,leading=12,textColor=MUTED),
    h1=ParagraphStyle('h1',fontName='Arial',fontSize=17,leading=21,textColor=NAVY,spaceBefore=6,spaceAfter=9,keepWithNext=1),
    h2=ParagraphStyle('h2',fontName='Arial',fontSize=11.5,leading=15,textColor=NAVY,spaceBefore=9,spaceAfter=4,keepWithNext=1),
    body=ParagraphStyle('body',fontName='Arial',fontSize=9.5,leading=13.6,textColor=INK,spaceAfter=6,alignment=TA_LEFT),
    eq=ParagraphStyle('eq',fontName='Arial',fontSize=10,leading=16,textColor=INK,alignment=TA_CENTER,spaceBefore=2,spaceAfter=4),
    bullet=ParagraphStyle('bullet',fontName='Arial',fontSize=9.5,leading=13.4,textColor=INK,leftIndent=13,bulletIndent=3,spaceAfter=3),
    cell=ParagraphStyle('cell',fontName='Arial',fontSize=8.1,leading=10.4,textColor=INK),
    cellb=ParagraphStyle('cellb',fontName='Arial-Bold',fontSize=8.1,leading=10.4,textColor=HexColor('#233142')),
    cap=ParagraphStyle('cap',fontName='Arial',fontSize=8.4,leading=11.4,textColor=HexColor('#4A5562'),spaceBefore=3,spaceAfter=10),
    small=ParagraphStyle('small',fontName='Arial',fontSize=8,leading=11,textColor=MUTED,spaceAfter=3),
    ref=ParagraphStyle('ref',fontName='Arial',fontSize=8.6,leading=11.6,textColor=INK,leftIndent=16,firstLineIndent=-16,spaceAfter=3),
    code=ParagraphStyle('code',fontName='Courier',fontSize=8.3,leading=11,textColor=INK,leftIndent=6,spaceAfter=2))
TABLE_W=16.4  # cm, the text frame minus its padding

# ---------- data ----------
RES=root/'results';J=lambda p:json.loads((RES/p).read_text())
C=json.loads((root/'configs/report_scale.json').read_text());PROTO=json.loads((root/'configs/improvement_protocol.json').read_text())
SUITES=['test','legacy','tau','robust','robust_control','robust_load']
IMP={s:J(f'improvement/{s}/summary.json') for s in SUITES};MAN={s:J(f'improvement/{s}/manifest.json') for s in SUITES}
SWEEP,HELD,THR,DEV=J('sweep/summary.json'),J('heldout/summary.json'),J('validation/threshold_selection.json'),J('improvement/dev/summary.json')
GATE_BUCKET=J('improvement/gate_by_bucket.json')['rows']
HIST={(r['setting'],r['policy']):r for r in csv.DictReader((root/'reference/report_table1.csv').open())}
ACC=['0.25','0.5','0.75','0.85','1.0'];REG=ACC[:4]
NAME={'best_fit':'Best-Fit','la_binary':'LA-Binary','nilas':'NILAS','lava':'LAVA','vm_ca':'VM-CA','host_ca':'Host-CA',
 'nilas_bayes':'NILAS-Bayes','lava_bayes':'LAVA-Bayes','vm_ca_bayes':'VM-CA-Bayes','host_ca_bayes':'Host-CA-Bayes'}
def pick(rows,policy,baseline,setting,metric='empty_pct',**kw):
    return next(r for r in rows if r['policy']==policy and r['baseline']==baseline and r['setting']==setting and r.get('metric','empty_pct')==metric and all(r[k]==v for k,v in kw.items()))
def lab(s):return f'{float(s):.0%}' if s[0].isdigit() else s.capitalize()
def num(x,d=3):return f'{0:.{d}f}' if round(x,d)==0 else f'{x:+.{d}f}'.replace('-','−')
def ci(r,d=3):return f"{num(r['mean'],d)} [{num(r['low'],d)}, {num(r['high'],d)}]"
def ci2(r):return 'identical' if r['low']==r['high']==0 else f"{num(r['mean'])}<br/>[{num(r['low'])}, {num(r['high'])}]"
def pf(p):return '&lt;0.001' if p<1e-3 else (f'{p:.3f}' if p<.01 else f'{p:.2f}')
def rows_of(path):
    return [dict(r,seed=int(r['seed']),empty_pct=float(r['empty_pct']),accepted=int(r['accepted']),failures=int(r['failures']),
                 empty_pct_arrivals=float(r.get('empty_pct_arrivals') or 'nan')) for r in csv.DictReader((RES/path).open())]
TEST_RAW=rows_of('improvement/test/raw.csv');HELD_RAW=list(csv.DictReader((RES/'heldout/raw.csv').open()));TAU_RAW=list(csv.DictReader((RES/'improvement/tau/raw.csv').open()))
IDX={(r['seed'],r['setting'],r['policy']):r for r in TEST_RAW};TEST_SEEDS=sorted({r['seed'] for r in TEST_RAW})
def res(m,lo,hi,p):return dict(mean=m,low=lo,high=hi,p=p)
def posthoc(policy,baseline,setting):return res(*t_test(paired_diffs(TEST_RAW,policy,baseline,setting)))
def cross(policy,setting,baseline,bsetting):
    """Paired difference between two policies run under different predictor settings on the same seed (Best-Fit is identical across settings)."""
    return res(*t_test([IDX[(s,setting,policy)]['empty_pct']-IDX[(s,bsetting,baseline)]['empty_pct'] for s in TEST_SEEDS]))
def gate_rate(setting,policy):return 100*statistics.mean(int(r['high_gate'])/r['accepted'] for r in TEST_RAW if r['setting']==setting and r['policy']==policy)
def held_mean(policy,field):return statistics.mean(float(r[field]) for r in HELD_RAW if r['policy']==policy and r['setting']=='synthetic')
FAMILY={(r['setting'],r['baseline']):r for r in IMP['test'] if r['primary']};N_TEST=MAN['test']['n_seeds'];N_ROB=MAN['robust']['n_seeds']
ok=lambda r:r['mean']>0 and r['p_holm']<.05
HOLDS=sum(ok(r) for r in FAMILY.values());HOLDS_LAVA=sum(ok(FAMILY[(a,'lava')]) for a in REG);HOLDS_BF=sum(ok(FAMILY[(a,'best_fit')]) for a in REG)
IMP_RUNS=sum(MAN[s]['runs'] for s in SUITES);IMP_SECS=sum(MAN[s]['elapsed_s'] for s in SUITES)
# Cross-platform check of the improvement suites, from scripts/verify_reproduction.py (macOS re-run of Linux results).
VLOG=[l.split() for l in (RES/'verification_log.txt').read_text().splitlines()] if (RES/'verification_log.txt').exists() else []
VIMP=[dict(kv.split('=') for kv in ' '.join(l).replace('= ','=').split() if '=' in kv) for l in VLOG if l and l[0] in SUITES]
def profile_probs(name):
    p,a,b=C['profiles'][name];mean,w=mixture_remaining((p,a,b),0);edges=[0]+C['class_bounds']+[math.inf]
    Sv=lambda t:0. if t==math.inf else w*math.exp(-t/a)+(1-w)*math.exp(-t/b)
    probs=[Sv(lo)-Sv(hi) for lo,hi in zip(edges,edges[1:])];k=sum(1 for x in C['class_bounds'] if mean>=x)
    return probs,mean,k
def predict_pair(profile,setting,value,age=0,cfg=None):
    c=cfg or C;q=BayesPredictor(c,0,setting,[]);q.values={0:value};raw=Predictor(c,0,setting,[]);raw.values={0:value}
    req=Request(0,0,.125,.125,profile);return q.predict(req,age),raw.predict(req,age)
def scale_facts():
    """Workload scale on the test seeds: empty share, window vs horizon, offered and realized load, Host-CA tail recovery."""
    win,hor,ua,uf,lost_a,lost_f=[],[],[],[],0.,0.
    for s in TEST_SEEDS:
        recs=trace(C,s);t0=recs[0].request.arrival;ta=max(r.request.arrival for r in recs);te=max(r.request.arrival+r.duration for r in recs)
        win.append(ta-t0);hor.append(te-t0)
        ua.append(sum(r.request.cpu*max(0.,min(r.request.arrival+r.duration,ta)-r.request.arrival) for r in recs)/(C['hosts']*(ta-t0)))
        uf.append(sum(r.request.cpu*r.duration for r in recs)/(C['hosts']*(te-t0)))
        bf,hc=IDX[(s,'synthetic','best_fit')],IDX[(s,'synthetic','host_ca')]
        lost_a+=(bf['empty_pct_arrivals']-hc['empty_pct_arrivals'])/100*C['hosts']*(ta-t0);lost_f+=(bf['empty_pct']-hc['empty_pct'])/100*C['hosts']*float(bf['horizon'])
    bfe=[IDX[(s,'synthetic','best_fit')]['empty_pct'] for s in TEST_SEEDS];H=statistics.mean(hor)
    pw=C['profile_weights'];ET=sum(w*(p*a+(1-p)*b) for w,(p,a,b) in zip(pw,C['profiles'].values()));Ecpu=sum(w*sh[0] for w,sh in zip(C['shape_weights'],C['shapes']))
    busy=C['hosts']*H*(1-statistics.mean(bfe)/100)
    return dict(bf_mean=statistics.mean(bfe),bf_min=min(bfe),bf_max=max(bfe),window=statistics.mean(win),horizon=H,tail=statistics.mean(1-w/h for w,h in zip(win,hor)),
                offered=C['arrival_rate']*ET*Ecpu/C['hosts'],ET=ET,Ecpu=Ecpu,util_arr=statistics.mean(ua),util_full=statistics.mean(uf),
                hh_per_pp=C['hosts']*H/100,busy=busy,recovery=1-lost_f/lost_a)

# ---------- figures ----------
def axis_frame(d,L,B,pw,ph,lo,hi,step,signed=True):
    v=lo
    while v<=hi+1e-9:
        y=B+ph*(v-lo)/(hi-lo);d.add(Line(L,y,L+pw,y,strokeColor=AXIS if abs(v)<1e-9 else GRID,strokeWidth=.8 if abs(v)<1e-9 else .5))
        d.add(String(L-5,y-2.6,(num(v,1) if signed else f'{v:.1f}') if abs(v)>1e-9 else '0.0',fontName='Arial',fontSize=7,fillColor=MUTED,textAnchor='end'));v+=step
def marker(d,shape,x,y,color,r=2.6):
    if shape=='circle':d.add(Circle(x,y,r,fillColor=color,strokeColor=white,strokeWidth=.9))
    elif shape=='square':d.add(Rect(x-r,y-r,2*r,2*r,fillColor=color,strokeColor=white,strokeWidth=.9))
    else:d.add(Polygon([x,y+r*1.25,x+r*1.25,y,x,y-r*1.25,x-r*1.25,y],fillColor=color,strokeColor=white,strokeWidth=.9))
def line_figure(series,xs,width=455,height=215,refs=()):
    """Accuracy on a true numeric axis; series are offset slightly so whiskers do not overlap."""
    d=Drawing(width,height);L,R,T,B=40,100,26,30;pw,ph=width-L-R,height-T-B
    vals=[v for _,_,_,pts in series for m in pts for v in (m['low'],m['high'])]+[0]+[v for _,v in refs]
    step=.2;lo=step*math.floor(min(vals)/step);hi=step*math.ceil(max(vals)/step)
    x0,x1=min(xs)-.05,max(xs)+.03;X=lambda x:L+pw*(x-x0)/(x1-x0);Y=lambda v:B+ph*(v-lo)/(hi-lo)
    axis_frame(d,L,B,pw,ph,lo,hi,step)
    for x in xs:
        d.add(Line(X(x),B,X(x),B-2.5,strokeColor=AXIS,strokeWidth=.6));d.add(String(X(x),B-11,f'{x:.0%}',fontName='Arial',fontSize=6.8,fillColor=MUTED,textAnchor='middle'))
    d.add(String(L+pw/2,4,'Controlled lifetime-prediction accuracy (to scale)',fontName='Arial',fontSize=7.4,fillColor=MUTED,textAnchor='middle'))
    d.add(String(L+pw+6,Y(0)-2.6,'Best-Fit',fontName='Arial',fontSize=7,fillColor=MUTED))
    for name,v in refs:
        d.add(Line(L,Y(v),L+pw,Y(v),strokeColor=AXIS,strokeWidth=.6));d.add(String(L+pw+6,Y(v)-2.6,f'{name} {num(v,2)}',fontName='Arial',fontSize=7,fillColor=MUTED))
    k=len(series)
    for i,(name,color,shape,pts) in enumerate(series):
        off=(i-(k-1)/2)*.009;P=[(X(x+off),Y(m['mean'])) for x,m in zip(xs,pts)]
        d.add(PolyLine([c for p in P for c in p],strokeColor=color,strokeWidth=1.3,strokeLineJoin=1,strokeLineCap=1))
        for (px,_),m in zip(P,pts):
            d.add(Line(px,Y(m['low']),px,Y(m['high']),strokeColor=color,strokeWidth=.9))
            for v in (m['low'],m['high']):d.add(Line(px-1.8,Y(v),px+1.8,Y(v),strokeColor=color,strokeWidth=.9))
        for px,py in P:marker(d,shape,px,py,color)
        lx=L+i*120;marker(d,shape,lx+4,height-10,color);d.add(String(lx+11,height-12.6,name,fontName='Arial',fontSize=7.4,fillColor=INK))
    return d
def bar_figure(groups,series,width=455,height=190,ref=None):
    d=Drawing(width,height);L,R,T,B=40,20,26,26;pw,ph=width-L-R,height-T-B;lo,hi,step=0.,1.,.2
    axis_frame(d,L,B,pw,ph,lo,hi,step,signed=False);gw=pw/len(groups);bw=min(26,gw/(len(series)+1.6))
    if ref is not None:  # reference line behind the bars
        y=B+ph*ref[1];d.add(Line(L,y,L+pw,y,strokeColor=HexColor('#B64A4A'),strokeWidth=.8,strokeDashArray=[3,2]));d.add(String(L+pw-2,y+3,ref[0],fontName='Arial',fontSize=7,fillColor=HexColor('#B64A4A'),textAnchor='end'))
    for gi,(gname,vals) in enumerate(groups):
        cx=L+gw*(gi+.5);d.add(String(cx,B-12,gname,fontName='Arial',fontSize=7.4,fillColor=MUTED,textAnchor='middle'))
        for si,v in enumerate(vals):
            x=cx+(si-(len(series)-1)/2)*(bw+3)-bw/2;h=ph*v
            d.add(Rect(x,B,bw,h,fillColor=series[si][1],strokeColor=None));d.add(String(x+bw/2,B+h+3,f'{v:.3f}',fontName='Arial',fontSize=6.8,fillColor=INK,textAnchor='middle'))
    for si,(name,color) in enumerate(series):
        lx=L+si*190;d.add(Rect(lx,height-14,8,8,fillColor=color,strokeColor=None));d.add(String(lx+12,height-12.6,name,fontName='Arial',fontSize=7.4,fillColor=INK))
    return d

# ---------- helpers ----------
def P(t,s='body'):return Paragraph(t,S[s])
def B(items):return [Paragraph(t,S['bullet'],bulletText='•') for t in items]
def cell(x,bold=False):return x if not isinstance(x,str) else Paragraph(x,S['cellb' if bold else 'cell'])
def table(rows,widths,shade=None,header=True):
    k=TABLE_W/sum(widths);data=[[cell(x,header and i==0) for x in r] for i,r in enumerate(rows)]
    st=[('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3.2),('BOTTOMPADDING',(0,0),(-1,-1),3.2),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('LINEBELOW',(0,1),(-1,-1),.45,RULE)]
    if header:st+=[('BACKGROUND',(0,0),(-1,0),HEAD_BG),('LINEBELOW',(0,0),(-1,0),.9,NAVY)]
    for (c,r),color in (shade or {}).items():st.append(('BACKGROUND',(c,r),(c,r),color))
    t=Table(data,colWidths=[w*k*cm for w in widths],repeatRows=1 if header else 0,hAlign='LEFT');t.setStyle(TableStyle(st));return t
def sig_shade(r):return POS if r['low']>0 else NEG if r['high']<0 else None
def shade_rows(rows_of_results,first_row=1):
    return {(c,i):sig_shade(r) for i,rs in enumerate(rows_of_results,first_row) for c,r in enumerate(rs,1) if sig_shade(r)}
def boxed(flow,width=TABLE_W):
    t=Table([[flow]],colWidths=[width*cm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BOX),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return t
class OutlinedDoc(SimpleDocTemplate):
    """Adds PDF bookmarks for section (h1) and subsection (h2) headings."""
    def afterFlowable(self,f):
        if isinstance(f,Paragraph) and f.style.name in ('h1','h2'):
            if f.style.name=='h1':self.seen_h1=True
            level=1 if f.style.name=='h2' and getattr(self,'seen_h1',False) else 0
            key=f'h{id(f)}';self.canv.bookmarkPage(key);self.canv.addOutlineEntry(f.getPlainText(),key,level=level,closed=True)
def figure(drawing,caption):return KeepTogether([drawing,P(caption,'cap')])
def section(title):return [CondPageBreak(9*cm),P(title,'h1')]

# ---------- content ----------
def build(out):
    st=[];F=scale_facts()
    fam=FAMILY;t_bf={p:{s:pick(IMP['test'],p,'best_fit',s) for s in ACC+['synthetic','oracle']} for p in NAME if p!='best_fit'}
    host_bf,host_vm,vm_bf=pick(IMP['test'],'host_ca','best_fit','synthetic'),pick(IMP['test'],'host_ca','vm_ca','synthetic'),pick(IMP['test'],'vm_ca','best_fit','synthetic')
    win_host=pick(IMP['test'],'host_ca','best_fit','synthetic','empty_pct_arrivals');hist=HIST[('synthetic','host_ca')]
    gate=[posthoc('vm_ca_bayes','lava_bayes',a) for a in ACC];noisy=[pick(IMP['test'],'lava_bayes','lava',a) for a in REG];prior=[cross('lava_bayes',a,'lava','synthetic') for a in REG]
    gb={(r['setting'],r['confidence']):r for r in GATE_BUCKET}
    rob=lambda v,a,b='lava':pick(IMP['robust'],'vm_ca_bayes',b,a,variant=v);ctrl=lambda a,b='lava':pick(IMP['robust_control'],'vm_ca_bayes',b,a);load=lambda a,b='lava',p='vm_ca_bayes':pick(IMP['robust_load'],p,b,a)
    x05=rob('prior_means_x0.5','0.85');x05bf=rob('prior_means_x0.5','0.85','best_fit')
    probs={n:profile_probs(n) for n in C['profiles']}
    (ex1,ex1raw),(ex2,ex2raw)=predict_pair('interactive','0.25',300.),predict_pair('service','0.5',2.)
    (cap300,cap300raw),(cap400,cap400raw)=predict_pair('service','1.0',float(C['cap_hours']),300.),predict_pair('service','1.0',float(C['cap_hours']),400.)
    half=dict(C,prior_profiles={k:[p,a*.5,b*.5] for k,(p,a,b) in C['profiles'].items()})
    cap_true,cap_half=predict_pair('service','0.85',float(C['cap_hours']))[0][0],predict_pair('service','0.85',float(C['cap_hours']),cfg=half)[0][0]
    devrow=lambda p,a:next(r for r in DEV if r['policy']==p and r['baseline']=='lava' and r['setting']==a);dev=lambda p,a:devrow(p,a)['mean']
    maps=[devrow(f'{v}_map@{t}','synthetic') for v in ('vm_ca','host_ca') for t in (0.4,0.5,0.9)];ee=devrow('lava_ee','synthetic')
    reg_time=PROTO['registered_at'];reg=f"{reg_time[11:16]} (UTC+8) on {int(reg_time[8:10])} October {reg_time[:4]}"
    lb_bf=[t_bf['la_binary'][s]['mean'] for s in ACC+['synthetic','oracle']]
    arr_vb=[pick(IMP['test'],'vm_ca_bayes','lava',a,'empty_pct_arrivals') for a in ('0.25','0.5','0.85')]
    load_bf=statistics.mean(float(r['empty_pct']) for r in csv.DictReader((RES/'improvement/robust_load/raw.csv').open()) if r['policy']=='best_fit')
    hh=lambda pp:pp*F['hh_per_pp']
    # ---- title page
    st+=[Spacer(1,1.0*cm),P('Revisiting Lifetime-Aware VM Allocation','title'),P('Reconstruction, Diagnosis and Prior-Fused Lifetime Prediction','subtitle'),
         P(f'CE7490 Course Project Report · Revised {REVISED}','meta'),Spacer(1,.5*cm),P('Abstract','h2'),
         P(f"Lifetime-aware VM allocation uses predicted departures to reduce fragmentation and increase the fraction of empty hosts. This project reconstructs an event-driven CPU and memory simulator of LAVA&nbsp;[1] from a surviving course report after the original code and traces became unavailable, and studies how lifetime-prediction quality and uncertainty handling change the scheduling benefit. With 180 hosts and 2,500 VMs per paired synthetic trace, LAVA's gain over Best-Fit grows with controlled prediction accuracy, but at 25% accuracy LAVA is significantly worse than Best-Fit ({ci(t_bf['lava']['0.25'])} percentage points, pp, on {N_TEST} fresh seeds)."),
         P(f"The earlier report proposed Host-Level Confidence-Aware LAVA as the remedy. It does not outperform Best-Fit on the report's held-out seeds and is significantly worse on {N_TEST} fresh seeds ({ci(host_bf)} pp). We present this as a diagnostic negative result. Three measured properties contribute: the default predictor's class confidence is inverted relative to predictability, the confidence gate passes essentially every request under controlled noise, and isolating hosts by mode costs about one percentage point of empty hosts during the arrival period."),
         P(f"We then propose <b>prior-fused lifetime prediction</b>: a Bayesian posterior that combines each noisy prediction with the profile-level lifetime distribution, treats the 14-day cap as censoring and conditions on uptime, while every scheduling rule stays unchanged. In a pre-registered, Holm-corrected evaluation on {N_TEST} fresh seeds, confidence-aware LAVA with the fused predictor beats LAVA in {HOLDS_LAVA} of 4 registered tests ({num(fam[('0.25','lava')]['mean'])}, {num(fam[('0.5','lava')]['mean'])} and {num(fam[('0.85','lava')]['mean'])} pp at 25%, 50% and 85% accuracy) and Best-Fit in {HOLDS_BF} of 4; {HOLDS} of 8 hypotheses hold. A post-hoc decomposition suggests that most of the gain comes from the fused estimate rather than the gate. Under milder errors, misspecified error spreads, doubled prior means and doubled load, the gain over LAVA shrinks or grows and is not always significant, but it is never significantly negative except with halved prior means at 85% accuracy."),
         Spacer(1,.1*cm),boxed([P('<b>Principal findings</b>','body')]+B([
            f"<b>RQ1 – prediction quality is first-order.</b> On fresh seeds LAVA moves from {num(t_bf['lava']['0.25']['mean'])} pp at 25% accuracy to {num(t_bf['lava']['1.0']['mean'])} pp at 100%; the Oracle reference is {num(t_bf['lava']['oracle']['mean'])} pp.",
            "<b>RQ2 – confidence routing is a diagnostic negative result.</b> Neither VM-level nor host-level routing beats Best-Fit under the default predictor; inverted confidence, a blind gate and the packing cost of isolation contribute.",
            f"<b>RQ3 – prior fusion fixes the low-accuracy failure.</b> {HOLDS_LAVA} of 4 registered tests against LAVA hold. Uncertainty helped inside the lifetime estimate, not as a policy switch. A prior that underestimates lifetimes is the main risk."])),
         Spacer(1,.3*cm),P('Keywords: VM scheduling, lifetime prediction, Bayesian fusion, censoring, uncertainty, paired experiments, pre-registration, reconstruction','small'),PageBreak()]
    # ---- 1 Introduction
    st+=[P('1  Introduction and research scope','h1'),
         P('A VM scheduler must place requests that consume several resources at once. A feasible placement can still leave CPU and memory in incompatible proportions and strand capacity. Departure times add a temporal dimension: VMs that fit equally well at arrival may keep a host occupied for very different periods. Empty hosts matter for maintenance, large requests and energy management, although this simulator measures empty capacity rather than those outcomes directly.'),
         P('LAVA&nbsp;[1] combines learned lifetime distributions, re-prediction with uptime and host lifecycle adaptation. The production system relies on private traces and integration with Borg&nbsp;[2]. This project studies the public scheduling ideas in a transparent synthetic environment, where policies can be compared on identical workloads and identical prediction realizations.'),
         P('Related work','h2'),
         P('Resource Central&nbsp;[3] showed that VM lifetimes in a large cloud are predictable from history and can inform resource management. Barbalho et al.&nbsp;[4] use lifetime predictions to align departures when packing VMs; our LA-Binary baseline follows that idea as evaluated in&nbsp;[1]. Protean&nbsp;[5] describes the production allocation service into which such policies plug. LAVA&nbsp;[1] adds lifetime distributions, re-prediction and host lifecycle states. Our prior-fused predictor applies standard Bayesian updating and the treatment of right-censored observations from survival analysis&nbsp;[6] to the noisy predictions that LAVA consumes.'),
         P('Research questions','h2'),
         P('<b>RQ1.</b> How does controlled lifetime-prediction accuracy change LAVA\'s improvement over a resource-only Best-Fit baseline?'),
         P('<b>RQ2.</b> Does routing low-confidence requests to Best-Fit, per VM or per host, make LAVA robust to unreliable predictions?'),
         P('<b>RQ3.</b> Can the lifetime estimate itself be made robust by fusing each noisy prediction with the profile-level lifetime distribution, without changing the scheduler?'),
         P('What changed in this revision','h2'),
         P('The surviving report&nbsp;[7] claimed that Host-Level CA significantly improved the default synthetic regime. The previous revision replaced those values with reconstructed measurements and found no such gain. This revision makes three changes. It turns that outcome into a <b>diagnostic negative result</b> (Section 7). It introduces <b>prior-fused prediction</b> as the new main contribution (Section 8). It evaluates the method under a <b>pre-registered protocol</b> on previously unused seeds, with robustness variants (Sections 9 and 10).'),
         P('After the change, the six original policies reproduce all 1,644 stored runs field by field on macOS (Section 5). The only historical value from the surviving report appears, labeled, in Section 7.1.'),
         P('Contributions','h2')]+B([
         'A runnable reconstruction of Best-Fit, LA-Binary, NILAS, LAVA and two confidence-aware variants, with paired statistics, resource assertions and raw per-seed results.',
         'A diagnosis of why confidence-aware routing does not help in this setting, supported by profile-level confidence analysis, gate pass rates and a time-window decomposition.',
         'Prior-fused lifetime prediction: a drop-in Bayesian predictor, with censoring at the prediction cap and survival-consistent re-prediction, that leaves every scheduling rule unchanged.',
         f'A pre-registered, Holm-corrected evaluation on {N_TEST} fresh seeds, plus robustness to error severity, model misspecification and load ({IMP_RUNS:,} additional simulations).'])
    # ---- 2 Algorithms
    alg=[['Policy','Placement signal','Prediction use'],
         ['Best-Fit','Minimize squared residual CPU plus squared residual memory','None for placement'],
         ['LA-Binary','Prefer non-empty hosts with the same initial short/long label, then other non-empty hosts, then empty hosts; Best-Fit within each group','One-shot label at 2 hours'],
         ['NILAS','Quantized extension of the predicted latest host exit, then Best-Fit','Re-predicts live residents'],
         ['LAVA','Lifecycle state and lifetime class, then NILAS and Best-Fit','Re-predicted remaining lifetime'],
         ['VM-Level CA (VM-CA)','LAVA or Best-Fit, chosen per arrival','Class confidence ≥ threshold τ'],
         ['Host-Level CA (Host-CA)','Same gate; eligible hosts restricted to the same mode or empty','Same gate as VM-CA'],
         ['*-Bayes variants (new)','Identical rules to NILAS, LAVA, VM-CA or Host-CA','Prior-fused prediction (Section 8)']]
    st+=section('2  Scheduling algorithms')+[table(alg,[3.4,8.4,5.2]),P('Table 2.1. Policies compared. “*-Bayes” denotes the four variants that only swap in the prior-fused predictor.','cap'),
         P('Host lifecycle and placement order','h2'),
         P('LAVA classes use remaining-lifetime boundaries at 1, 10 and 100 hours, supplemented from the public paper&nbsp;[1]. A newly occupied host is <i>open</i>. When CPU or memory reaches 90%, it becomes <i>recycling</i> and records its current VMs as the residual cohort. Placement prefers recycling hosts in a higher class than the arriving VM (closest class first), then open hosts in the same class, then other non-empty hosts and finally empty hosts. When the residual cohort exits, a non-empty recycling host drops one class; deadline expiry raises the class and refreshes the cohort.'),
         P('Confidence-aware routing','h2'),
         P('VM-CA routes each arrival by its confidence. Because hosts are shared, one host can receive both LAVA and Best-Fit decisions; we call this <i>mode mixing</i>. Host-CA assigns a mode at a host\'s first placement and keeps it until the host empties. It considers same-mode and empty hosts first and allows a cross-mode placement only when no such host can admit the request (capacity fallback). No fallback occurred in any recorded suite.'),
         P('Prior-fused variants','h2'),
         P('The four *-Bayes policies run exactly the scheduling code of their base policy. Only the predictor object differs, so any difference in outcome is attributable to the lifetime estimate and its confidence. Under the default predictor and the Oracle there is no noisy value to fuse, and the variants reproduce their base policies bit for bit.')]
    # ---- 3 Workload
    params=[['Parameter','Value','Status'],['Hosts / requests','180 / 2,500 per trace','Recovered'],['Mean arrival rate','8 requests/hour','Recovered'],
            ['Interarrival distribution','Independent exponential','Inferred'],['Profile probabilities','Interactive 0.45, batch 0.35, service 0.20','Inferred'],
            ['Prediction cap','336 hours (14 days)','Recovered'],['Recycling threshold','0.90 CPU or memory','Recovered'],['LAVA class boundaries','1, 10, 100 hours','Public paper supplement'],
            ['Best-Fit score','Residual CPU squared + residual memory squared','Inferred']]
    mix=[['Profile','p (short component)','a (hours)','b (hours)']]+[[n.capitalize(),f'{p:g}',f'{a:g}',f'{b:g}'] for n,(p,a,b) in C['profiles'].items()]
    st+=section('3  Workload and parameter provenance')+[
         P('Each host has normalized CPU and memory capacity of one. Every trace contains 2,500 VM requests at a documented mean arrival rate of eight per simulated hour. The reconstruction uses independent exponential interarrival times; the surviving report gives the mean rate but not the arrival process, so Poisson arrivals are an explicit assumption (Table 3.1).'),
         table(params,[4.6,7.2,5.2]),P('Table 3.1. Simulator parameters and their provenance.','cap'),
         P('Two-exponential lifetime mixtures','h2'),
         P('For each profile, <i>p</i> is the probability of the short component and <i>a</i>, <i>b</i> are the component means (Table 3.2). The profile names and the two-component family are recovered; all numeric values are declared synthetic defaults.'),
         table(mix,[4.0,4.4,4.3,4.3]),P('Table 3.2. Lifetime mixture of each VM profile.','cap'),
         P('CPU and memory shapes','h2'),
         P('The inferred (CPU, memory) shapes are (0.125, 0.125), (0.25, 0.125), (0.125, 0.25), (0.5, 0.25) and (0.25, 0.5) with probabilities 0.35, 0.20, 0.20, 0.125 and 0.125. Shape, profile and component are sampled independently. Lifetimes are not truncated; only predictions receive the 14-day cap.'),
         P('These values were declared once and never fitted to the earlier report or to any result. A different plausible mixture could change relative policy performance; Section 10 varies predictor-side assumptions and the load, but not the generating mixture itself.')]
    # ---- 4 Prediction
    st+=section('4  Lifetime prediction and confidence')+[P('Conditional remaining lifetime','h2'),
         P('Let <i>T</i> follow a two-exponential mixture with short-component probability <i>p</i> and means <i>a</i> and <i>b</i>. At uptime <i>u</i> the short-component weight and the expected remaining lifetime are'),
         P('<i>w(u)</i> = <i>p</i>·e<super>−u/a</super> / [ <i>p</i>·e<super>−u/a</super> + (1−<i>p</i>)·e<super>−u/b</super> ],','eq'),
         P('E[<i>T</i> − <i>u</i> | <i>T</i> &gt; <i>u</i>] = <i>w(u)</i>·<i>a</i> + (1 − <i>w(u)</i>)·<i>b</i>.','eq'),
         P('The weights are evaluated in log space to avoid underflow. The <i>default predictor</i> returns this conditional mean, capped at 336 hours. Its confidence is the conditional probability that the remaining lifetime falls in the LAVA class that contains the mean.'),
         P('Controlled prediction accuracy','h2'),
         P('Following the controlled-noise protocol of&nbsp;[1, Appendix G.1], the harness assigns each VM to the <i>correct bucket</i> with probability equal to the requested accuracy and to the <i>incorrect bucket</i> otherwise. It applies Gaussian noise in log10 space with σ = 0.001 (correct) or σ = 3 (incorrect) to the true total lifetime and caps the result at 14 days. All policies with the same seed and setting see the same noisy values; the bucket label never reaches the scheduler.'),
         P('The original controlled predictor freezes the noisy value. Before that value is reached, remaining lifetime is the value minus uptime; afterwards it switches to min(336, max(0.1, uptime)) hours. Its confidence is a posterior class mass under a log-uniform prior and the global error model (accuracy and the two σ values).'),
         P('Strict Oracle','h2'),P('Oracle predictions use the actual remaining lifetime with confidence one. This full-information reference measures how much the same scheduling rules can gain with perfect lifetimes. It is not an upper bound for every policy (Section 11).'),
         P('Three properties that matter later','h2')]+B([
         'The default confidence is the probability of the class that contains the mixture <i>mean</i>. For bimodal mixtures the mean often lies in a low-probability class (Section 7.3).',
         'The controlled predictor trusts every noisy value, including errors that span several orders of magnitude (Section 7.4).',
         'When a VM outlives its noisy value, its predicted remaining lifetime jumps to min(336, max(0.1, uptime)), and a value at the 336-hour cap is treated as an exact observation rather than as censored.'])+[
         P('Section 7 shows how the first two properties affect confidence-aware routing. Section 8 addresses the second and third directly.')]
    # ---- 5 Protocol
    suites=[['Suite','Seeds','Settings and policies','Runs'],['Smoke','0–1','3 predictor settings, 6 policies','36'],['Initial sweep','0–19','8 accuracies + default + Oracle; Best-Fit, LAVA, VM-CA','600'],
            ['Validation','200–205','Default predictor; 7 thresholds; 4 policies','168'],['Held-out','20–39','5 accuracies + default + Oracle; 6 policies','840'],
            ['Improvement test','1000–1099','5 accuracies + default + Oracle; 10 policies (pre-registered)',f"{MAN['test']['runs']:,}"],
            ['Legacy rerun','20–39','Same 7 settings; 10 policies',f"{MAN['legacy']['runs']:,}"],['Threshold sensitivity','200–219','4 accuracies; 7 thresholds; 4 policies',f"{MAN['tau']['runs']:,}"],
            ['Robustness','2000–2049','4 accuracies; 7 predictor or load variants; 7 policies',f"{MAN['robust']['runs']:,}"],
            ['Robustness control*','2000–2049','4 accuracies; unmodified protocol; 7 policies',f"{MAN['robust_control']['runs']:,}"],
            ['Load ×2*','2000–2049','4 accuracies; arrival rate 16/h, 5,000 VMs; 7 policies',f"{MAN['robust_load']['runs']:,}"]]
    st+=section('5  Experimental protocol and verification')+[table(suites,[3.6,2.2,9.0,2.2]),
         P('Table 5.1. Experiment suites. Controlled sweep accuracies are 25%, 50%, 75%, 80%, 85%, 90%, 95% and 100%; later suites use 25%, 50%, 75%, 85% and 100%. *Added after review; descriptive.','cap'),
         P('Metrics','h2'),
         P('The primary metric is 100 times the time integral of the number of empty hosts, divided by the number of hosts and the interval from the first arrival to the final exit. It includes the full drain tail. Results are paired differences in percentage points (pp) relative to the same-seed baseline. A secondary diagnostic integrates only the arrival window (first to last arrival) to separate packing during the busy period from consolidation during the drain tail.'),
         P(f"Scale matters for reading the results. Best-Fit leaves {F['bf_mean']:.1f}% of host-time empty on average ({F['bf_min']:.1f}–{F['bf_max']:.1f}% across test seeds), because the offered load is low and the drain tail is long. The arrival window lasts about {F['window']:.0f} hours of a {F['horizon']:.0f}-hour horizon, so about {F['tail']:.0%} of the primary metric is the drain tail. With 180 hosts, 1 pp equals 1.8 hosts on average over the horizon. The headline gain of {num(fam[('0.25','lava')]['mean'])} pp is therefore about {fam[('0.25','lava')]['mean']*1.8:.2f} of a host, or {hh(fam[('0.25','lava')]['mean']):.0f} empty host-hours per trace ({100*hh(fam[('0.25','lava')]['mean'])/F['busy']:.1f}% of Best-Fit's busy host-hours)."),
         P(f"The offered load is about {F['offered']:.0%} at steady state (8 VMs per hour × {F['ET']:.2f} h mean lifetime × {F['Ecpu']:.4f} CPU, over 180 hosts). Because the 2,500 arrivals end before steady state is fully reached, realized CPU utilization is about {F['util_arr']:.0%} during the arrival window and {F['util_full']:.0%} over the full horizon."),
         P('Inference','h2'),
         P('For each seed the analysis subtracts the baseline metric from the alternative and forms a two-sided Student-t 95% interval with n−1 degrees of freedom. It refuses comparisons with missing pairs, failed admissions or unequal accepted counts. Intervals in all tables are unadjusted. Only the eight registered tests of Section 9 also carry Holm–Bonferroni adjusted p-values&nbsp;[8]; all other comparisons are descriptive.'),
         P('Pre-registration','h2'),
         P(f'Development of the new method used only seeds 0–19. The hypotheses, test seeds, frozen threshold, correction and decision rule were written to <i>configs/improvement_protocol.json</i>, with SHA256 hashes of all simulator sources, at {reg}. This was before any prior-fused run on the legacy, threshold, test or robustness seeds. The registration is a local file with a self-reported timestamp, not an external registry. No simulator source changed afterwards, and all six improvement-suite manifests record the registered hashes. The development exploration script was packaged after registration; it reproduces exactly the development numbers recorded in the registration file. The two suites marked * in Table 5.1 were added after review.'),
         P('Verification','h2'),
         P(f'All {1644+IMP_RUNS:,} runs accept every request with zero scheduling failures and no oversubscription. Twenty-nine unit tests pass, covering event ordering, time integration, mixture conditioning, resource bounds, host isolation, capacity fallback, Oracle equivalence, the no-truth-access boundary of both predictors, censoring, and the paired t-test and Holm adjustment. Re-simulating the 1,644 stored reconstruction runs reproduces every field bit for bit on macOS; on Linux all integer decision counts match and floating-point values differ only in the last digits (relative difference ≤ 3.3×10<super>−16</super>). '+(f"In the other direction, an evenly spaced sample of {sum(int(v['runs']) for v in VIMP)} improvement runs computed on the Linux server, re-simulated on macOS, matches every integer field, with floating-point differences of at most {max(float(v['difference']) for v in VIMP)/1e-16:.1f}×10<super>−16</super>. " if VIMP and all(v['tolerance']=='0' for v in VIMP) and 'macOS' in ' '.join(VLOG[1]) else '')+'<i>scripts/verify_reproduction.py</i> performs these checks and writes <i>results/verification_log.txt</i>.'),
         P('Compute','h2'),
         P(f'The simulator is pure-Python CPU code and needs no GPU. A report-scale run takes about 0.1–0.3 s for the original policies and 0.7 s with the fused predictor on one Apple M5 core, and about 0.9 s on average on one core of the server used below. The {IMP_RUNS:,} improvement runs used 64 low-priority processes on a 192-thread Xeon server and finished in about {IMP_SECS/60:.0f} minutes of wall time; the server\'s H20 GPUs were not used.')]
    # ---- 6 RQ1
    xs=[.25,.5,.75,.8,.85,.9,.95,1.];pts=[pick(SWEEP,'lava','best_fit',f'{x:g}' if x<1 else '1.0',split='initial') for x in xs]
    sweep_rows=[['Accuracy / predictor','LAVA − Best-Fit, mean [95% CI], pp']]+[[f'{x:.0%}',ci(r)] for x,r in zip(xs,pts)]+[['Default predictor',ci(pick(SWEEP,'lava','best_fit','synthetic',split='initial'))],['Oracle',ci(pick(SWEEP,'lava','best_fit','oracle',split='initial'))]]
    sig=[f'{x:.0%}' for x,r in zip(xs,pts) if r['low']>0]
    st+=section('6  RQ1: Prediction accuracy sensitivity')+[
         P('Figure 6.1 and Table 6.1 show LAVA minus Best-Fit across controlled accuracy on the initial split.'),
         figure(line_figure([('LAVA',C_LAVA,'circle',pts)],xs),'Figure 6.1. LAVA minus Best-Fit across controlled accuracy, initial split (seeds 0–19). Percentage points; paired means with 95% intervals, n = 20 per point; the accuracy axis is to scale.'),
         table(sweep_rows,[5.0,8.0]),P('Table 6.1. Values plotted in Figure 6.1.','cap'),
         P(f'The first tested level with a positive paired interval is {sig[0]}, and the estimated gain keeps increasing through the high-accuracy regime. This answers RQ1 within the reconstructed workload. The significance point is a property of the tested grid, the workload and the implementation, not a universal threshold; the scan is descriptive and not corrected for multiplicity.'),
         P(f"The {N_TEST} fresh test seeds of Section 9 confirm the shape with tighter intervals: LAVA minus Best-Fit is {ci(t_bf['lava']['0.25'])} pp at 25%, {ci(t_bf['lava']['0.5'])} at 50%, {ci(t_bf['lava']['0.75'])} at 75%, {ci(t_bf['lava']['0.85'])} at 85% and {ci(t_bf['lava']['1.0'])} at 100%; the Oracle reaches {ci(t_bf['lava']['oracle'])}. <b>At 25% accuracy LAVA is significantly worse than Best-Fit</b>: trusting unreliable predictions harms packing. This is the regime that RQ2 and RQ3 target."),
         P(f"Under the default predictor, LAVA's small gain on the initial split ({ci(pick(SWEEP,'lava','best_fit','synthetic',split='initial'))} pp) does not replicate on the held-out seeds ({ci(pick(HELD,'lava','best_fit','synthetic',split='heldout'))}) or on the fresh seeds ({ci(t_bf['lava']['synthetic'])}).")]
    # ---- 7 RQ2
    held=[['Setting','LAVA','VM-CA','Host-CA']]+[[lab(s),*[ci(pick(HELD,p,'best_fit',s,split='heldout')) for p in ['lava','vm_ca','host_ca']]] for s in ACC+['synthetic','oracle']]
    comp=[['Default predictor, Host-CA minus …','Held-out seeds 20–39 (n = 20)',f'Fresh seeds 1000–1099 (n = {N_TEST})'],
          ['Best-Fit',ci(pick(HELD,'host_ca','best_fit','synthetic',split='heldout')),ci(host_bf)],['LAVA',ci(pick(HELD,'host_ca','lava','synthetic',split='heldout')),ci(posthoc('host_ca','lava','synthetic'))],
          ['VM-CA',ci(pick(HELD,'host_ca','vm_ca','synthetic',split='heldout')),ci(host_vm)]]
    mech=[['Diagnostic, mean per trace (seeds 20–39)','VM-CA','Host-CA'],['Gate changes per 1,000 arrivals',f"{held_mean('vm_ca','gate_switches')/2.5:.2f}",f"{held_mean('host_ca','gate_switches')/2.5:.2f}"],
          ['Best-Fit decisions placed on LAVA-mode hosts',f"{held_mean('vm_ca','cross_baseline_into_lava'):.2f}",f"{held_mean('host_ca','cross_baseline_into_lava'):.0f}"],
          ['LAVA decisions placed on Best-Fit-mode hosts',f"{held_mean('vm_ca','cross_lava_into_baseline'):.2f}",f"{held_mean('host_ca','cross_lava_into_baseline'):.0f}"],
          ['Capacity fallbacks',f"{held_mean('vm_ca','capacity_fallback'):.0f}",f"{held_mean('host_ca','capacity_fallback'):.0f}"]]
    prof=[['Profile','P(&lt;1 h)','P(1–10 h)','P(10–100 h)','P(≥100 h)','Mean','Class of mean','Gate confidence']];cls=['&lt;1 h','1–10 h','10–100 h','≥100 h']
    for n,(pr,mean,k) in probs.items():
        prof.append([n.capitalize(),*[f'<b>{x:.3f}</b>' if j==max(range(4),key=pr.__getitem__) else f'{x:.3f}' for j,x in enumerate(pr)],f'{mean:.2f} h',cls[k],f'{pr[k]:.3f}'])
    gates=[['Accuracy','VM-CA (original confidence)','VM-CA-Bayes (fused confidence)']]+[[lab(s),f"{gate_rate(s,'vm_ca'):.2f}%",f"{gate_rate(s,'vm_ca_bayes'):.2f}%"] for s in ACC+['synthetic']]
    win=[['Comparison','Setting','Arrival window','Full horizon (primary)']]
    for p,b,s in [('host_ca','best_fit','synthetic'),('host_ca','vm_ca','synthetic'),('host_ca_bayes','vm_ca_bayes','0.5')]:
        win.append([f'{NAME[p]} − {NAME[b]}',lab(s),ci(pick(IMP['test'],p,b,s,'empty_pct_arrivals')),ci(pick(IMP['test'],p,b,s))])
    tie=[t for t,v in THR['scores'].items() if abs(v-THR['scores'][str(THR['selected'])])<1e-12]
    st+=section('7  RQ2: Confidence-aware routing, a diagnostic negative result')+[
         P('7.1  Held-out and fresh-seed outcome','h2'),
         P('Table 7.1 reports the held-out comparison (seeds 20–39) relative to Best-Fit, with the threshold fixed at the report value 0.3. At 50% accuracy and above, both confidence-aware variants follow LAVA exactly, because the gate passes every arrival.'),
         table(held,[2.3,4.9,4.9,4.9]),P('Table 7.1. Held-out seeds 20–39, pp versus Best-Fit, mean [95% CI].','cap'),
         P(f"Under the default predictor, Host-CA does not improve on Best-Fit on the held-out seeds and is significantly worse than VM-CA there (Table 7.2). On {N_TEST} fresh seeds it is significantly worse than Best-Fit ({ci(host_bf)} pp). The small held-out gain of VM-CA does not replicate ({ci(vm_bf)} pp). For reference, the surviving report gave Host-CA minus Best-Fit as {num(float(hist['mean_pp']))} [{num(float(hist['low_pp']))}, {num(float(hist['high_pp']))}] pp; this historical value is not reproduced."),
         table(comp,[4.6,6.2,6.2]),P('Table 7.2. Paired comparisons of Host-CA under the default predictor.','cap'),
         P('7.2  The mechanism works as designed','h2'),
         P('Host isolation removes exactly what it was designed to remove. Both variants receive the same gate sequence, and Host-CA reduces both cross-mode counts to zero without any capacity fallback (Table 7.3). The missing gain is therefore not an implementation defect of the invariant.'),
         table(mech,[8.0,4.5,4.5]),P('Table 7.3. Mechanism counts under the default predictor, held-out seeds.','cap'),
         P('7.3  Diagnosis 1: confidence is inverted relative to predictability','h2'),
         P('Under the default predictor every request arrives with uptime zero, so its confidence is a fixed number per profile (Table 7.4, Figure 7.1). The confidence measures the probability of the class that contains the mixture mean, which for bimodal mixtures is often an unlikely class. Interactive VMs are the most predictable profile, yet they receive the lowest confidence; service VMs are the least predictable, yet they receive the highest. At τ = 0.3 only service VMs pass the gate, so Host-CA reduces to isolating service VMs on their own hosts.'),
         table(prof,[2.1,1.7,1.9,2.2,1.9,1.7,2.6,2.9]),P('Table 7.4. Class probabilities at arrival (most likely class in bold) and the confidence used by the gate.','cap'),
         figure(bar_figure([(n.capitalize(),[max(probs[n][0]),probs[n][0][probs[n][2]]]) for n in C['profiles']],[('Probability of the most likely class',C_VB),('Confidence used by the gate',C_ORANGE)],ref=('τ = 0.3',.3)),
                'Figure 7.1. Predictability versus gate confidence per profile. The gate confidence is lowest for the most predictable profile and highest for the least predictable one.'),
         P(f"Fixing the inversion alone is not enough. On the development seeds, routing by the most likely class and its probability did not beat LAVA at any tested threshold ({num(min(r['mean'] for r in maps))} to {num(max(r['mean'] for r in maps))} pp versus LAVA for the VM-level and host-level variants at τ = 0.4, 0.5 and 0.9; Section 8). The inversion is a contributing factor, not a sufficient explanation."),
         P('7.4  Diagnosis 2: the gate is blind under controlled noise','h2'),
         P('At arrival, the correct-bucket error of the original controlled predictor lies almost entirely inside the predicted class, so the confidence is at least about the global accuracy. At 50% accuracy and above this bound alone exceeds τ = 0.3; at 25% almost every request still passes (Table 7.5). Confidence-aware routing therefore cannot separate the errors that actually harm packing.'),
         table(gates,[3.0,6.5,6.5]),P(f'Table 7.5. Share of arrivals routed to LAVA at τ = 0.3, fresh seeds (n = {N_TEST}); fused confidence (Section 8) for comparison.','cap'),
         P('7.5  Diagnosis 3: isolation costs packing','h2'),
         P(f"Host-CA restricts every request to hosts of its own mode or to empty hosts, so requests often start new hosts that could otherwise have been shared. During the arrival window Host-CA has {abs(win_host['mean']):.2f} pp fewer empty hosts than Best-Fit; over the full horizon the deficit is {abs(host_bf['mean']):.2f} pp, so the drain tail recovers about {F['recovery']:.0%} of the lost empty host-hours (Table 7.6). Combining isolation with the fused predictor makes it worse (Section 9)."),
         table(win,[5.0,2.4,4.8,4.8]),P(f'Table 7.6. Arrival-window and full-horizon differences, fresh seeds (n = {N_TEST}), pp.','cap'),
         P('7.6  Threshold validation','h2'),
         P(f"On validation seeds 200–205 the reconstructed objective (mean Host-CA improvement over LAVA and VM-CA) selects τ = {THR['selected']} by smallest-threshold tie-breaking: τ = {', '.join(tie)} tie at {num(max(THR['scores'].values()))} pp, because at these thresholds no profile passes the gate and Host-CA equals Best-Fit. Every candidate score is negative, so changing the threshold cannot rescue host-level routing; the held-out comparisons keep the frozen report value 0.3."),
         P('Conclusion for RQ2','h2'),
         P('Confidence-aware routing does not help here, and threshold tuning did not change that. The confidence signal is inverted under the default predictor and uninformative under controlled noise, and host isolation has a measurable packing cost. Mode mixing is real, but removing it does not produce a gain. The negative result points at the predictor, which RQ3 changes.')]
    # ---- 8 Method
    st+=section('8  RQ3: Prior-fused lifetime prediction')+[
         P('The diagnosis suggests repairing the lifetime estimate rather than switching policies. The scheduler already knows a profile-level lifetime distribution, because the default predictor is exactly that model. Under controlled noise it also receives a per-VM noisy value whose error model is globally known. Prior fusion combines both sources with Bayes\' rule.'),
         P('Model','h2')]+B([
         '<b>Prior.</b> The VM\'s profile mixture, the same two-exponential model used by the default predictor.',
         '<b>Likelihood.</b> log10 <i>o</i> = log10 <i>T</i> + ε with ε ~ acc·N(0, 0.001²) + (1−acc)·N(0, 3²). The correct-bucket component is far narrower than any grid, so its weight is the global accuracy times the prior density of log10 <i>T</i> at log10 <i>o</i>. It is represented by nine atoms one σ apart over ±4σ.',
         '<b>Censoring.</b> A value at the 336-hour cap contributes P(log10 <i>T</i> + ε ≥ log10 336), not a point likelihood&nbsp;[6].',
         '<b>Posterior.</b> 425 weighted atoms on a log10 grid from 10<super>−4</super> to 10<super>4.5</super> hours (50 per decade), plus the correct-bucket atoms. Suffix sums make each re-prediction O(log n).',
         '<b>Uptime conditioning.</b> Keep the atoms above the current age. An overdue VM therefore falls back smoothly to the incorrect-bucket component, which removes the jump to max(0.1, uptime). If no atom remains, the predictor falls back to the profile prediction.',
         '<b>Outputs.</b> The posterior mean remaining lifetime (capped at 336 hours) and the posterior mass of its LAVA class. This is the same interface as the original predictor, so the NILAS, LAVA and CA rules are unchanged.'])+[
         P('Information boundary','h2'),
         P('The fused predictor uses the noisy value, the global accuracy, the error spreads, the cap and the profile. These are the quantities the original controlled confidence uses, plus the profile model that the default predictor already uses. That prior is the generating distribution; Section 10 tests misspecified priors. The predictor never sees the bucket label or the true lifetime. A unit test rebuilds it on records whose true durations are multiplied by 50, keeps the same noisy values and verifies identical predictions.'),
         P('Worked examples','h2')]+B([
         f'Interactive VM, accuracy 25%, noisy value 300 h. The original predictor returns {ex1raw[0]:.0f} h. The posterior mean is {ex1[0]:.2f} h, close to the profile mean of {probs["interactive"][1]:.2f} h, because 300 h is implausible under the interactive prior.',
         f'Service VM, accuracy 50%, noisy value 2 h. A plausible value moves the posterior mean to {ex2[0]:.1f} h, against the prior mean of {probs["service"][1]:.1f} h and the raw value of {ex2raw[0]:.0f} h.',
         f'Service VM, accuracy 100%, correct value at the 336-hour cap, re-predicted later. At uptime 300 h the original predictor expects {cap300raw[0]:.0f} h remaining and the fused one {cap300[0]:.0f} h, because the true lifetime is only known to exceed 336 h. At 400 h the original jumps to {cap400raw[0]:.0f} h with confidence {cap400raw[1]:.1f}, while the fused one expects {cap400[0]:.0f} h.'])+[
         P('Development history','h2'),
         P(f"Two other ideas were explored on development seeds 0–19 and rejected before registration. An expected host-exit extension score computed from the full mixture gave no gain under the default predictor (LAVA variant {ci(ee)} pp versus LAVA). Routing by the most likely class and its probability did not beat LAVA at any tested threshold ({num(min(r['mean'] for r in maps))} to {num(max(r['mean'] for r in maps))} pp). On these seeds the confidence gate also appeared to add value on top of fusion: VM-CA-Bayes minus LAVA was {num(dev('vm_ca_bayes','0.25'))}, {num(dev('vm_ca_bayes','0.5'))} and {num(dev('vm_ca_bayes','0.75'))} pp at 25%, 50% and 75%, against {num(dev('lava_bayes','0.25'))}, {num(dev('lava_bayes','0.5'))} and {num(dev('lava_bayes','0.75'))} pp for LAVA-Bayes. This is why VM-CA-Bayes was registered as the primary variant; Section 9 shows the gate's advantage did not replicate. The exploration script and its outputs are part of the artifact (scripts/explore_dev.py).")]
    # ---- 9 Evaluation
    famrows=[['Accuracy','VM-CA-Bayes − LAVA','Holm p','Holds','VM-CA-Bayes − Best-Fit','Holm p','Holds']];sh={}
    for i,a in enumerate(REG,1):
        l,b=fam[(a,'lava')],fam[(a,'best_fit')];famrows.append([lab(a),ci(l),pf(l['p_holm']),'yes' if ok(l) else 'no',ci(b),pf(b['p_holm']),'yes' if ok(b) else 'no'])
        for c,r in [(1,l),(4,b)]:
            if ok(r):sh[(c,i)]=POS
    orig=[['Setting']+[NAME[p] for p in ['lava','nilas','vm_ca','host_ca']]]+[[lab(s)]+[ci(t_bf[p][s]) for p in ['lava','nilas','vm_ca','host_ca']] for s in ACC+['synthetic','oracle']]
    bay=[['Setting']+[NAME[p] for p in ['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']]]+[[lab(s)]+[ci(t_bf[p][s]) for p in ['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']] for s in ACC+['synthetic','oracle']]
    SETS=ACC+['synthetic','oracle'];shade=lambda keys:{(c,i):sig_shade(t_bf[k][s]) for i,s in enumerate(SETS,1) for c,k in enumerate(keys,1) if sig_shade(t_bf[k][s])}
    vsbase=[['Accuracy','NILAS-Bayes − NILAS','LAVA-Bayes − LAVA','VM-CA-Bayes − VM-CA','Host-CA-Bayes − Host-CA']];vb=[]
    for s in ACC:
        rs=[pick(IMP['test'],b,b[:-6],s) for b in ['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']];vb.append(rs);vsbase.append([lab(s)]+[ci(r) for r in rs])
    dec=[['Accuracy','LAVA-Bayes − LAVA<br/>(vs noisy predictions alone)','LAVA-Bayes − LAVA, default predictor<br/>(vs prior alone)','VM-CA-Bayes − LAVA-Bayes<br/>(gate on top)']]
    for a,n_,p_,g in zip(REG,noisy,prior,gate):dec.append([lab(a),ci(n_),ci(p_),ci(g)])
    gbt=[['Accuracy','Original gate: correct','Original gate: incorrect','Fused gate: correct','Fused gate: incorrect']]
    for a in REG:gbt.append([lab(a)]+[f"{100*gb[(a,c)][f'{b}_pass']:.1f}%" for c in ('original','fused') for b in ('correct','incorrect')])
    main_fig=line_figure([('VM-CA-Bayes',C_VB,'circle',[t_bf['vm_ca_bayes'][s] for s in ACC]),('LAVA-Bayes',C_LB,'square',[t_bf['lava_bayes'][s] for s in ACC]),('LAVA',C_LAVA,'diamond',[t_bf['lava'][s] for s in ACC])],
                         [.25,.5,.75,.85,1.],refs=[('Oracle LAVA',t_bf['lava']['oracle']['mean'])])
    l75=fam[('0.75','lava')];b25=fam[('0.25','best_fit')];lb25,nb25=t_bf['lava_bayes']['0.25'],t_bf['nilas_bayes']['0.25']
    hb=[pick(IMP['test'],'host_ca_bayes','host_ca',a) for a in REG]
    st+=section('9  Pre-registered evaluation of prior fusion')+[
         P(f'The registered family compares VM-CA-Bayes against LAVA and against Best-Fit at 25%, 50%, 75% and 85% accuracy on fresh seeds 1000–1099 (n = {N_TEST}). VM-CA-Bayes was registered because the project studies confidence-aware scheduling and it was the strongest variant on development seeds; 100% accuracy was excluded because the two predictors then differ only in overdue handling. The threshold stays at the frozen report value 0.3, and no parameter was tuned on any seed. An improvement is claimed only if the mean is positive and the Holm-adjusted p-value is below 0.05.'),
         table(famrows,[1.7,3.6,1.5,1.1,3.6,1.5,1.1],sh),P(f'Table 9.1. Registered family (8 tests). Intervals are unadjusted; p-values are Holm-adjusted. {HOLDS_LAVA} of 4 tests against LAVA and {HOLDS_BF} of 4 against Best-Fit hold.','cap'),
         P(f"Against LAVA, three of four tests hold. At 75% the interval includes zero (lower bound {num(l75['low'])}; Holm p = {pf(l75['p_holm'])}). Against Best-Fit, the tests at 75% and 85% would also hold for unmodified LAVA ({num(t_bf['lava']['0.75']['mean'])} and {num(t_bf['lava']['0.85']['mean'])} pp), so the evidence specific to fusion is the three LAVA tests and the Best-Fit test at 50%. At 25% the registered test against Best-Fit fails ({ci(b25)} pp). Secondary, unadjusted comparisons at 25% put NILAS-Bayes ({ci(nb25)}, p {'&lt; 0.001' if nb25['p']<1e-3 else '= '+pf(nb25['p'])}) and LAVA-Bayes ({ci(lb25)}, p = {pf(lb25['p'])}) above Best-Fit; they were not registered."),
         figure(main_fig,f'Figure 9.1. Gain over Best-Fit versus controlled accuracy, fresh seeds 1000–1099. VM-CA-Bayes is the registered variant; LAVA-Bayes (not registered) and LAVA are shown for reference. Paired means with unadjusted 95% intervals, n = {N_TEST}; the accuracy axis is to scale.'),
         P('All policies versus Best-Fit','h2'),
         P(f'Tables 9.2 and 9.3 list every policy on the test seeds. LA-Binary, omitted from the tables, is slightly below Best-Fit in every setting ({num(max(lb_bf))} to {num(min(lb_bf))} pp).'),
         table(orig,[2.0,3.75,3.75,3.75,3.75],shade(['lava','nilas','vm_ca','host_ca'])),P('Table 9.2. Original policies, fresh seeds, pp versus Best-Fit. Shading marks intervals entirely above (green) or below (red) zero.','cap'),
         table(bay,[2.0,3.75,3.75,3.75,3.75],shade(['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes'])),P('Table 9.3. Prior-fused variants on the same seeds; identical to their base policies under the default predictor and the Oracle.','cap'),
         P('Only the predictor changes','h2'),
         P(f"Table 9.4 compares each fused variant with its own base policy, so the scheduling rules are identical within each column. Fusion helps NILAS, LAVA and VM-CA at most accuracies, most where predictions are least reliable. It makes Host-CA significantly worse at every accuracy from 25% to 85% ({num(max(r['mean'] for r in hb))} to {num(min(r['mean'] for r in hb))} pp), consistent with the more selective gate splitting the fleet further (Diagnosis 3)."),
         table(vsbase,[2.0,3.75,3.75,3.75,3.75],shade_rows(vb)),P('Table 9.4. Fused variant minus its base policy, fresh seeds, pp.','cap'),
         P('Where the gain comes from (post hoc)','h2'),
         P(f"The comparisons in Tables 9.5 and 9.6 were not registered and are descriptive. Fusion improves on both of its ingredients (Table 9.5): the prior alone at every accuracy (second column, the same seeds under the default predictor) and the noisy predictions alone at every accuracy except "+', '.join(lab(a) for a,r in zip(REG,noisy) if r['low']<=0)+f", where the interval includes zero (first column). Adding the confidence gate on top changes little: VM-CA-Bayes minus LAVA-Bayes lies between {num(min(r['mean'] for r in gate))} and {num(max(r['mean'] for r in gate))} pp, with intervals about ±0.05 pp wide, so a gate effect of that size cannot be excluded; the development-seed advantage of the gate did not replicate."),
         table(dec,[1.8,5.0,5.0,5.0],shade_rows([[n_,p_,g] for n_,p_,g in zip(noisy,prior,gate)])),P('Table 9.5. Decomposition of the gain, fresh seeds, pp. The second column pairs each seed under controlled noise with the same seed under the default predictor; Best-Fit is identical in both.','cap'),
         P(f"The fused gate is more selective than the original one but discriminates only weakly between good and bad predictions (Table 9.6). It routes {min(100*gb[(a,'fused')]['correct_pass'] for a in REG):.0f}–{max(100*gb[(a,'fused')]['correct_pass'] for a in REG):.0f}% of correct-bucket predictions to LAVA and {min(100*gb[(a,'fused')]['incorrect_pass'] for a in REG):.0f}–{max(100*gb[(a,'fused')]['incorrect_pass'] for a in REG):.0f}% of incorrect-bucket ones, while the original gate routes essentially all of both. The fused estimate, rather than the gate, appears to absorb most of the damage from wrong predictions. NILAS-Bayes is nominally the strongest fused variant at low accuracy; that comparison would need its own confirmatory test."),
         table(gbt,[2.0,3.6,3.6,3.6,3.6]),P('Table 9.6. Share of arrivals routed to LAVA at τ = 0.3 by the hidden error bucket, fresh seeds (post hoc; the bucket is recovered from the harness\'s random stream and never seen by the scheduler).','cap')]
    # ---- 10 Robustness
    rlabels=[('protocol','Protocol, same seeds'),('bad_sigma=1','Incorrect-bucket σ = 1'),('bad_sigma=0.5','Incorrect-bucket σ = 0.5'),('fusion_assumes_3_true_1','Fusion assumes σ = 3, true σ = 1'),
             ('fusion_assumes_1_true_3','Fusion assumes σ = 1, true σ = 3'),('prior_means_x0.5','Prior means × 0.5'),('prior_means_x2','Prior means × 2'),('load_x2','Arrival rate × 2 (load × 2)')]
    def rob_row(v,b):return [ctrl(a,b) if v=='protocol' else load(a,b) if v=='load_x2' else rob(v,a,b) for a in REG]
    def rob_table(b):
        rows=[['Variant (n = 50)']+[lab(a) for a in REG]];res_rows=[]
        for v,name in rlabels:rs=rob_row(v,b);res_rows.append(rs);rows.append([name]+[ci2(r) for r in rs])
        return rows,shade_rows(res_rows)
    t1,s1=rob_table('lava');t2,s2=rob_table('best_fit')
    taus=MAN['tau']['thresholds'];tt=[['τ']+[lab(a) for a in REG]];tres=[]
    for t in taus:rs=[pick(IMP['tau'],'vm_ca_bayes','lava',a,threshold=t) for a in REG];tres.append(rs);tt.append([f'{t}']+[ci(r) for r in rs])
    good=[r for t,rs in zip(taus,tres) if t<=.5 for r in rs];bad=[r for t,rs in zip(taus,tres) if t>=.7 for r in rs[1:]]
    share=lambda t,a:100*statistics.mean(int(r['high_gate'])/2500 for r in TAU_RAW if float(r['threshold'])==t and r['setting']==a and r['policy']=='vm_ca_bayes')
    hi_shares=[share(t,a) for t in taus if t>=.7 for a in ('0.75','0.85')];lo_shares=[share(.3,a) for a in ('0.75','0.85')]
    leg=[['Setting','LAVA − Best-Fit','VM-CA − Best-Fit','Host-CA − Best-Fit','VM-CA-Bayes − Best-Fit','VM-CA-Bayes − LAVA']];lres=[]
    for s in ACC+['synthetic','oracle']:
        rs=[pick(IMP['legacy'],p,b,s) for p,b in [('lava','best_fit'),('vm_ca','best_fit'),('host_ca','best_fit'),('vm_ca_bayes','best_fit'),('vm_ca_bayes','lava')]];lres.append(rs);leg.append([lab(s)]+[ci2(r) for r in rs])
    cvals=[ctrl(a) for a in REG];lvals=[load(a) for a in REG]
    st+=section('10  Robustness and sensitivity')+[
         P(f'The robustness suites use fresh seeds 2000–2049 (n = {N_ROB}). Each variant changes one assumption: the severity of incorrect predictions, a misspecified error spread in the fusion model, a misspecified prior or the load. The first row of Tables 10.1 and 10.2 is the unmodified protocol on the same seeds. These comparisons are descriptive and not corrected for multiplicity.'),
         table(t1,[4.6,3.0,3.0,3.0,3.0],s1),P('Table 10.1. VM-CA-Bayes minus LAVA, pp, mean and [95% CI]. Green: interval above zero; red: interval below zero.','cap'),
         table(t2,[4.6,3.0,3.0,3.0,3.0],s2),P('Table 10.2. VM-CA-Bayes minus Best-Fit under the same variants.','cap'),
         P('Interpretation','h2')]+B([
         f"On the same seeds the unmodified protocol gives {', '.join(num(r['mean']) for r in cvals)} pp over LAVA at 25–85% accuracy, all with intervals above zero.",
         'Milder errors (σ = 1 or 0.5) make wrong predictions harder to recognize. Gains over LAVA shrink and are significant in only one or two cells, but never significantly negative; gains over Best-Fit remain significant from 50% accuracy upward.',
         'A misspecified error spread keeps a positive mean in every cell, with intervals above zero in two or three of four.',
         'Prior means × 2 keeps all four gains over LAVA. This is consistent with overestimation being the cheaper error here: a short VM on a long-lived host costs little, while a long VM on a short-lived host keeps it busy.',
         f"<b>Failure mode.</b> With halved prior means, correct predictions of long lifetimes look implausible. For a service VM at 85% accuracy whose correct value sits at the 336-hour cap, the posterior mean drops from {cap_true:.0f} h under the true prior to {cap_half:.0f} h. VM-CA-Bayes is then worse than LAVA at 85% accuracy ({ci(x05)} pp; one descriptive cell of 32, unadjusted p = {pf(x05['p'])}), while still better than Best-Fit ({ci(x05bf)} pp). A deployment needs a prior that does not underestimate lifetimes, or a learned prior.",
         f"<b>Load × 2.</b> Doubling the arrival rate (16 VMs per hour, 5,000 VMs, same 180 hosts) lowers Best-Fit's empty share to {load_bf:.1f}%. LAVA's penalty at 25% accuracy deepens to {num(load('0.25','best_fit','lava')['mean'])} pp, and the fused advantage over LAVA grows at 25–75% accuracy ({', '.join(num(r['mean']) for r in lvals[:3])} pp against {', '.join(num(r['mean']) for r in cvals[:3])} on the protocol); at 85% it is {ci(lvals[3])} pp.",
         'An earlier variant with 90 hosts turned out to be a pure rescaling: fewer than 90 hosts are ever busy and ties go to the lowest host index, so every placement equals the 180-host run and only the denominator of pp changes. It is not reported as a load test.'])+[
         P('Threshold sensitivity','h2'),
         P(f"On threshold-sensitivity seeds 200–219 (Table 10.3), thresholds from 0.1 to 0.5 give a positive mean gain over LAVA at every accuracy, with intervals above zero in {sum(r['low']>0 for r in good)} of {len(good)} cells. Thresholds of 0.7 and above still help at 25% accuracy but give negative means at 50–85%, with intervals below zero in {sum(r['high']<0 for r in bad)} of {len(bad)} cells. These thresholds still route {min(hi_shares):.0f}–{max(hi_shares):.0f}% of arrivals to LAVA at 75–85% accuracy, against {min(lo_shares):.0f}–{max(lo_shares):.0f}% at τ = 0.3; sending the additional requests to Best-Fit costs more than it saves. The frozen τ = 0.3 was not chosen from these numbers."),
         table(tt,[2.0,3.75,3.75,3.75,3.75],shade_rows(tres)),P('Table 10.3. VM-CA-Bayes minus LAVA by threshold, seeds 200–219 (n = 20), pp.','cap'),
         P('Continuity with the report split','h2'),
         P('Rerunning the held-out seeds 20–39 with all ten policies reproduces the original-policy columns of Table 7.1 (identical integer decisions; floating-point differences ≤ 3.3×10<super>−16</super>) and shows the same pattern for the fused variant (Table 10.4).'),
         table(leg,[2.0,3.0,3.0,3.0,3.0,3.0],shade_rows(lres)),P('Table 10.4. Held-out seeds 20–39 (n = 20), pp, mean and [95% CI].','cap')]
    # ---- 11 Threats
    st+=section('11  Threats to validity')+B([
         '<b>Calibrated prior.</b> The fusion prior is the generating profile distribution, the same model the default predictor already uses. In practice it would be estimated from history; Table 10.1 shows the risk of underestimating lifetimes.',
         '<b>Known error model.</b> The scheduler is assumed to know the global accuracy and the error spreads, as the original confidence model also assumes. Both directions of σ misspecification were tested.',
         '<b>Error separability.</b> The σ = 3 incorrect bucket of the protocol spans orders of magnitude and is easy to flag as implausible; milder errors give smaller gains.',
         f"<b>Metric and workload.</b> Mixture parameters, profile probabilities and VM shapes are inferred, and only the load was varied. About {F['tail']:.0%} of the primary metric is the drain tail; the arrival-window metric points the same way for the fused predictor ({', '.join(num(r['mean']) for r in arr_vb)} pp over LAVA at 25%, 50% and 85%). Absolute values are not comparable with production results&nbsp;[1].",
         f"<b>Reconstruction fidelity.</b> NILAS outperforms LAVA at most accuracies here (Table 9.2), unlike in&nbsp;[1]; our class, deadline and tie-breaking rules are reconstructed choices. The Oracle is a reference, not an upper bound: NILAS-Bayes at 100% accuracy ({num(t_bf['nilas_bayes']['1.0']['mean'])} pp) exceeds the NILAS Oracle ({num(t_bf['nilas']['oracle']['mean'])} pp).",
         '<b>Statistics and registration.</b> Only the eight-test primary family is multiplicity-adjusted. The decomposition, the NILAS-Bayes observation and all robustness cells are descriptive. The registration is a self-timestamped local file.',
         '<b>Reconstruction boundary.</b> The original code, traces and random streams were not recovered. Disagreement with the surviving report does not falsify it, because critical parameters are unknown.'])+[
         P('Within these limits the internal comparisons are strong. Every policy sees identical traces and noisy values, every comparison is paired, admission is equal, and the main claims rest on seeds that were unused when the hypotheses were registered.')]
    # ---- 12 Conclusion
    st+=section('12  Conclusion and reproducible artifact')+[
         P('The reconstruction restores a runnable study of lifetime-aware VM placement and confirms that prediction quality is a first-order variable: LAVA helps clearly at high accuracy and hurts at low accuracy.'),
         P('The earlier proposal, host-level confidence-aware routing, does not survive reconstruction. This revision explains why: the confidence signal is inverted under the default predictor and blind under controlled noise, and isolating hosts by mode costs packing.'),
         P(f"The diagnosis leads to a different use of uncertainty: put it into the lifetime estimate. Prior-fused prediction combines each noisy prediction with the profile distribution, handles the cap as censoring and conditions on uptime, with every scheduling rule unchanged. In a pre-registered test on {N_TEST} fresh seeds it beats LAVA in {HOLDS_LAVA} of 4 tests ({HOLDS} of 8 overall), and LAVA's low-accuracy penalty disappears. The gain appears to come from the estimate rather than the gate. It persists, sometimes smaller and not always significant, under milder errors, misspecified error spreads, doubled prior means and doubled load, and it can turn negative when the prior underestimates lifetimes. A prior that does not underestimate lifetimes is therefore the main condition for using it."),
         P('Running the artifact','h2'),P('Python 3.9 or newer and the standard library run every experiment; only the report and slide builders need third-party packages (reportlab and python-pptx). From the project directory:')]+[
         KeepTogether([P(escape(c),'code') for c in ['python3 -m unittest discover -s tests -v','python3 run.py --suite all --workers 8 --output results/my_all','python3 run_improvement.py --suite all --workers 8 --output results/improvement',
                                      'python3 scripts/run_robust_extra.py --suite control --workers 8   # and --suite load','python3 scripts/verify_reproduction.py','python3 scripts/build_report.py && python3 scripts/build_deck.py']])]+[
         Spacer(1,.15*cm),
         P('Raw per-seed results, paired summaries, manifests with source hashes, the registration file and figures are under results/ and configs/&nbsp;[9]. IMPROVEMENT.md and REPRODUCTION_DIFFERENCES.md (both in Chinese) record every assumption and its status. The rebuilt source should not be cited as the lost original commit 377cbb1.'),
         P('References','h2')]+[P(r,'ref') for r in [
         '[1] J. Ling et al. LAVA: Lifetime-Aware VM Allocation with Learned Distributions and Adaptation to Mispredictions. MLSys, 2025. arXiv:2412.09840.',
         '[2] A. Verma, L. Pedrosa, M. Korupolu, D. Oppenheimer, E. Tune and J. Wilkes. Large-scale cluster management at Google with Borg. EuroSys, 2015.',
         '[3] E. Cortez, A. Bonde, A. Muzio, M. Russinovich, M. Fontoura and R. Bianchini. Resource Central: Understanding and Predicting Workloads for Improved Resource Management in Large Cloud Platforms. SOSP, 2017.',
         '[4] H. Barbalho et al. Virtual Machine Allocation with Lifetime Predictions. MLSys, 2023.',
         '[5] O. Hadary et al. Protean: VM Allocation Service at Scale. OSDI, 2020.',
         '[6] E. L. Kaplan and P. Meier. Nonparametric Estimation from Incomplete Observations. Journal of the American Statistical Association, 53(282):457–481, 1958.',
         '[7] Surviving course report and presentation, October 2026. Historical metadata and summary results; original code and traces unavailable.',
         '[8] S. Holm. A Simple Sequentially Rejective Multiple Test Procedure. Scandinavian Journal of Statistics, 6(2):65–70, 1979.',
         '[9] Reconstructed artifact: lava_reproduction/ (results/improvement, results/heldout, results/sweep, results/validation, configs/improvement_protocol.json).']]
    merged=[]
    for f in st:
        # Keep every table with its caption, and with a heading directly above it
        # (keepWithNext cannot attach a heading to a KeepTogether).
        if isinstance(f,Paragraph) and f.style.name=='cap' and merged and isinstance(merged[-1],Table):
            group=[merged.pop(),f]
            if merged and isinstance(merged[-1],Paragraph) and merged[-1].style.name=='h2':group.insert(0,merged.pop())
            merged.append(KeepTogether(group))
        else:merged.append(f)
    def deco(canvas,doc):
        canvas.saveState();w,h=A4;canvas.setFont('Arial',7.8);canvas.setFillColor(MUTED)
        if doc.page>1:canvas.drawString(2*cm,h-1.25*cm,'Revisiting Lifetime-Aware VM Allocation');canvas.setStrokeColor(RULE);canvas.setLineWidth(.5);canvas.line(2*cm,h-1.42*cm,w-2*cm,h-1.42*cm)
        canvas.drawString(2*cm,1.2*cm,f'Reconstruction, diagnosis and prior-fused prediction · revised {REVISED}');canvas.drawRightString(w-2*cm,1.2*cm,str(doc.page));canvas.restoreState()
    doc=OutlinedDoc(str(out),pagesize=A4,leftMargin=2*cm,rightMargin=2*cm,topMargin=2.1*cm,bottomMargin=2.0*cm,
                    title='Revisiting Lifetime-Aware VM Allocation: Reconstruction, Diagnosis and Prior-Fused Lifetime Prediction',author='CE7490 Course Project',subject='LAVA reconstruction and prior-fused lifetime prediction')
    doc.build(merged,onFirstPage=deco,onLaterPages=deco);print(out)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',default=str(root.parent/'Revisiting_Lifetime_Aware_VM_Allocation_Report_v3.pdf'));build(Path(a.parse_args().output))
