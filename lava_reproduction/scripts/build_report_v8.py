#!/usr/bin/env python3
"""Moderate revision of v6: retain the research narrative and evidence chain.

Only four redundant tables are omitted. Body size, experiments, detailed
methods, protocol, primary comparisons and robustness matrices are retained.
"""
import argparse
import json
import re
from pathlib import Path
from reportlab.platypus import Table
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph, TableStyle
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, PageTemplate,
                               KeepTogether, CondPageBreak)
from reportlab.platypus.flowables import _listWrapOn
from reportlab.pdfgen.canvas import Canvas

import build_report_mlsys as layout
import build_report_v6 as original
from build_report_v7 import compact_confidence, compact_fusion

BASE_DECORATION = layout.decoration
OMITTED = {'6.1','7.4','9.6','10.4'}


def revised_capture():
    source,old=original.cited_capture()
    P=source.P
    omitted_indices=set()
    omitted_rows={}
    for i,flow in enumerate(old):
        if getattr(flow,'role',None)=='cap':
            m=re.match(r'Table (\d+\.\d+)\.',flow.original)
            if m and m[1] in OMITTED:
                assert isinstance(old[i-1],Table)
                omitted_indices.update([i-1,i])
                omitted_rows[m[1]]=[[getattr(c,'original',str(c)) for c in row]
                                    for row in old[i-1]._cellvalues]
    content=[]
    for i,flow in enumerate(old):
        if i in omitted_indices:continue
        if isinstance(flow,layout.PaperParagraph):
            text=flow.original
            if text.startswith('Figure 6.1 and Table 6.1'):
                text=text.replace('Figure 6.1 and Table 6.1 show','Figure 6.1 shows')
            text=text.replace('(Table 7.4, Figure 7.1)','(Figure 7.1)')
            text=text.replace('(Table 9.6)','(post-hoc bucket analysis)')
            text=text.replace('Tables 9.5 and 9.6','Table 9.5 and the bucket analysis')
            text=text.replace('(Table 10.4)','(complete archived results)')
            text=re.sub(r'\bTable 7\.([56])\b',lambda m:'Table 7.'+str(int(m[1])-1),text)
            if text.startswith('Censoring matters when a service VM'):
                text=text.replace('has a correct prediction','at 100% controlled accuracy has a capped noisy prediction')
                text=text.replace('because the lifetime is only known to exceed 336 h.',
                    'because the uncapped noisy observation is at least 336 h, rather than an exact departure time.')
            text=text.replace('about 68% of the primary metric is the drain tail',
                              'about 68% of the evaluation horizon is the drain tail')
            text=text.replace('About 68% of the primary metric is the drain tail',
                              'About 68% of the evaluation horizon is the drain tail')
            if text.startswith('The fused gate is more selective'):
                text+=' Hidden error-bucket labels are reconstructed only by the analysis and never reach the scheduler.'
            if text.startswith('Under the default predictor, LAVA'):
                oracle=omitted_rows['6.1'][-1][1]
                text+=' For comparison, the initial-split Oracle gain is '+oracle+'; the full sweep values are archived.'
            text=text.replace('A deployment needs a prior that does not underestimate lifetimes, or a learned prior.',
                              'This failure motivates learning priors from history and testing systematic underestimation.')
            if flow.role=='code':text=text.replace('build_report_v6.py','build_report_v8.py')
            content.append(P(text,flow.role))
        elif isinstance(flow,Drawing) and getattr(flow,'_data_points',None) and isinstance(flow._data_points[0],dict) and 'profile' in flow._data_points[0]:
            drawing=compact_confidence(source)
            drawing._paper_final_style=True
            drawing._paper_narrow=True
            content.append(drawing)
        else:content.append(flow)

    # Let the accuracy section's detailed results fill the available column
    # before the indivisible plot, instead of ending a page after one sentence.
    i=next(i for i,f in enumerate(content) if isinstance(f,Drawing))
    figure=content[i:i+2]
    assert getattr(figure[1],'role',None)=='cap'
    del content[i:i+2]
    index=next(i for i,f in enumerate(content)
               if getattr(f,'role',None)=='body' and f.original.startswith('Learning-augmented online algorithms'))
    content[index:index]=figure

    assert sum(isinstance(f,Table) for f in content)==17
    assert sum(isinstance(f,Drawing) for f in content)==3
    assert sum(getattr(f,'role',None)=='ref' for f in content)==21
    return source,content


def decoration(canvas,document):
    BASE_DECORATION(canvas,document)
    canvas.saveState()
    canvas.setFont('PaperTimes',9)
    canvas.drawCentredString(layout.LEFT+layout.TEXT_W/2,46,str(document.page))
    canvas.restoreState()


def continuous_capture():
    source,content=revised_capture()
    result=[]
    table_data=[]
    for i,flow in enumerate(content):
        if isinstance(flow,Table):
            caption=content[i+1]
            assert getattr(caption,'role',None)=='cap'
            label=re.match(r'Table (\d+\.\d+)\.',caption.original)[1]
            rows=[[getattr(c,'original',str(c)) for c in row] for row in flow._cellvalues]
            if label=='2.1':
                rows=[['Policy','Placement and prediction use']]+[
                    [r[0],r[1]+'<br/><i>Prediction:</i> '+r[2]] for r in rows[1:]]
                widths=[54,180]
            elif label=='5.1':
                rows=[['Suite / seeds','Settings and policies','Runs']]+[
                    [r[0]+'<br/>'+r[1],r[2],r[3]] for r in rows[1:]]
                widths=[60,134,40]
            elif label=='9.1':
                rows=[['Acc.','VM-CA-Bayes − LAVA','VM-CA-Bayes − Best-Fit']]+[
                    [r[0],r[1]+'<br/>p<sub>H</sub>: '+r[2]+'; '+r[3],
                     r[4]+'<br/>p<sub>H</sub>: '+r[5]+'; '+r[6]] for r in rows[1:]]
                widths=[30,102,102]
            elif label in ('9.2','9.3','9.4'):
                widths=[38,49,49,49,49]
                if label=='9.4':rows[0]=['Acc.','NILAS','LAVA','VM-CA','Host-CA']
            elif label=='9.5':
                widths=[30,68,68,68]
                rows[0]=['Acc.','Fused − noisy','Fused − prior','Gate on top']
            elif label in ('10.1','10.2'):
                widths=[66,42,42,42,42]
                rows[0]=['Variant','25%','50%','75%','85%']
            elif label=='10.3':widths=[26,52,52,52,52]
            elif label=='3.1':widths=[72,108,54]
            elif label=='3.2':widths=[66,56,56,56]
            elif label=='7.1':widths=[39,65,65,65]
            elif label=='7.2':widths=[80,77,77]
            elif label=='7.3':widths=[154,40,40]
            elif label=='7.4':widths=[34,100,100]
            elif label=='7.5':widths=[72,40,61,61]
            else:raise ValueError(label)
            # Reflow the existing fields at their original 8.6-point size,
            # without dropping numeric values or silently scaling text.
            cells=[[Paragraph(str(v),source.S['cellb' if r==0 else 'cell'])
                    for v in row] for r,row in enumerate(rows)]
            table=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1)
            commands=[('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
                ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                ('LINEABOVE',(0,0),(-1,0),.8,layout.BLACK),
                ('LINEBELOW',(0,0),(-1,0),.5,layout.BLACK),
                ('LINEBELOW',(0,-1),(-1,-1),.8,layout.BLACK)]
            if label!='9.1':commands+=list(flow._bkgrndcmds)
            table.setStyle(TableStyle(commands))
            result.extend([caption,table])
            table_data.append({'label':'Table '+label,'rows':rows})
        elif getattr(flow,'role',None)=='cap' and flow.original.startswith('Table '):
            continue
        elif isinstance(flow,Drawing) and hasattr(flow,'_oracle_mean'):
            result.append(compact_fusion(source))
        else:result.append(flow)
    source._v8_tables=table_data
    return source,result


def build_continuous(output,audit=None):
    layout.register_fonts()
    source,content=continuous_capture()
    first_h1=next(i for i,f in enumerate(content) if getattr(f,'role',None)=='h1')
    header=layout.assemble(source,content[:first_h1]+[source.P('1  Introduction','h1')])[:-1]
    _,height=_listWrapOn(header,layout.TEXT_W,Canvas('/dev/null'))
    body_top=layout.PAGE_H-72-height-7
    first=[Frame(layout.LEFT,body_top+7,layout.TEXT_W,height,id='title',
                 leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)]
    first += [Frame(layout.LEFT+k*(layout.COL_W+layout.GUTTER),layout.BOTTOM,
                    layout.COL_W,body_top-layout.BOTTOM,id=f'first-{k}',
                    leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0) for k in range(2)]
    later=[Frame(layout.LEFT+k*(layout.COL_W+layout.GUTTER),layout.BOTTOM,
                 layout.COL_W,layout.PAGE_H-layout.TOP-layout.BOTTOM,id=f'column-{k}',
                 leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0) for k in range(2)]
    doc=BaseDocTemplate(str(output),pagesize=(layout.PAGE_W,layout.PAGE_H),
        title='Revisiting Lifetime-Aware VM Allocation: Reconstruction, Diagnosis and Prior-Fused Lifetime Prediction',
        author='; '.join(m['name'] for m in layout.team_metadata()['members']),
        subject='Course report: detailed methods and evaluation in MLSys-style columns')
    doc.addPageTemplates([PageTemplate('first',frames=first,onPage=decoration,autoNextPageTemplate='later'),
                          PageTemplate('later',frames=later,onPage=decoration)])
    raw=content[first_h1:];story=[];i=0
    while i<len(raw):
        f=raw[i]
        if isinstance(f,Drawing):
            story.append(KeepTogether([f,raw[i+1]]));i+=2;continue
        if (getattr(f,'role',None) in ('h1','h2') and i+2<len(raw)
                and getattr(raw[i+1],'role',None)=='cap' and isinstance(raw[i+2],Table)):
            caption,table=raw[i+1:i+3]
            table.wrapOn(None,layout.COL_W,1e7)
            _,heading_height=f.wrap(layout.COL_W,1e7)
            _,caption_height=caption.wrap(layout.COL_W,1e7)
            minimum=(heading_height+f.getSpaceBefore()+f.getSpaceAfter()+caption_height
                     +caption.getSpaceBefore()+caption.getSpaceAfter()+sum(table._rowHeights[:2])+2)
            story.append(CondPageBreak(minimum))
            f.keepWithNext=False
        if getattr(f,'role',None)=='cap' and i+1<len(raw) and isinstance(raw[i+1],Table):
            table=raw[i+1]
            table.wrapOn(None,layout.COL_W,1e7)
            _,cap_height=f.wrap(layout.COL_W,1e7)
            # Bind the caption to the header and first data row, not the
            # entire table. The remaining rows may use the current column.
            minimum=cap_height+f.getSpaceBefore()+f.getSpaceAfter()+sum(table._rowHeights[:2])+2
            story.append(CondPageBreak(minimum));f.keepWithNext=False
        if (getattr(f,'role',None) in ('h1','h2') and i+1<len(raw)
                and getattr(raw[i+1],'role',None)=='body'):
            following=raw[i+1]
            following.wrap(layout.COL_W,1e7)
            parts=following.split(layout.COL_W,following.style.leading*3) or [following]
            if len(parts)>1:parts[0].spaceAfter=0
            f.keepWithNext=False
            holder=Table([[[f,parts[0]]]],colWidths=[layout.COL_W],splitByRow=0)
            holder.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),
                ('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),
                ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
            story.extend([holder,*parts[1:]]);i+=2;continue
        story.append(f);i+=1
    output.parent.mkdir(parents=True,exist_ok=True)
    doc.build([*header,FrameBreak(),*story])
    if audit:
        records=[]
        for f in content:
            if isinstance(f,layout.PaperParagraph):records.append({'type':f.role,'text':f.original})
            elif isinstance(f,Drawing):records.append({'type':'figure','points':f._data_points,
                                                       'oracle':getattr(f,'_oracle_mean',None)})
        audit.parent.mkdir(parents=True,exist_ok=True)
        audit.write_text(json.dumps({'content':records,'tables':source._v8_tables},indent=2,ensure_ascii=False))
    print(output)


def build(output,audit=None):
    layout.COMPACT_ACCURACY_TABLE=True
    layout.TABLE_PADDING=2.2
    build_continuous(output,audit)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=layout.PROJECT/'Revisiting_Lifetime_Aware_VM_Allocation_Report_v8.pdf')
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args();build(args.output,args.audit)
